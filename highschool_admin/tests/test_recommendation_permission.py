"""Enforcement of the ``manage_student_recommendation`` permission.

Before this, the only check in the portal was commented out, in a dead
``views/home.py`` copy of the student view (since deleted), so any hsadmin could
post a recommendation and approve/deny registrations for any student at any of
their high schools. Three things are pinned here:

  * the permission is keyed to the STUDENT's high school, not the section's
    host high school -- those differ when a student takes a section hosted
    elsewhere
  * the POST is refused whole, before any write; a per-registration gate would
    still let the StudentRecommendation record itself save
  * pending-recommendation lists are scoped to the schools where the admin
    actually holds the permission, not every school they hold a position at
"""
import uuid

from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.section import ClassSection, StudentRegistration
from cis.models.settings import Setting
from cis.models.student import Student, StudentRecommendation
from cis.models.term import AcademicYear, Term

from .test_student_detail_tabs import (
    _login, _provision_groups, _provision_menu,
)

User = get_user_model()


def _u(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


class _Fixture(TestCase):
    """Two high schools, one admin, one rec-eligible student at HS A."""

    def setUp(self):
        _provision_groups()
        _provision_menu()
        User.objects.get_or_create(
            username='cron', defaults={'email': 'cron@example.com'})

        self.hs_a = HighSchool.objects.create(name=_u('HS-A'))
        self.hs_b = HighSchool.objects.create(name=_u('HS-B'))

        self.user = User.objects.create(
            email=f'{_u("admin")}@x.com', username=_u('admin'))
        self.user.groups.add(
            Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        self.position = HSPosition.objects.create(name=_u('Pos'))

        ay = AcademicYear.objects.create(name=_u('AY'))
        self.term = Term.objects.create(
            academic_year=ay, code='F25', label=_u('Fall'))
        cohort = Cohort.objects.create(name=_u('Cohort'), designator='CO')
        self.course = Course.objects.create(
            catalog_number='101', title='Intro', name=_u('COURSE'),
            cohort=cohort, credit_hours=3,
            registration_eligibility=['FR*'],
        )
        # Section hosted at HS B while the student attends HS A -- the case
        # the old class_section__highschool check got wrong.
        self.section = ClassSection.objects.create(
            term=self.term, course=self.course,
            class_number=_u('CN'), section_number='01',
            highschool=self.hs_b,
        )

        su = User.objects.create(email=f'{_u("stu")}@x.com', username=_u('stu'))
        self.student = Student.objects.create(
            user=su, highschool=self.hs_a, grade_level='FR')
        self.registration = StudentRegistration.objects.create(
            student=self.student, class_section=self.section,
            status='applied', status_changed_on={},
        )

        Setting.objects.update_or_create(
            key=f'{dj_settings.CAMPUS_CODE_PREFIX}_cis_registrations',
            defaults={'value': {'registration_terms': [str(self.term.id)]}},
        )

    def _position(self, highschool, can_recommend):
        return HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=highschool,
            position=self.position, status='Active',
            meta={'manage_student_recommendation': 'Yes' if can_recommend else 'No'},
        )

    def _url(self):
        return reverse('highschool_admin:student', args=[self.student.id])

    def _post_data(self):
        return {
            'student': str(self.student.id),
            'student_grade_level': self.student.grade_level,
            'student_gpa': '3.5',
            'student_prereq': 'Yes',
            'school_assessment': 'Proficient',
            'keystone_exam': 'Proficient',
            'geip': 'No',
            'enrolled_in_honors': 'No',
            f'registration_{self.registration.id}': 'approved',
            'submit_recommendation': 'Submit Recommendation',
        }


class CanManageStudentRecommendationTests(_Fixture):

    def test_yes_grants(self):
        self._position(self.hs_a, True)
        self.assertTrue(
            self.admin.can_manage_student_recommendation(self.hs_a.id))

    def test_no_denies(self):
        self._position(self.hs_a, False)
        self.assertFalse(
            self.admin.can_manage_student_recommendation(self.hs_a.id))

    def test_missing_meta_key_denies(self):
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs_a,
            position=self.position, status='Active', meta={},
        )
        self.assertFalse(
            self.admin.can_manage_student_recommendation(self.hs_a.id))

    def test_inactive_position_denies(self):
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs_a,
            position=self.position, status='Inactive',
            meta={'manage_student_recommendation': 'Yes'},
        )
        self.assertFalse(
            self.admin.can_manage_student_recommendation(self.hs_a.id))

    def test_permission_at_another_highschool_does_not_carry(self):
        self._position(self.hs_b, True)
        self.assertFalse(
            self.admin.can_manage_student_recommendation(self.hs_a.id))

    def test_falsy_highschool_id_denies(self):
        self._position(self.hs_a, True)
        self.assertFalse(self.admin.can_manage_student_recommendation(None))
        self.assertFalse(self.admin.can_manage_student_recommendation(''))


