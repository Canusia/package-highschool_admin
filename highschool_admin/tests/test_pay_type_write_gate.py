"""Who may edit a registration's pay type is tenant policy.

The endpoint's only checks were the PT-18 scope guard and the global
`is_pay_type_review_open()` window. The rule that an HS admin may then edit
*any* registration at their schools, in *any* status, is a tenant decision --
several deployments restrict it to applied registrations or to the current
registration terms -- and there was no seam to express that.

Default is unchanged: allowed.
"""
from unittest.mock import MagicMock, patch

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

from ..services.registration import can_update_pay_type

User = get_user_model()


class CanUpdatePayTypeResolverTests(TestCase):
    def test_default_allows(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertTrue(can_update_pay_type(MagicMock(), MagicMock()))

    def test_tenant_override_can_deny(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda registration, user: False):
            self.assertFalse(can_update_pay_type(MagicMock(), MagicMock()))

    def test_override_receives_registration_and_user(self):
        seen = {}

        def override(registration, user):
            seen['registration'] = registration
            seen['user'] = user
            return True

        reg, user = MagicMock(), MagicMock()
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=override):
            can_update_pay_type(reg, user)
        self.assertIs(seen['registration'], reg)
        self.assertIs(seen['user'], user)

    def test_override_is_looked_up_under_an_hsadmin_scoped_name(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None) as gto:
            can_update_pay_type(MagicMock(), MagicMock())
        gto.assert_called_once_with(
            'registration', 'hsadmin_can_update_pay_type')


class PayTypeEndpointHonoursTheGateTests(TestCase):
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
        Group.objects.get_or_create(name='highschool_admin')
        Group.objects.get_or_create(name='student')
        User.objects.create_user(
            username='cron', email='cron@example.com', password='x')

        cls.hs = HighSchool.objects.create(name='HS Alpha')
        admin_user = User.objects.create_user(
            username='counselor', email='counselor@example.com', password='x',
            first_name='Coun', last_name='Selor')
        admin_user.groups.add(Group.objects.get(name='highschool_admin'))
        cls.admin_user = admin_user
        hsadmin = HSAdministrator.objects.create(user=admin_user)
        HSAdministratorPosition.objects.create(
            hsadmin=hsadmin, highschool=cls.hs,
            position=HSPosition.objects.create(name='Counselor'),
            status='Active')

        academic_year = AcademicYear.objects.create(name='2025-2026')
        term = Term.objects.create(
            academic_year=academic_year, code='FA25', label='Fall 2025')
        cohort = Cohort.objects.create(name='Default Cohort', designator='DC')
        course = Course.objects.create(
            name='ENG101', title='English 101', catalog_number='101',
            cohort=cohort, credit_hours=3)
        section = ClassSection.objects.create(
            class_number='1001', section_number='A', term=term, course=course,
            highschool=cls.hs)
        student_user = User.objects.create_user(
            username='stu', email='stu@example.com', password='x',
            first_name='Stu', last_name='Dent')
        student = Student.objects.create(user=student_user, highschool=cls.hs)
        cls.reg = StudentRegistration.objects.create(
            student=student, class_section=section, status_changed_on={})

    def _call(self):
        from ..views.registrations import update_registration_status
        req = RequestFactory().get('/', {
            'id': str(self.reg.id),
            'pay_type': 'school_partial',
            'non_student_pay_amount': '321',
        })
        req.user = self.admin_user
        return update_registration_status(req)

    def test_default_permits_the_edit_when_window_open(self):
        with patch('cis.utils.is_pay_type_review_open', return_value=True):
            resp = self._call()
        self.assertEqual(resp.status_code, 200)
        self.reg.refresh_from_db()
        self.assertEqual(self.reg.pay_type, 'school_partial')

    def test_denied_edit_is_403_and_leaves_the_record_untouched(self):
        original_pay_type = self.reg.pay_type
        original_amount = self.reg.non_student_pay_amount
        original_reviewer_id = self.reg.reviewer_id

        with patch('cis.utils.is_pay_type_review_open', return_value=True), \
             patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda registration, user: False):
            resp = self._call()

        self.assertEqual(resp.status_code, 403)
        self.reg.refresh_from_db()
        self.assertEqual(self.reg.pay_type, original_pay_type)
        self.assertNotEqual(self.reg.pay_type, 'school_partial')
        self.assertEqual(self.reg.non_student_pay_amount, original_amount)
        self.assertEqual(self.reg.reviewer_id, original_reviewer_id)

    def test_denial_does_not_depend_on_the_review_window(self):
        """A denied caller gets 403 whether or not the window is open, so the
        response does not leak window state and the gate cannot be bypassed by
        timing the request."""
        with patch('cis.utils.is_pay_type_review_open', return_value=False), \
             patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda registration, user: False):
            resp = self._call()
        self.assertEqual(resp.status_code, 403)
