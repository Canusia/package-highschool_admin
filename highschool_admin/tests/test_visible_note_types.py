"""Which note types an HS admin may see is tenant visibility policy.

`meta__type__contains='to_counselor'` was hardcoded twice inside one method
(StudentNoteViewSet.get_queryset, the student-scoped and school-wide branches).
A tenant that names the marker differently, or wants counselors to see a second
type, had two places to change and no seam to change them from.
"""
from unittest.mock import MagicMock, patch

from django.db.models import Q
from django.test import SimpleTestCase

from . import PKG
from ..services.notes import (
    hsadmin_visible_note_types, hsadmin_visible_notes_q,
)


class VisibleNoteTypesResolverTests(SimpleTestCase):
    def test_default_is_to_counselor(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertEqual(hsadmin_visible_note_types(), ['to_counselor'])

    def test_tenant_override_wins(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda: ['to_counselor', 'to_school']):
            self.assertEqual(
                hsadmin_visible_note_types(), ['to_counselor', 'to_school'])

    def test_caller_cannot_mutate_the_default(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            hsadmin_visible_note_types().append('junk')
            self.assertEqual(hsadmin_visible_note_types(), ['to_counselor'])

    def test_override_is_looked_up_under_an_hsadmin_scoped_name(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None) as gto:
            hsadmin_visible_note_types()
        gto.assert_called_once_with('notes', 'hsadmin_visible_note_types')


class VisibleNotesQTests(SimpleTestCase):
    def test_default_q_is_the_original_single_contains_lookup(self):
        """One type must produce exactly the pre-existing lookup, not an OR
        chain wrapped around it — otherwise the default query plan changes."""
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertEqual(
                str(hsadmin_visible_notes_q()),
                str(Q(meta__type__contains='to_counselor')))

    def test_multiple_types_are_ored(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda: ['to_counselor', 'to_school']):
            self.assertEqual(
                str(hsadmin_visible_notes_q()),
                str(Q(meta__type__contains='to_counselor')
                    | Q(meta__type__contains='to_school')))

    def test_empty_type_list_matches_nothing_rather_than_everything(self):
        """A tenant returning [] means "counselors see no notes". An empty Q()
        would mean the opposite -- every note in scope, a disclosure bug."""
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda: []):
            q = hsadmin_visible_notes_q()
        self.assertNotEqual(str(q), str(Q()))
        from cis.models.note import StudentNote
        self.assertEqual(StudentNote.objects.filter(q).count(), 0)


class ViewSetUsesTheResolverTests(SimpleTestCase):
    """Both branches of get_queryset -- student-scoped and school-wide."""

    def _run(self, student_id):
        from ..views.api.viewsets import StudentNoteViewSet
        sentinel = Q(meta__type__contains='sentinel_type')
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.values_list.return_value = []
        qs.__or__ = MagicMock(return_value=qs)
        manager = MagicMock()
        manager.filter.return_value = qs
        view = StudentNoteViewSet()
        view.request = MagicMock()
        view.request.GET.get.return_value = student_id
        with patch(f'{PKG}.views.api.viewsets.get_user_highschools',
                   return_value=MagicMock()), \
             patch(f'{PKG}.views.api.viewsets.hsadmin_visible_notes_q',
                   return_value=sentinel), \
             patch('cis.models.note.StudentNote.objects', manager), \
             patch('cis.models.section.StudentRegistration.objects', manager):
            view.get_queryset()
        passed = [c.args for c in manager.filter.call_args_list if c.args]
        return sentinel, passed

    def test_student_scoped_branch_uses_resolver(self):
        sentinel, passed = self._run('some-student-id')
        self.assertIn((sentinel,), passed)

    def test_school_wide_branch_uses_resolver(self):
        sentinel, passed = self._run(None)
        self.assertIn((sentinel,), passed)


class NoStrayNoteTypeLiteralTests(SimpleTestCase):
    def test_only_the_resolver_names_the_note_type(self):
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
                        os.path.join('services', 'notes.py')):
                    continue
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if 'to_counselor' in line:
                            offenders.append(
                                f'{os.path.relpath(path, root)}:{lineno}')
        self.assertEqual(offenders, [], '\n'.join(offenders))
