"""Bulk per-student document upload for a term (#6).

A second entry point to cis's StudentSupportingDocumentForm: pick a term and a
document type, then attach a file per student on one page. Every upload is
scoped server-side to the admin's own high schools.
"""
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cis.forms.student import StudentSupportingDocumentForm
from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.section import ClassSection, StudentRegistration
from cis.models.student import StudentSupportingDocument
from cis.models.term import AcademicYear, Term
from cis.storage_backend import PrivateMediaStorage
from two_step.models import TwoStep

from .test_student_detail_scoping import (
    _NoLoginHistoryMixin, _provision_groups, _provision_registration_setting,
    _provision_menu_setting, _make_student, _hs_admin_bound_to,
)

TYPES = ['Transcript', 'ACT score report']


# The form owns the vocabulary; the view reads it from the same staticmethod.
@mock.patch.object(StudentSupportingDocumentForm, '_document_type_labels',
                   staticmethod(lambda term: TYPES))
class BulkStudentDocumentsTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        _provision_registration_setting()
        _provision_menu_setting()
        from django.contrib.auth import get_user_model
        get_user_model().objects.get_or_create(  # registration signals note as 'cron'
            username='cron', defaults={'email': 'cron@example.com'})
        cls.hs_a = HighSchool.objects.create(name='HS Alpha BD')
        cls.hs_b = HighSchool.objects.create(name='HS Bravo BD')
        cls.registered = _make_student(cls.hs_a, 'bd_reg')
        cls.unregistered = _make_student(cls.hs_a, 'bd_unreg')
        cls.other_school = _make_student(cls.hs_b, 'bd_other')
        cls.admin = _hs_admin_bound_to('bd', cls.hs_a)

        ay = AcademicYear.objects.create(name='BD 2026-2027')
        cls.term = Term.objects.create(academic_year=ay, code='FA26', label='Fall 2026')
        cohort = Cohort.objects.create(name='BD Cohort', designator='BD')
        course = Course.objects.create(catalog_number='101', title='BD', cohort=cohort)
        section = ClassSection.objects.create(
            class_number='BD-1', section_number='01', term=cls.term, course=course,
            highschool=cls.hs_a)
        for student in (cls.registered, cls.other_school):
            StudentRegistration.objects.create(
                student=student, class_section=section, status='registered',
                status_changed_on={})

    def setUp(self):
        self.client.force_login(self.admin)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.admin,
            defaults={'verification_code': '123456', 'verified': True})

    def _page(self, **params):
        return self.client.get(reverse('highschool_admin:student_documents'),
                               {'term': str(self.term.id), **params})

    def _upload(self, student, **extra):
        data = {
            'student': str(student.id), 'term': str(self.term.id),
            'document_type': 'Transcript', 'description': 'bulk',
            'media': SimpleUploadedFile('t.pdf', b'%PDF-1.4', content_type='application/pdf'),
            **extra,
        }
        with mock.patch.object(PrivateMediaStorage, 'save', return_value='docs/t.pdf'):
            return self.client.post(reverse('highschool_admin:upload_student_document'), data)

    def test_page_lists_own_students_registered_this_term(self):
        html = self._page().content.decode()
        self.assertIn(str(self.registered.id), html)
        self.assertNotIn(str(self.unregistered.id), html)
        self.assertNotIn(str(self.other_school.id), html)  # registered, but not our school
        self.assertIn('ACT score report', html)

    def test_all_toggle_adds_unregistered_own_students_only(self):
        html = self._page(all='1').content.decode()
        self.assertIn(str(self.unregistered.id), html)
        self.assertNotIn(str(self.other_school.id), html)

    def test_upload_stores_a_document_for_the_term(self):
        resp = self._upload(self.registered)
        self.assertEqual(resp.status_code, 200, resp.content)
        doc = StudentSupportingDocument.objects.get(student=self.registered)
        self.assertEqual((doc.term_id, doc.document_type, doc.description, doc.status),
                         (self.term.id, 'Transcript', 'bulk', ''))

    def test_student_at_another_school_is_refused(self):
        resp = self._upload(self.other_school)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(StudentSupportingDocument.objects.exists())

    def test_type_outside_vocabulary_is_refused(self):
        resp = self._upload(self.registered, document_type='Made up')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(StudentSupportingDocument.objects.exists())

    def test_missing_file_is_refused(self):
        resp = self._upload(self.registered, media='')
        self.assertEqual(resp.status_code, 400)

    def test_malformed_student_id_is_404(self):
        resp = self.client.post(reverse('highschool_admin:upload_student_document'),
                                {'student': 'not-a-uuid', 'term': str(self.term.id)})
        self.assertEqual(resp.status_code, 404)

    def test_upload_requires_post(self):
        resp = self.client.get(reverse('highschool_admin:upload_student_document'))
        self.assertEqual(resp.status_code, 405)

    def test_existing_documents_are_shown(self):
        self._upload(self.registered)
        html = self._page().content.decode()
        self.assertIn('Transcript: t.pdf', html)

    def test_pages_cross_link(self):
        url = reverse('highschool_admin:student_documents')
        self.assertIn(url, self.client.get(reverse('highschool_admin:transcripts')).content.decode())
        self.assertIn(url, self.client.get(reverse('highschool_admin:students')).content.decode())

    def test_other_roles_refused(self):
        self.client.force_login(self.registered.user)
        resp = self.client.get(reverse('highschool_admin:student_documents'))
        self.assertIn(resp.status_code, (302, 403))
