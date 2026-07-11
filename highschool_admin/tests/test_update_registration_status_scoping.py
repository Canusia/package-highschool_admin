"""PT-18: /highschool_admin/update_registration_status/ must only edit
registrations whose student belongs to the caller's administered high schools.

Calls the view directly via RequestFactory (no middleware), mirroring the
shape of the vulnerable endpoint. Out-of-scope or missing/malformed ids must
get a 403 with no mutation; in-scope ids must pass the ownership check.
"""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase, RequestFactory

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.term import AcademicYear, Term
from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.section import ClassSection, StudentRegistration
from cis.models.student import Student
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)

User = get_user_model()


class UpdateRegistrationStatusScopingTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # django_login_history's post_login signal handler raises in tests
        # (no usable request IP). Disconnect for the duration of this case.
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
        Group.objects.get_or_create(name='highschool_admin')
        Group.objects.get_or_create(name='student')

        # Creating a StudentRegistration fires a post_save signal that adds a
        # note attributed to the 'cron' user when there is no current request.
        User.objects.create_user(
            username='cron', email='cron@example.com', password='x',
        )

        # Two high schools: the attacker administers hs_a, not hs_b.
        cls.hs_a = HighSchool.objects.create(name='HS Alpha')
        cls.hs_b = HighSchool.objects.create(name='HS Beta')

        # Attacker: a highschool_admin bound to hs_a only via an Active position.
        attacker_user = User.objects.create_user(
            username='attacker', email='attacker@example.com', password='x',
            first_name='Att', last_name='Acker',
        )
        attacker_user.groups.add(Group.objects.get(name='highschool_admin'))
        cls.attacker = attacker_user
        cls.hsadmin = HSAdministrator.objects.create(user=attacker_user)
        position = HSPosition.objects.create(name='Counselor')
        HSAdministratorPosition.objects.create(
            hsadmin=cls.hsadmin, highschool=cls.hs_a, position=position,
            status='Active',
        )

        # Minimal class-section graph (shared by both registrations).
        academic_year = AcademicYear.objects.create(name='2025-2026')
        term = Term.objects.create(
            academic_year=academic_year, code='FA25', label='Fall 2025',
        )
        cohort = Cohort.objects.create(name='Default Cohort', designator='DC')
        course = Course.objects.create(
            name='ENG101', title='English 101', catalog_number='101',
            cohort=cohort, credit_hours=3,
        )
        section_a = ClassSection.objects.create(
            class_number='1001', section_number='A', term=term, course=course,
            highschool=cls.hs_a,
        )
        section_b = ClassSection.objects.create(
            class_number='2002', section_number='B', term=term, course=course,
            highschool=cls.hs_b,
        )

        # A student + registration at each school.
        in_student = cls._make_student('in', cls.hs_a)
        out_student = cls._make_student('out', cls.hs_b)
        cls.in_reg = StudentRegistration.objects.create(
            student=in_student, class_section=section_a, status_changed_on={},
        )
        cls.out_reg = StudentRegistration.objects.create(
            student=out_student, class_section=section_b, status_changed_on={},
        )

    @classmethod
    def _make_student(cls, tag, highschool):
        user = User.objects.create_user(
            username=f'stu_{tag}', email=f'stu_{tag}@example.com', password='x',
            first_name=tag.title(), last_name='Student',
        )
        return Student.objects.create(user=user, highschool=highschool)

    def _call(self, user, reg_id):
        from ..views.registrations import update_registration_status
        req = RequestFactory().get('/', {
            'id': str(reg_id),
            'pay_type': 'school_partial',
            'non_student_pay_amount': '321',
        })
        req.user = user
        return update_registration_status(req)

    def test_out_of_scope_registration_is_forbidden_and_unchanged(self):
        original_pay_type = self.out_reg.pay_type
        original_amount = self.out_reg.non_student_pay_amount
        original_reviewer_id = self.out_reg.reviewer_id

        resp = self._call(self.attacker, self.out_reg.id)
        self.assertEqual(resp.status_code, 403)

        self.out_reg.refresh_from_db()
        self.assertEqual(self.out_reg.pay_type, original_pay_type)
        self.assertNotEqual(self.out_reg.pay_type, 'school_partial')
        self.assertEqual(self.out_reg.non_student_pay_amount, original_amount)
        self.assertEqual(self.out_reg.reviewer_id, original_reviewer_id)

    def test_missing_or_malformed_id_is_forbidden(self):
        # Unknown UUID and a non-UUID id both deny by default (403).
        self.assertEqual(self._call(self.attacker, uuid.uuid4()).status_code, 403)
        self.assertEqual(self._call(self.attacker, 'not-a-uuid').status_code, 403)

    def test_in_scope_registration_is_not_forbidden(self):
        # In-scope passes the ownership check. With the review window closed
        # (default in tests — no Setting fixture) the view returns 401, not
        # 403; the point is that the scope guard does not block it.
        resp = self._call(self.attacker, self.in_reg.id)
        self.assertNotEqual(resp.status_code, 403)
