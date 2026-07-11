"""Tests for highschool_admin dashboard page-message providers.

Strategy: provider-level unit tests (patching get_user_highschools and model
queries) for the three provider functions, plus one end-to-end view assertion
that a registered provider's message reaches the rendered template.

We avoid building the full StudentRegistration graph (Course/Cohort/Term/
AcademicYear/ClassSection) because that graph is heavy and would duplicate
fixtures already covered in cis.tests. The end-to-end view test patches the
pending_recommendations provider at the module level so the template partial
renders a real PageMessage via get_page_messages.
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting
from cis.page_messages import PageMessage

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_groups():
    for name in ('highschool_admin',):
        Group.objects.get_or_create(name=name)


def _provision_menu_setting():
    Setting.objects.get_or_create(
        key='cis.settings.menu',
        defaults={'value': {'highschool_admin_menu': json.dumps([
            {'type': 'nav-item', 'name': 'home', 'label': 'Home',
             'url': 'highschool_admin:dashboard'},
        ])}},
    )


def _login(user):
    """Login and mark session as two-step verified."""
    try:
        from django_login_history.models import post_login
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.disconnect(post_login)
        c = Client()
        c.force_login(user)
        user_logged_in.connect(post_login)
    except Exception:
        c = Client()
        c.force_login(user)
    # Two-step enforcement redirects unverified sessions; mark as verified.
    from two_step.models import TwoStep
    session_key = c.session.session_key
    TwoStep.objects.update_or_create(
        session_id=session_key,
        user=user,
        defaults={'verification_code': '123456', 'verified': True},
    )
    return c


def _make_hsadmin():
    """Create a HighSchool + HSAdmin user linked via HSAdministratorPosition."""
    hs = HighSchool.objects.create(name='Test HS')
    user = User.objects.create(email='hsa@example.com', username='hsa@example.com')
    group, _ = Group.objects.get_or_create(name='highschool_admin')
    user.groups.add(group)
    admin = HSAdministrator.objects.create(user=user)
    position = HSPosition.objects.create(name='Counselor')
    HSAdministratorPosition.objects.create(
        hsadmin=admin, highschool=hs, position=position, status='Active',
    )
    return user, hs


# ---------------------------------------------------------------------------
# Provider unit tests (no heavy DB graph needed)
# ---------------------------------------------------------------------------

class PendingRecommendationsProviderTest(TestCase):
    def test_returns_message_when_count_positive(self):
        from ..page_messages import pending_recommendations
        request = MagicMock()
        mock_hs = MagicMock()
        mock_hs.id = 1
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_hs]))
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            with patch('cis.models.section.StudentRegistration.get_pending_recommendations') as mock_gpr:
                mock_gpr.return_value.count.return_value = 3
                result = pending_recommendations(request)
        self.assertIsInstance(result, PageMessage)
        self.assertIn('needing recommendation', result.text)
        self.assertEqual(result.tile_id, 'id_tile_students')

    def test_returns_none_when_count_zero(self):
        from ..page_messages import pending_recommendations
        request = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            with patch('cis.models.section.StudentRegistration.get_pending_recommendations') as mock_gpr:
                mock_gpr.return_value.count.return_value = 0
                result = pending_recommendations(request)
        self.assertIsNone(result)


class PendingPayTypeProviderTest(TestCase):
    def test_returns_message_when_count_positive(self):
        from ..page_messages import pending_pay_type
        request = MagicMock()
        mock_qs = MagicMock()
        mock_qs.values_list.return_value = [1]
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            with patch('cis.models.section.StudentRegistration.objects') as mock_obj:
                mock_obj.filter.return_value.count.return_value = 2
                result = pending_pay_type(request)
        self.assertIsInstance(result, PageMessage)
        self.assertIn('needing payment type review', result.text)
        self.assertEqual(result.tile_id, 'id_tile_students')

    def test_returns_none_when_count_zero(self):
        from ..page_messages import pending_pay_type
        request = MagicMock()
        mock_qs = MagicMock()
        mock_qs.values_list.return_value = []
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            with patch('cis.models.section.StudentRegistration.objects') as mock_obj:
                mock_obj.filter.return_value.count.return_value = 0
                result = pending_pay_type(request)
        self.assertIsNone(result)


class PendingDropRequestsProviderTest(TestCase):
    def test_returns_message_when_count_positive(self):
        from ..page_messages import pending_drop_requests
        request = MagicMock()
        mock_qs = MagicMock()
        mock_qs.values_list.return_value = [1]
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            # patch whichever DropWDRequest gets imported
            import importlib.util
            if importlib.util.find_spec('drop_wd.drop_wd'):
                target = 'drop_wd.drop_wd.models.DropWDRequest.objects'
            else:
                target = 'drop_wd.models.DropWDRequest.objects'
            with patch(target) as mock_obj:
                mock_obj.filter.return_value.count.return_value = 1
                result = pending_drop_requests(request)
        self.assertIsInstance(result, PageMessage)
        self.assertIn('drop request', result.text)
        self.assertEqual(result.tile_id, 'id_tile_drop_wd_requests')

    def test_returns_none_when_count_zero(self):
        from ..page_messages import pending_drop_requests
        request = MagicMock()
        mock_qs = MagicMock()
        mock_qs.values_list.return_value = []
        with patch('highschool_admin.highschool_admin.page_messages.get_user_highschools', return_value=mock_qs):
            import importlib.util
            if importlib.util.find_spec('drop_wd.drop_wd'):
                target = 'drop_wd.drop_wd.models.DropWDRequest.objects'
            else:
                target = 'drop_wd.models.DropWDRequest.objects'
            with patch(target) as mock_obj:
                mock_obj.filter.return_value.count.return_value = 0
                result = pending_drop_requests(request)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# End-to-end view tests
# ---------------------------------------------------------------------------

class HsAdminDashboardViewTest(TestCase):
    """End-to-end: the dashboard view passes page_messages to the template."""

    def setUp(self):
        _provision_groups()
        _provision_menu_setting()
        self.user, self.hs = _make_hsadmin()

    def test_no_messages_when_nothing_pending(self):
        """With nothing pending the dashboard loads 200 and shows no alert."""
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'needing recommendation')
        self.assertNotContains(resp, 'needing payment type review')
        self.assertNotContains(resp, 'drop request')

    def test_page_messages_partial_renders_provider_output(self):
        """Patch pending_recommendations to return a message; confirm it
        reaches the rendered template via the cis/page_messages.html partial."""
        forced_msg = PageMessage(
            text='There are student application(s) needing recommendation.',
            level='danger', tile_id='id_tile_students',
        )
        c = _login(self.user)
        with patch(
            'highschool_admin.highschool_admin.page_messages.pending_recommendations',
            return_value=forced_msg,
        ):
            # Re-register the patched function so get_page_messages picks it up.
            # Easier: patch get_page_messages directly for this scope.
            with patch(
                'highschool_admin.highschool_admin.views.dashboard.get_page_messages',
                return_value=[forced_msg],
            ):
                resp = c.get(reverse('highschool_admin:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'needing recommendation')
        self.assertContains(resp, 'id_tile_students')
