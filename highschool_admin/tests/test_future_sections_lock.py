"""The school-facing course-requests payload must surface the review lock.

Once CE marks a request `pending_review` (or `reviewed`), the high school
administrator's UI must stop offering Edit/Delete on that row -- the server
already refuses the write (`future_sections.utils.assert_editable`), this
just makes the UI agree so a locked row does not offer a button that only
403s.

The endpoint under test is `CourseRequestViewSet.list()`
(`highschool_admin/views/api/viewsets.py`), reverse-resolved as
`highschool_admin:course-requests-list` -- confirmed via
`reverse('highschool_admin:course-requests-list')` ==
'/highschool_admin/api/course-requests/', not hardcoded.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from django.urls import reverse

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.term import AcademicYear
from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.teacher import Teacher, TeacherHighSchool, TeacherCourseCertificate
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)

import importlib.util
if importlib.util.find_spec('future_sections.future_sections'):
    from future_sections.future_sections.models import FutureCourse
else:
    from future_sections.models import FutureCourse

User = get_user_model()


class CourseRequestLockPayloadTests(TestCase):
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
        Group.objects.get_or_create(name='instructor')

        cls.hs = HighSchool.objects.create(name='HS Alpha')

        cls.user = User.objects.create_user(
            username='counselor', email='counselor@example.com', password='x',
            first_name='Coun', last_name='Selor')
        cls.user.groups.add(Group.objects.get(name='highschool_admin'))
        hsadmin = HSAdministrator.objects.create(user=cls.user)
        HSAdministratorPosition.objects.create(
            hsadmin=hsadmin, highschool=cls.hs,
            position=HSPosition.objects.create(name='Counselor'),
            status='Active')

        cls.ay = AcademicYear.objects.create(name='2025-2026')

        cohort = Cohort.objects.create(name='Default Cohort', designator='DC')

        teacher_user = User.objects.create_user(
            username='teach', email='teach@example.com', password='x',
            first_name='Tea', last_name='Cher')
        teacher = Teacher.objects.create(user=teacher_user)
        teacher_hs = TeacherHighSchool.objects.create(
            teacher=teacher, highschool=cls.hs)

        # A course/certificate carrying a FutureCourse marked pending_review.
        locked_course = Course.objects.create(
            name='ENG101', title='English 101', catalog_number='101',
            cohort=cohort, credit_hours=3)
        cls.certificate = TeacherCourseCertificate.objects.create(
            teacher_highschool=teacher_hs, course=locked_course,
            status='Teaching')
        FutureCourse.objects.create(
            teacher_course=cls.certificate, academic_year=cls.ay,
            status='pending_review')

        # A course/certificate whose FutureCourse is still submitted.
        submitted_course = Course.objects.create(
            name='MTH101', title='Math 101', catalog_number='102',
            cohort=cohort, credit_hours=3)
        cls.submitted_certificate = TeacherCourseCertificate.objects.create(
            teacher_highschool=teacher_hs, course=submitted_course,
            status='Teaching')
        FutureCourse.objects.create(
            teacher_course=cls.submitted_certificate, academic_year=cls.ay,
            status='submitted')

        # A certificate with no FutureCourse request at all yet.
        bare_course = Course.objects.create(
            name='HIS101', title='History 101', catalog_number='103',
            cohort=cohort, credit_hours=3)
        cls.bare_certificate = TeacherCourseCertificate.objects.create(
            teacher_highschool=teacher_hs, course=bare_course,
            status='Teaching')

    def _payload_row_for(self, certificate):
        self.client.force_login(self.user)
        fs_config = {
            'academic_year': str(self.ay.id),
            'course_status': ['Active'],
            'teacher_course_status': ['Teaching'],
        }
        with patch('cis.settings.future_sections.future_sections.from_db',
                   return_value=fs_config):
            resp = self.client.get(
                reverse('highschool_admin:course-requests-list'),
                {'academic_year_id': str(self.ay.id)})
        self.assertEqual(resp.status_code, 200)
        rows = {r['certificate_id']: r for r in resp.json()}
        return rows[str(certificate.certificate_id)]

    def test_payload_reports_the_review_status(self):
        row = self._payload_row_for(self.certificate)
        self.assertEqual(row['review_status'], 'pending_review')
        self.assertTrue(row['is_locked'])

    def test_a_submitted_request_is_not_locked(self):
        row = self._payload_row_for(self.submitted_certificate)
        self.assertEqual(row['review_status'], 'submitted')
        self.assertFalse(row['is_locked'])

    def test_a_certificate_with_no_request_is_not_locked(self):
        row = self._payload_row_for(self.bare_certificate)
        self.assertIsNone(row['review_status'])
        self.assertFalse(row['is_locked'])
