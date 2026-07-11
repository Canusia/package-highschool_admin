"""PT-10: /highschool_admin/student/<uuid> and the detail page's notes API
must be scoped to the caller's administered high schools."""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase, RequestFactory
from django.urls import reverse

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.note import StudentNote
from cis.models.settings import Setting
from cis.models.student import Student
from two_step.models import TwoStep

User = get_user_model()


def _provision_groups():
    for name in ('student', 'ce', 'highschool_admin'):
        Group.objects.get_or_create(name=name)


def _provision_registration_setting():
    """registration_terms() reads a Setting keyed by CAMPUS_CODE_PREFIX; without
    it the detail view's `for term in current_registration_terms` iterates None."""
    from django.conf import settings as dj_settings
    key = f'{dj_settings.CAMPUS_CODE_PREFIX}_cis_registrations'
    Setting.objects.get_or_create(
        key=key, defaults={'value': {'registration_terms': []}},
    )


def _provision_menu_setting():
    """The detail view renders the highschool_admin portal blurb, whose form reads
    the `highschool_admin_menu` Setting (a JSON-string list). Without it
    json.loads(None) raises. A minimal one-item menu satisfies the form builder."""
    import json
    Setting.objects.get_or_create(
        key='cis.settings.menu',
        defaults={'value': {'highschool_admin_menu': json.dumps([
            {'type': 'nav-item', 'name': 'home', 'label': 'Home',
             'url': 'highschool_admin:dashboard'},
        ])}},
    )


def _make_student(highschool, tag):
    user = User.objects.create_user(
        username=f'stu_{tag}', email=f'stu_{tag}@example.com',
        password='x', first_name='Stu', last_name=tag,
    )
    return Student.objects.create(user=user, highschool=highschool)


def _hs_admin_bound_to(tag, *highschools):
    user = User.objects.create_user(
        username=f'hsadmin_{tag}', email=f'hsadmin_{tag}@example.com',
        password='x', first_name='Admin', last_name=tag,
    )
    user.groups.add(Group.objects.get(name='highschool_admin'))
    hsadmin = HSAdministrator.objects.create(user=user)
    position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
    for hs in highschools:
        HSAdministratorPosition.objects.create(
            hsadmin=hsadmin, highschool=hs, position=position, status='Active',
        )
    return user


class _NoLoginHistoryMixin:
    @classmethod
    def setUpClass(cls):
        # django_login_history's post_login signal handler blows up in tests
        # because the request has no usable IP. Disconnect for the duration.
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if _login_history_post_login is not None:
            user_logged_in.connect(_login_history_post_login)


class StudentDetailScopingTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        _provision_registration_setting()
        _provision_menu_setting()
        cls.hs_a = HighSchool.objects.create(name='HS Alpha')
        cls.hs_b = HighSchool.objects.create(name='HS Bravo')
        cls.in_scope_student = _make_student(cls.hs_a, 'in')
        cls.out_scope_student = _make_student(cls.hs_b, 'out')
        cls.attacker = _hs_admin_bound_to('detail', cls.hs_a)

    def setUp(self):
        self.client.force_login(self.attacker)
        # PT-19: highschool_admin page views are now gated by two-step
        # verification at the URL choke point. Mark this session verified so
        # these scoping tests exercise the view, not the second-factor gate.
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key,
            user=self.attacker,
            defaults={'verification_code': '123456', 'verified': True},
        )

    def test_in_scope_student_detail_is_accessible(self):
        url = reverse('highschool_admin:student', args=[self.in_scope_student.id])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_out_of_scope_student_detail_is_404(self):
        url = reverse('highschool_admin:student', args=[self.out_scope_student.id])
        self.assertEqual(self.client.get(url).status_code, 404)


class StudentNoteViewSetScopingTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        cls.hs_a = HighSchool.objects.create(name='HS Alpha')
        cls.hs_b = HighSchool.objects.create(name='HS Bravo')
        cls.in_scope_student = _make_student(cls.hs_a, 'note_in')
        cls.out_scope_student = _make_student(cls.hs_b, 'note_out')
        cls.attacker = _hs_admin_bound_to('notes', cls.hs_a)

        author = User.objects.create_user(
            username='note_author', email='note_author@example.com', password='x',
        )
        cls.in_note = StudentNote.objects.create(
            student=cls.in_scope_student, note='in', createdby=author,
            meta={'type': 'to_counselor'},
        )
        cls.out_note = StudentNote.objects.create(
            student=cls.out_scope_student, note='out', createdby=author,
            meta={'type': 'to_counselor'},
        )

    def _qs(self, **params):
        from ..views.api.viewsets import StudentNoteViewSet
        vs = StudentNoteViewSet()
        req = RequestFactory().get('/', params)
        req.user = self.attacker
        vs.request = req
        return vs.get_queryset()

    def test_in_scope_student_id_returns_notes(self):
        ids = [n.id for n in self._qs(student_id=str(self.in_scope_student.id))]
        self.assertIn(self.in_note.id, ids)

    def test_out_of_scope_student_id_returns_nothing(self):
        ids = [n.id for n in self._qs(student_id=str(self.out_scope_student.id))]
        self.assertNotIn(self.out_note.id, ids)
