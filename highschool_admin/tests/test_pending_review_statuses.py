"""The three "pending" surfaces must agree on which statuses count.

`status__in=['applied']` was written out three times — the Pending Review tab
(views/api/viewsets.py), the Pending Pay Type feed (views/registrations.py) and
the dashboard pay-type message (page_messages.py). A tenant whose registration
vocabulary differs had to find all three; missing one leaves a screen silently
wrong rather than erroring. These tests pin the single resolver and assert each
call site routes through it.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from . import PKG
from ..services.registration import pending_review_statuses

SENTINEL = ['applied', 'sentinel_status']


class PendingReviewStatusesResolverTests(SimpleTestCase):
    def test_default_is_applied_when_tenant_does_not_override(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertEqual(pending_review_statuses(), ['applied'])

    def test_tenant_override_wins(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda: ['applied', 'pre_applied']):
            self.assertEqual(
                pending_review_statuses(), ['applied', 'pre_applied'])

    def test_caller_cannot_mutate_the_default(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            pending_review_statuses().append('junk')
            self.assertEqual(pending_review_statuses(), ['applied'])

    def test_override_is_looked_up_under_an_hsadmin_scoped_name(self):
        """The tenant module is shared with cis's registration overrides, so
        the name must not collide with one of theirs."""
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None) as gto:
            pending_review_statuses()
        gto.assert_called_once_with(
            'registration', 'hsadmin_pending_review_statuses')


def _chained_manager():
    """A StudentRegistration.objects stand-in where every .filter() chains and
    the final queryset iterates empty."""
    qs = MagicMock()
    qs.__iter__ = MagicMock(return_value=iter([]))
    qs.filter.return_value = qs
    qs.select_related.return_value = qs
    qs.count.return_value = 0
    manager = MagicMock()
    manager.filter.return_value = qs
    return manager, qs


def _status_filters(qs, manager):
    """Every status__in value passed to any filter in the chain."""
    calls = list(qs.filter.call_args_list) + list(manager.filter.call_args_list)
    return [c.kwargs['status__in'] for c in calls if 'status__in' in c.kwargs]


class CallSitesUseTheResolverTests(SimpleTestCase):

    def test_dashboard_pay_type_message_uses_resolver(self):
        from ..page_messages import pending_pay_type
        manager, qs = _chained_manager()
        hs = MagicMock()
        hs.values_list.return_value = [1]
        with patch(f'{PKG}.page_messages.get_user_highschools', return_value=hs), \
             patch(f'{PKG}.page_messages.pending_review_statuses',
                   return_value=SENTINEL), \
             patch('cis.models.section.StudentRegistration.objects', manager):
            pending_pay_type(MagicMock())
        self.assertIn(SENTINEL, _status_filters(qs, manager))

    def test_pending_pay_type_feed_uses_resolver(self):
        from ..views.registrations import get_pending_pay_type
        manager, qs = _chained_manager()
        request = MagicMock()
        request.GET.get.return_value = None
        with patch(f'{PKG}.views.registrations.get_user_highschools',
                   return_value=MagicMock()), \
             patch(f'{PKG}.views.registrations.pending_review_statuses',
                   return_value=SENTINEL), \
             patch('cis.models.section.StudentRegistration.objects', manager):
            get_pending_pay_type(request)
        self.assertIn(SENTINEL, _status_filters(qs, manager))

    def test_pending_review_viewset_uses_resolver(self):
        from ..views.api.viewsets import PendingReviewViewSet
        manager, qs = _chained_manager()
        view = PendingReviewViewSet()
        view.request = MagicMock()
        view.request.GET.get.return_value = None
        with patch(f'{PKG}.views.api.viewsets.get_user_highschools',
                   return_value=MagicMock()), \
             patch(f'{PKG}.views.api.viewsets.pending_review_statuses',
                   return_value=SENTINEL), \
             patch('cis.models.section.StudentRegistration.objects', manager):
            view.get_queryset()
        self.assertIn(SENTINEL, _status_filters(qs, manager))


class NoStrayAppliedLiteralTests(SimpleTestCase):
    """Guard against a fourth copy reappearing."""

    def test_only_the_resolver_names_the_default_status(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in ('tests', '__pycache__', 'migrations')]
            for name in filenames:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(dirpath, name)
                if os.path.normpath(path).endswith(
                        os.path.join('services', 'registration.py')):
                    continue
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if "status__in=['applied']" in line.replace('"', "'"):
                            offenders.append(
                                f'{os.path.relpath(path, root)}:{lineno}')
        self.assertEqual(offenders, [], '\n'.join(offenders))
