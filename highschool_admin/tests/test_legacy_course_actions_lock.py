"""The legacy `FutureSectionsActionViewSet` (routed at `course-actions`) is a
duplicate of the endpoints `future_sections` itself now guards with
`assert_editable`. It is not what the live `/highschool_admin/future_sections/`
page calls -- that page is served entirely by `future_sections`' own
`FutureSectionsPageView` and its own router (see
`myce/urls.py` -- `future_sections.urls.highschool_admin`) -- but this
viewset is still registered in `highschool_admin/urls.py` as `course-actions`
and reachable by any authenticated HS admin, or by stale cached JS pointing
at the old endpoints. `mark_teaching`/`mark_not_teaching`/
`remove_teaching_status` all call `FutureCourse.get_or_add` (or look one up)
and go on to mutate `section_info` -- an unguarded bypass of the review lock.

These tests hit the legacy routes directly and confirm a locked
`FutureCourse` is refused there too.
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

from . import PKG

User = get_user_model()


class LegacyCourseActionsLockTests(TestCase):
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

        course = Course.objects.create(
            name='ENG101', title='English 101', catalog_number='101',
            cohort=cohort, credit_hours=3)
        cls.certificate = TeacherCourseCertificate.objects.create(
            teacher_highschool=teacher_hs, course=course, status='Teaching')
        cls.future_course = FutureCourse.objects.create(
            teacher_course=cls.certificate, academic_year=cls.ay,
            status='pending_review')

    def setUp(self):
        self.client.force_login(self.user)

    def _get(self, url_name):
        # `_get_or_create_future_projection` (called by mark-teaching and
        # mark-not-teaching before they reach the lock check) resolves its
        # academic year from the tenant's `future_sections` Setting, not from
        # the request -- stub it to the fixture's academic year so the
        # unrelated (unconfigured-in-tests) tenant setting doesn't 500 first.
        with patch(f'{PKG}.views.api.viewsets._get_fs_config',
                   return_value={'academic_year': str(self.ay.id)}):
            return self.client.get(
                reverse(f'highschool_admin:{url_name}'),
                {
                    'course_certificate_id': str(self.certificate.certificate_id),
                    'academic_year_id': str(self.ay.id),
                })

    def test_mark_teaching_refuses_a_locked_request(self):
        resp = self._get('course-actions-mark-teaching')
        self.assertEqual(resp.status_code, 403)

    def test_mark_not_teaching_refuses_a_locked_request(self):
        resp = self._get('course-actions-mark-not-teaching')
        self.assertEqual(resp.status_code, 403)
        self.future_course.refresh_from_db()
        self.assertEqual(self.future_course.section_info, {})

    def test_remove_teaching_status_refuses_a_locked_request(self):
        with patch(
                f'{PKG}.views.api.viewsets.FutureCourse.is_window_open',
                return_value=True):
            resp = self._get('course-actions-remove-teaching-status')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            FutureCourse.objects.filter(pk=self.future_course.pk).exists())

    def test_mark_not_teaching_still_works_when_not_locked(self):
        self.future_course.status = 'submitted'
        self.future_course.save()
        resp = self._get('course-actions-mark-not-teaching')
        self.assertEqual(resp.status_code, 200)
