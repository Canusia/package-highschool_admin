"""HS-admin student detail page: Supporting Documents tab (upload / delete).

The tab lets a school admin upload supporting documents for one of their own
students. Uploads/deletes are scoped to the URL's student (which the view
already restricts to the admin's high schools).
"""
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool
from cis.models.student import StudentSupportingDocument
from cis.models.term import Term, AcademicYear
from cis.storage_backend import PrivateMediaStorage
from two_step.models import TwoStep

from .test_student_detail_scoping import (
    _NoLoginHistoryMixin, _provision_groups, _provision_registration_setting,
    _provision_menu_setting, _make_student, _hs_admin_bound_to,
)


class SupportingDocTabTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        _provision_registration_setting()
        _provision_menu_setting()
        cls.hs_a = HighSchool.objects.create(name='HS Alpha SD')
        cls.hs_b = HighSchool.objects.create(name='HS Bravo SD')
        cls.student = _make_student(cls.hs_a, 'sd_in')
        cls.other_student = _make_student(cls.hs_b, 'sd_out')
        cls.admin = _hs_admin_bound_to('sd', cls.hs_a)
        ay = AcademicYear.objects.create(name='SD 2025-2026')
        cls.term = Term.objects.create(
            academic_year=ay, code='FA25', label='Fall 2025')

    def setUp(self):
        self.client.force_login(self.admin)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.admin,
            defaults={'verification_code': '123456', 'verified': True})

    def _url(self, student):
        return reverse('highschool_admin:student', args=[student.id])

    def test_tab_present_on_detail_page(self):
        html = self.client.get(self._url(self.student)).content.decode()
        self.assertIn('Supporting Documents', html)
        self.assertIn('id="support_docs"', html)

    @mock.patch.object(PrivateMediaStorage, 'save', return_value='docs/t.pdf')
    def test_upload_creates_doc_scoped_to_student(self, _save):
        f = SimpleUploadedFile('t.pdf', b'%PDF-1.4', content_type='application/pdf')
        resp = self.client.post(self._url(self.student), {
            'action': 'upload_support_doc',
            'student': str(self.student.id),
            'term': str(self.term.id),
            'document_type': '',
            'description': 'HS admin upload',
            'media': f,
        })
        self.assertEqual(resp.status_code, 302)
        docs = StudentSupportingDocument.objects.filter(student=self.student)
        self.assertEqual(docs.count(), 1)
        self.assertEqual(docs.first().description, 'HS admin upload')

    @mock.patch.object(PrivateMediaStorage, 'save', return_value='docs/t.pdf')
    def test_upload_forces_url_student_scope(self, _save):
        # Even if the hidden student field is tampered to a student at another
        # high school, the doc is saved against the URL's (scoped) student.
        f = SimpleUploadedFile('t.pdf', b'x', content_type='application/pdf')
        self.client.post(self._url(self.student), {
            'action': 'upload_support_doc',
            'student': str(self.other_student.id),   # tampered
            'term': str(self.term.id),
            'media': f,
        })
        self.assertEqual(
            StudentSupportingDocument.objects.filter(
                student=self.other_student).count(), 0)
        self.assertEqual(
            StudentSupportingDocument.objects.filter(
                student=self.student).count(), 1)

    def test_delete_removes_doc(self):
        doc = StudentSupportingDocument.objects.create(
            student=self.student, term=self.term, media='docs/d.pdf')
        resp = self.client.post(self._url(self.student), {
            'action': 'delete_support_doc', 'id': str(doc.id)})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            StudentSupportingDocument.objects.filter(id=doc.id).exists())

    def test_cannot_delete_other_students_doc(self):
        # A doc on a student outside the admin's scope isn't reachable: the
        # detail page for that student is 404, so the delete never runs.
        doc = StudentSupportingDocument.objects.create(
            student=self.other_student, term=self.term, media='docs/o.pdf')
        resp = self.client.post(self._url(self.other_student), {
            'action': 'delete_support_doc', 'id': str(doc.id)})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(
            StudentSupportingDocument.objects.filter(id=doc.id).exists())
