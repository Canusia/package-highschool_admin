"""The high-school-admin student importer must only let an admin assign
students to high schools they administer (scope gate at parse and commit)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.highschool import HighSchool
from cis.models.student import Student
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from two_step.models import TwoStep

User = get_user_model()

HEADER = (
    'first_name,last_name,email,permanent_address_country,permanent_address,'
    'city,state,zip_code,preferred_phone,home_phone,cell_phone,legal_sex,'
    'date_of_birth,start_date,graduation_date,highschool_ceeb,same_as_permanent,'
    'mailing_address')


def _row(ceeb):
    return (
        'Ann,Lee,ann@example.com,US,1 Main St,Spokane,WA,99201,Mobile,'
        '5095551234,5095559999,f,05/14/2012,09/01/2026,06/01/2028,%s,true,' % ceeb)


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


class HSAdminImportScopingTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ('student', 'highschool_admin'):
            Group.objects.get_or_create(name=name)
        cls.mine = HighSchool.objects.create(name='Mine HS', code='111111')
        cls.other = HighSchool.objects.create(name='Other HS', code='222222')
        cls.user = User.objects.create_user(
            username='hsa@x.com', email='hsa@x.com', password='x')
        cls.user.groups.add(Group.objects.get(name='highschool_admin'))
        hsa = HSAdministrator.objects.create(user=cls.user)
        pos = HSPosition.objects.create(name='Primary Contact')
        HSAdministratorPosition.objects.create(
            hsadmin=hsa, highschool=cls.mine, position=pos, status='Active')

    def setUp(self):
        self.client = self.client_class(REMOTE_ADDR='127.0.0.1')
        self.client.force_login(self.user)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.user,
            defaults={'verification_code': '123456', 'verified': True})

    def _upload(self, ceeb):
        csv = '%s\n%s\n' % (HEADER, _row(ceeb))
        f = SimpleUploadedFile('r.csv', csv.encode(), content_type='text/csv')
        return self.client.post(
            reverse('highschool_admin:student_import'), {'file': f}, follow=True)

    def test_in_scope_ceeb_is_valid(self):
        resp = self._upload('111111')
        batch = resp.context['batch']
        self.assertEqual(batch.rows.get(row_number=1).status, 'valid')

    def test_out_of_scope_ceeb_is_error(self):
        resp = self._upload('222222')
        row = resp.context['batch'].rows.get(row_number=1)
        self.assertEqual(row.status, 'error')
        self.assertIn('highschool', row.errors)

    def test_confirm_only_creates_in_scope(self):
        resp = self._upload('111111')
        batch = resp.context['batch']
        row = batch.rows.get(row_number=1)
        self.client.post(
            reverse('highschool_admin:student_import_confirm', args=[batch.id]),
            {'selected_rows': [str(row.id)]})
        student = Student.objects.get(user__email='ann@example.com')
        self.assertEqual(student.highschool, self.mine)

    def test_commit_rejects_valid_row_with_out_of_scope_ceeb(self):
        # Simulate a tampered/stale batch: a row marked 'valid' whose CEEB is
        # for a school this admin does NOT administer. Commit-time re-validation
        # must reject it (no student created).
        from cis.models.student_import import StudentImportBatch, StudentImportRow
        from cis.models.student import Student
        batch = StudentImportBatch.objects.create(
            source_filename='x.csv', scope='highschool_admin', created_by=self.user)
        raw = dict(zip(HEADER.split(','), _row('222222').split(',')))  # 222222 = self.other
        row = StudentImportRow.objects.create(
            batch=batch, row_number=1, raw_data=raw, status='valid',
            errors={}, selected=True)
        before = Student.objects.count()
        self.client.post(
            reverse('highschool_admin:student_import_confirm', args=[batch.id]),
            {'selected_rows': [str(row.id)]})
        self.assertEqual(Student.objects.count(), before)  # nothing created
        row.refresh_from_db()
        self.assertTrue(row.result.startswith('Failed'))
