"""The college's prerequisite review, shown read-only to HS admins (#7).

Values come from the tenant's `prereq_tracking` service (RVCC's shape:
term-level transcript_received / test_score_needed, per-registration
prereq_met, plus a CE-internal `note`). Only the three flags may reach a high
school. A tenant without the service shows nothing.
"""
import types
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.section import ClassSection, StudentRegistration
from cis.models.term import AcademicYear, Term
from two_step.models import TwoStep

from . import PKG
from .test_student_detail_scoping import (
    _NoLoginHistoryMixin, _provision_groups, _provision_registration_setting,
    _provision_menu_setting, _make_student, _hs_admin_bound_to,
)

SECRET_NOTE = 'CE-ONLY-NOTE-do-not-show'


def fake_service():
    """A prereq_tracking stand-in reading RVCC's Student.meta layout."""
    module = types.ModuleType('prereq_tracking')

    def get_review(student, term):
        return ((student.meta or {}).get('prereq_tracking') or {}).get(str(term.id)) or {}

    def get_registration_review(student, term, registration):
        return (get_review(student, term).get('registrations') or {}).get(
            str(registration.id)) or {}

    module.get_review = get_review
    module.get_registration_review = get_registration_review
    module.test_score_display = lambda value: {'Either': 'ACT or Accuplacer'}.get(value, value or '')
    module.set_review = mock.Mock(side_effect=AssertionError('HS admin must never write'))
    module.set_flag = mock.Mock(side_effect=AssertionError('HS admin must never write'))
    return module


class PrereqReviewReadOnlyTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        _provision_registration_setting()
        _provision_menu_setting()
        get_user_model().objects.get_or_create(
            username='cron', defaults={'email': 'cron@example.com'})
        cls.hs = HighSchool.objects.create(name='HS Prereq')
        cls.student = _make_student(cls.hs, 'pr_stu')
        cls.admin = _hs_admin_bound_to('pr', cls.hs)

        ay = AcademicYear.objects.create(name='PR 2026-2027')
        cls.term = Term.objects.create(academic_year=ay, code='FA26', label='Fall 2026')
        cohort = Cohort.objects.create(name='PR Cohort', designator='PR')
        course = Course.objects.create(catalog_number='103', title='English', cohort=cohort)
        section = ClassSection.objects.create(
            class_number='PR-1', section_number='01', term=cls.term, course=course,
            highschool=cls.hs)
        cls.registration = StudentRegistration.objects.create(
            student=cls.student, class_section=section, status='registered',
            status_changed_on={})

        cls.student.meta = {**(cls.student.meta or {}), 'prereq_tracking': {
            str(cls.term.id): {
                'transcript_received': 'Yes', 'transcript_received_by': 'someone',
                'test_score_needed': 'Either',
                'registrations': {str(cls.registration.id): {
                    'prereq_met': 'No', 'note': SECRET_NOTE}},
            }}}
        cls.student.save()

    def setUp(self):
        self.client.force_login(self.admin)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.admin,
            defaults={'verification_code': '123456', 'verified': True})

    def _with_service(self):
        service = fake_service()
        patcher = mock.patch('cis.services.tenant_services.get_tenant_service',
                             return_value=service)
        patcher.start()
        self.addCleanup(patcher.stop)
        return service

    def _api(self):
        return self.client.get('/highschool_admin/api/registration/',
                               {'format': 'datatables', 'term': str(self.term.id)})

    def _student_page(self):
        return self.client.get(reverse('highschool_admin:student', args=[self.student.id]))

    # --- with the tenant service -------------------------------------------------

    def test_registration_rows_carry_the_three_flags(self):
        self._with_service()
        resp = self._api()
        row = resp.json()['data'][0]
        self.assertEqual(row['prereq_review'], {
            'transcript_received': 'Yes', 'prereq_met': 'No',
            'test_score_needed': 'ACT or Accuplacer'})
        self.assertNotIn(SECRET_NOTE, resp.content.decode())

    def test_students_page_shows_the_columns(self):
        self._with_service()
        html = self.client.get(reverse('highschool_admin:students')).content.decode()
        self.assertIn('Transcript Received', html)
        self.assertIn('data-prereq-review="1"', html)

    def test_student_page_shows_review_tab_without_the_note(self):
        self._with_service()
        html = self._student_page().content.decode()
        self.assertIn('href="#prereq_review"', html)
        self.assertIn('ACT or Accuplacer', html)
        self.assertNotIn(SECRET_NOTE, html)
        self.assertNotIn('transcript_received_by', html)

    def test_reading_never_writes(self):
        service = self._with_service()
        self._api()
        self._student_page()
        self.client.post(reverse('highschool_admin:student', args=[self.student.id]),
                         {'action': 'set_review', 'prereq_met': 'Yes'})
        service.set_review.assert_not_called()
        service.set_flag.assert_not_called()
        self.student.refresh_from_db()
        self.assertEqual(self.student.meta['prereq_tracking'][str(self.term.id)]
                         ['registrations'][str(self.registration.id)]['prereq_met'], 'No')

    # --- without it ---------------------------------------------------------------

    def test_tenant_without_the_service_shows_nothing(self):
        # ewu's tenant app has no prereq_tracking module.
        resp = self._api()
        self.assertIsNone(resp.json()['data'][0]['prereq_review'])
        self.assertNotIn('href="#prereq_review"', self._student_page().content.decode())
        html = self.client.get(reverse('highschool_admin:students')).content.decode()
        self.assertNotIn('Transcript Received', html)

    def test_breakage_inside_the_service_is_not_hidden(self):
        from django.conf import settings
        import importlib
        prereq = importlib.import_module(f'{PKG}.services.prereq_review')
        error = ModuleNotFoundError("No module named 'missing_dependency'",
                                    name='missing_dependency')
        with mock.patch('cis.services.tenant_services.get_tenant_service', side_effect=error), \
                self.settings(TENANT_SERVICES_APP=settings.TENANT_SERVICES_APP):
            with self.assertRaises(ModuleNotFoundError):
                prereq.tracking_service()
