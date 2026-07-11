"""The /highschool_admin/api/student-registrations/ DataTables endpoint.

Returns the shared cis StudentRegistrationSerializer shape, scoped to the
requesting HS admin's high schools + the `student` param. Mirrors the fixture
of cis/tests/test_registration_viewset_scoping.py.
"""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from rest_framework.test import APIClient

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.course import College, Department, Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.section import ClassSection, StudentRegistration
from cis.models.student import Student
from cis.models.term import AcademicYear, Term

User = get_user_model()
API_URL = '/highschool_admin/api/student-registrations/?format=datatables'


def _u(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


class StudentRegistrationsTableApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if _login_history_post_login is not None:
            user_logged_in.connect(_login_history_post_login)

    @classmethod
    def setUpTestData(cls):
        for name in ('ce', 'highschool_admin', 'student'):
            Group.objects.get_or_create(name=name)
        # StudentRegistration post_save -> Student.add_note() falls back to the
        # 'cron' user when no request user is present.
        User.objects.get_or_create(username='cron', defaults={'email': 'cron@example.com'})

        ay = AcademicYear.objects.create(name=_u('AY'))
        cls.term = Term.objects.create(academic_year=ay, code='F25', label=_u('Fall'))
        college = College.objects.create(name=_u('College'))
        dept = Department.objects.create(name=_u('Dept'), college=college)
        cohort = Cohort.objects.create(name=_u('Cohort'), designator='CO')
        course = Course.objects.create(
            catalog_number='101', title='Intro', department=dept,
            cohort=cohort, credit_hours=3)

        cls.hs_a = HighSchool.objects.create(name=_u('HS-A'))
        cls.hs_b = HighSchool.objects.create(name=_u('HS-B'))
        cls.student_a = cls._make_student(cls.hs_a, 'stud-a')
        cls.student_b = cls._make_student(cls.hs_b, 'stud-b')

        section_a = ClassSection.objects.create(
            class_number=_u('CN'), section_number='01',
            term=cls.term, course=course, highschool=cls.hs_a)
        section_b = ClassSection.objects.create(
            class_number=_u('CN'), section_number='02',
            term=cls.term, course=course, highschool=cls.hs_b)
        cls.reg_a = StudentRegistration.objects.create(
            student=cls.student_a, class_section=section_a, status_changed_on={})
        cls.reg_b = StudentRegistration.objects.create(
            student=cls.student_b, class_section=section_b, status_changed_on={})

        # HS admin bound to HS-A only.
        admin_user = User.objects.create_user(
            username=_u('admin'), email=f'{_u("admin")}@x.com', password='x')
        admin_user.groups.add(Group.objects.get(name='highschool_admin'))
        cls.admin_user = admin_user
        administrator = HSAdministrator.objects.create(user=admin_user)
        position = HSPosition.objects.create(name=_u('Pos'))
        HSAdministratorPosition.objects.create(
            hsadmin=administrator, highschool=cls.hs_a,
            position=position, status='Active')

        # A plain student user (wrong role) for the 403 check.
        cls.student_user = cls.student_a.user

    @classmethod
    def _make_student(cls, hs, tag):
        su = User.objects.create_user(
            username=_u(tag), email=f'{_u(tag)}@x.com', password='x',
            first_name='S', last_name=tag)
        su.groups.add(Group.objects.get(name='student'))
        return Student.objects.create(user=su, highschool=hs)

    def _client(self, user):
        # force_login (real session) rather than force_authenticate: cis's
        # LoginRequiredMiddleware checks request.user.is_authenticated on the
        # raw Django request before DRF's own authentication runs, and
        # force_authenticate only patches the user DRF sees, not the session.
        # Mirrors cis/tests/test_registration_viewset_scoping.py.
        c = APIClient()
        c.force_login(user)
        return c

    def test_in_scope_student_returns_their_registration(self):
        resp = self._client(self.admin_user).get(f'{API_URL}&student={self.student_a.id}')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.json()['data']]
        self.assertIn(str(self.reg_a.id), [str(i) for i in ids])

    def test_out_of_scope_student_returns_empty(self):
        # student_b is in HS-B; the admin only administers HS-A.
        resp = self._client(self.admin_user).get(f'{API_URL}&student={self.student_b.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_non_uuid_student_param_is_empty_not_500(self):
        resp = self._client(self.admin_user).get(f'{API_URL}&student=not-a-uuid')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_non_hsadmin_forbidden(self):
        resp = self._client(self.student_user).get(f'{API_URL}&student={self.student_a.id}')
        self.assertEqual(resp.status_code, 403)
