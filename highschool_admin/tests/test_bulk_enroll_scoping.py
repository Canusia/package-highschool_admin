"""End-to-end scoping for the high-school-admin bulk-enroll page: a HS admin
may only see their own sections, only enroll their own students, the page is
gated by the registration-open window, and confirm creates 'applied'
registrations."""
import csv
import io

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.course import Cohort, Course
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


class _NoLoginHistoryMixin:
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


def _open_registration(term):
    Setting.objects.update_or_create(
        key=f'{django_settings.CAMPUS_CODE_PREFIX}_cis_registrations',
        defaults={'value': {
            'starting_date': '01/01/2020',
            'ending_date': '12/31/2030',
            'active_term': str(term.id),
            'registration_terms': [str(term.id)],
        }},
    )


class BulkEnrollScopingTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ('student', 'highschool_admin'):
            Group.objects.get_or_create(name=name)
        User.objects.create_user(username='cron', email='cron@example.com', password='x')

        cls.mine = HighSchool.objects.create(name='Mine HS', code='111111')
        cls.other = HighSchool.objects.create(name='Other HS', code='222222')

        cls.user = User.objects.create_user(
            username='hsa@x.com', email='hsa@x.com', password='x')
        cls.user.groups.add(Group.objects.get(name='highschool_admin'))
        hsa = HSAdministrator.objects.create(user=cls.user)
        pos = HSPosition.objects.create(name='Primary Contact')
        HSAdministratorPosition.objects.create(
            hsadmin=hsa, highschool=cls.mine, position=pos, status='Active')

        ay = AcademicYear.objects.create(name='2025-2026')
        cls.term = Term.objects.create(academic_year=ay, code='FA25', label='Fall 2025')
        cohort = Cohort.objects.create(name='Default Cohort', designator='DC')
        course = Course.objects.create(
            name='ENG101', title='English 101', catalog_number='101',
            cohort=cohort, credit_hours=3)
        cls.my_section = ClassSection.objects.create(
            class_number='1001', section_number='A', term=cls.term,
            course=course, highschool=cls.mine)
        cls.other_section = ClassSection.objects.create(
            class_number='2002', section_number='B', term=cls.term,
            course=course, highschool=cls.other)

        cls.my_student = cls._student('in', cls.mine)
        cls.other_student = cls._student('out', cls.other)
        _open_registration(cls.term)

    @classmethod
    def _student(cls, tag, hs):
        user = User.objects.create_user(
            username=f'stu_{tag}', email=f'stu_{tag}@example.com', password='x',
            first_name=tag.title(), last_name='Student')
        return Student.objects.create(user=user, highschool=hs)

    def setUp(self):
        self.client = self.client_class(REMOTE_ADDR='127.0.0.1')
        self.client.force_login(self.user)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.user,
            defaults={'verification_code': '123456', 'verified': True})

    def _upload(self, emails, section_ids):
        csv_text = 'email\n' + '\n'.join(emails) + '\n'
        f = SimpleUploadedFile('e.csv', csv_text.encode(), content_type='text/csv')
        return self.client.post(
            reverse('highschool_admin:bulk_enroll'),
            {'term': str(self.term.id), 'sections': section_ids, 'file': f},
            follow=True)

    def test_section_picker_scoped_to_own_highschools(self):
        resp = self.client.get(
            reverse('highschool_admin:bulk_enroll'), {'term': str(self.term.id)})
        section_ids = {s.id for s in resp.context['sections']}
        self.assertIn(self.my_section.id, section_ids)
        self.assertNotIn(self.other_section.id, section_ids)

    def test_in_scope_email_parses_valid(self):
        resp = self._upload(['stu_in@example.com'], [str(self.my_section.id)])
        row = resp.context['batch'].rows.get(row_number=1)
        self.assertEqual(row.status, 'valid')

    def test_out_of_scope_student_is_error(self):
        resp = self._upload(['stu_out@example.com'], [str(self.my_section.id)])
        row = resp.context['batch'].rows.get(row_number=1)
        self.assertEqual(row.status, 'error')

    def test_confirm_creates_applied_registration(self):
        resp = self._upload(['stu_in@example.com'], [str(self.my_section.id)])
        batch = resp.context['batch']
        row = batch.rows.get(row_number=1)
        self.client.post(
            reverse('highschool_admin:bulk_enroll_confirm', args=[batch.id]),
            {'selected_rows': [str(row.id)]})
        reg = StudentRegistration.objects.get(
            student=self.my_student, class_section=self.my_section)
        self.assertEqual(reg.status, 'applied')

    def test_upload_blocked_when_registration_closed(self):
        Setting.objects.filter(
            key=f'{django_settings.CAMPUS_CODE_PREFIX}_cis_registrations').delete()
        resp = self._upload(['stu_in@example.com'], [str(self.my_section.id)])
        self.assertIsNone(resp.context.get('batch'))
        self.assertIn('error', resp.context)

    def test_report_download_is_csv(self):
        resp = self._upload(['stu_in@example.com'], [str(self.my_section.id)])
        batch = resp.context['batch']
        report = self.client.get(
            reverse('highschool_admin:bulk_enroll_report', args=[batch.id]))
        self.assertEqual(report['Content-Type'], 'text/csv')
        self.assertIn(b'Email', report.content)

    def test_malformed_term_param_does_not_500(self):
        # A non-UUID ?term= must be ignored (fall back to default term), not
        # raise ValidationError -> 500.
        resp = self.client.get(
            reverse('highschool_admin:bulk_enroll'), {'term': 'not-a-uuid'})
        self.assertEqual(resp.status_code, 200)

    def test_malformed_section_id_is_ignored_not_500(self):
        # A non-UUID section value must be filtered out, yielding the
        # "select a section" path (200, no batch), never a 500.
        f = SimpleUploadedFile(
            'e.csv', b'email\nstu_in@example.com\n', content_type='text/csv')
        resp = self.client.post(
            reverse('highschool_admin:bulk_enroll'),
            {'term': str(self.term.id), 'sections': ['not-a-uuid'], 'file': f},
            follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context.get('batch'))