class GetRecommendationHighschoolsTests(_Fixture):

    def test_lists_only_permitted_schools(self):
        self._position(self.hs_a, True)
        self._position(self.hs_b, False)

        names = set(
            self.admin.get_recommendation_highschools().values_list('name', flat=True))

        self.assertEqual(names, {self.hs_a.name})

    def test_is_narrower_than_get_highschools(self):
        self._position(self.hs_a, True)
        self._position(self.hs_b, False)

        self.assertEqual(self.admin.get_highschools().count(), 2)
        self.assertEqual(self.admin.get_recommendation_highschools().count(), 1)


class StudentViewRecommendationGateTests(_Fixture):

    def test_post_is_refused_without_permission(self):
        self._position(self.hs_a, False)
        c = _login(self.user)

        resp = c.post(self._url(), self._post_data())

        self.assertEqual(resp.status_code, 302)
        # Nothing was written: no recommendation record, status unchanged.
        self.assertFalse(
            StudentRecommendation.objects.filter(student=self.student).exists())
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'applied')
        self.assertIsNone(self.registration.reviewer_id)

    def test_post_succeeds_with_permission(self):
        self._position(self.hs_a, True)
        c = _login(self.user)

        resp = c.post(self._url(), self._post_data())

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            StudentRecommendation.objects.filter(student=self.student).exists())
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'approved')

    def test_permission_follows_the_student_not_the_section_host(self):
        """The student attends HS A; the section is hosted at HS B.

        Permission at HS B alone must not let the admin recommend -- the old
        check keyed off class_section.highschool and would have allowed it.
        """
        self._position(self.hs_a, False)
        self._position(self.hs_b, True)
        c = _login(self.user)

        resp = c.post(self._url(), self._post_data())

        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            StudentRecommendation.objects.filter(student=self.student).exists())
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'applied')

    def test_template_hides_the_controls_without_permission(self):
        self._position(self.hs_a, False)
        c = _login(self.user)

        resp = c.get(self._url())

        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, f'name="registration_{self.registration.id}"')
        self.assertNotContains(resp, 'id="btn_submit_recommendation"')
        self.assertContains(resp, 'You do not have permission to submit recommendations')

    def test_template_shows_the_controls_with_permission(self):
        self._position(self.hs_a, True)
        c = _login(self.user)

        resp = c.get(self._url())

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f'name="registration_{self.registration.id}"')
        self.assertContains(resp, 'id="btn_submit_recommendation"')


class PendingRecommendationScopingTests(_Fixture):

    def test_pending_list_is_scoped_to_permitted_schools(self):
        self._position(self.hs_a, False)
        self._position(self.hs_b, True)

        # Scoped by the student's high school (HS A), where the admin has no
        # recommendation permission -- so nothing is listed.
        permitted = self.admin.get_recommendation_highschools()
        records = StudentRegistration.get_pending_recommendations(
            highschool_ids=[hs.id for hs in permitted])

        self.assertEqual(records.count(), 0)

    def test_pending_list_includes_permitted_students(self):
        self._position(self.hs_a, True)

        permitted = self.admin.get_recommendation_highschools()
        records = StudentRegistration.get_pending_recommendations(
            highschool_ids=[hs.id for hs in permitted])

        self.assertEqual(
            list(records.values_list('id', flat=True)), [self.registration.id])
