"""The students list page's No Classes tab (#16).

/highschool_admin/api/students-without-classes/ lists students linked to the
admin's high school(s) who have never had a class registration -- in any
term or status -- and whose accounts are active, ordered by name. The tab
is shown unless the student_tabs setting hides it.
"""
import json
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from django.urls import reverse
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
from cis.models.settings import Setting
from cis.models.student import Student
from cis.models.term import AcademicYear, Term
from two_step.models import TwoStep

User = get_user_model()
API_URL = '/highschool_admin/api/students-without-classes/?format=datatables'
TAB_KEY = 'highschool_admin.settings.student_tabs'


def _u(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


class StudentsWithoutClassesTests(TestCase):
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
        User.objects.get_or_create(username='cron', defaults={'email': 'cron@example.com'})

        ay = AcademicYear.objects.create(name=_u('AY'))
        past_term = Term.objects.create(academic_year=ay, code='F19', label=_u('Fall'))
        college = College.objects.create(name=_u('College'))
        dept = Department.objects.create(name=_u('Dept'), college=college)
        cohort = Cohort.objects.create(name=_u('Cohort'), designator='CO')
        course = Course.objects.create(
            catalog_number='101', title='Intro', department=dept,
            cohort=cohort, credit_hours=3)

        cls.hs_a = HighSchool.objects.create(name=_u('HS-A'))
        cls.hs_b = HighSchool.objects.create(name=_u('HS-B'))
        cls.zed = cls._student(cls.hs_a, 'Zed')
        cls.amy = cls._student(cls.hs_a, 'Amy')
        cls.inactive = cls._student(cls.hs_a, 'Inactive', active=False)
        cls.cancelled_once = cls._student(cls.hs_a, 'Cancelled')
        cls.other_school = cls._student(cls.hs_b, 'Other')

        section = ClassSection.objects.create(
            class_number=_u('CN'), section_number='01',
            term=past_term, course=course, highschool=cls.hs_a)
        StudentRegistration.objects.create(
            student=cls.cancelled_once, class_section=section,
            status='cancelled', status_changed_on={})

        cls.admin_user = User.objects.create_user(
            username=_u('admin'), email=f'{_u("admin")}@x.com', password='x')
        cls.admin_user.groups.add(Group.objects.get(name='highschool_admin'))
        administrator = HSAdministrator.objects.create(user=cls.admin_user)
        HSAdministratorPosition.objects.create(
            hsadmin=administrator, highschool=cls.hs_a,
            position=HSPosition.objects.create(name=_u('Pos')), status='Active')

    @classmethod
    def _student(cls, hs, last_name, active=True):
        user = User.objects.create_user(
            username=_u(last_name), email=f'{_u(last_name)}@x.com', password='x',
            first_name='S', last_name=last_name, is_active=active)
        user.groups.add(Group.objects.get(name='student'))
        return Student.objects.create(user=user, highschool=hs)

    def _get(self, user):
        client = APIClient()
        client.force_login(user)
        return client.get(API_URL)

    def test_lists_only_never_registered_active_students_at_own_schools(self):
        response = self._get(self.admin_user)
        self.assertEqual(response.status_code, 200)
        ids = [row['id'] for row in response.json()['data']]
        # Ordered by last name; a cancelled past registration still counts,
        # inactive accounts and other schools' students never appear.
        self.assertEqual(ids, [str(self.amy.id), str(self.zed.id)])

    def test_rows_link_to_the_student_profile(self):
        row = self._get(self.admin_user).json()['data'][0]
        self.assertEqual(row['details'], reverse(
            'highschool_admin:student', kwargs={'record_id': self.amy.id}))
        self.assertEqual(row['highschool'], self.hs_a.name)

    def test_other_roles_are_refused(self):
        response = self._get(self.zed.user)
        self.assertIn(response.status_code, (302, 403))

    def _page(self):
        Setting.objects.get_or_create(
            key='cis.settings.menu',
            defaults={'value': {'highschool_admin_menu': json.dumps([
                {'type': 'nav-item', 'name': 'students', 'label': 'Students',
                 'url': 'highschool_admin:students'},
            ])}})
        client = APIClient()
        client.force_login(self.admin_user)
        TwoStep.objects.update_or_create(
            session_id=client.session.session_key, user=self.admin_user,
            defaults={'verification_code': '123456', 'verified': True})
        return client.get(reverse('highschool_admin:students'))

    def test_page_shows_the_tab_by_default(self):
        response = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="#no_classes"')
        self.assertContains(response, 'id="tbl_no_classes"')

    def test_setting_can_hide_the_tab(self):
        Setting.objects.update_or_create(key=TAB_KEY, defaults={'value': {
            'show_recommendation': True, 'show_review': True,
            'show_pay_type': True, 'show_no_classes': False}})
        response = self._page()
        self.assertNotContains(response, 'href="#no_classes"')
        self.assertNotContains(response, 'id="tbl_no_classes"')
