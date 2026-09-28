"""#15: HS admins upload files on the Transcripts page and see review status.

Depends on package-cis #56 (HighSchoolTranscript.term / reviewed_*, the shared
HSTranscriptUploadForm rules, notify_hs_upload). The high school is checked on
the server against the admin's own schools; a file can be deleted only by its
uploader and only before CE reviews it.
"""
import importlib
import json
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool, HighSchoolTranscript
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting
from cis.models.term import AcademicYear, Term
from two_step.models import TwoStep

# The module, not views.transcripts (views/__init__ exports a function of that
# name). Resolved relative to this package so it works nested and installed.
transcripts_view = importlib.import_module(
    __package__.rsplit('.', 1)[0] + '.views.transcripts')

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

User = get_user_model()


def _sfx():
    return uuid.uuid4().hex[:8]


def _hs_admin(*highschools):
    user = User.objects.create_user(
        username=f'hsa_{_sfx()}', email=f'hsa_{_sfx()}@example.com',
        password='x', first_name='Hal', last_name='Admin')
    user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
    hsadmin = HSAdministrator.objects.create(user=user)
    position = HSPosition.objects.create(name=f'Pos-{_sfx()}')
    for hs in highschools:
        HSAdministratorPosition.objects.create(
            hsadmin=hsadmin, highschool=hs, position=position, status='Active')
    return user


class _Base(TestCase):
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

    def setUp(self):
        for target in ('_save', 'delete'):
            patcher = mock.patch(
                f'cis.storage_backend.PrivateMediaStorage.{target}',
                side_effect=(lambda name, content: name) if target == '_save' else None)
            patcher.start()
            self.addCleanup(patcher.stop)
        notify = mock.patch.object(
            transcripts_view, 'notify_hs_upload', return_value=[])
        self.notify = notify.start()
        self.addCleanup(notify.stop)

        self.hs_a = HighSchool.objects.create(name=f'Auburn {_sfx()}')
        self.hs_b = HighSchool.objects.create(name=f'Bristol {_sfx()}')
        ay = AcademicYear.objects.create(name=f'AY{_sfx()}')
        self.term = Term.objects.create(academic_year=ay, code=f'F{_sfx()}', label='Fall')
        terms = mock.patch('cis.forms.highschool.upload_terms',
                           return_value=Term.objects.filter(pk=self.term.pk))
        terms.start()
        self.addCleanup(terms.stop)

        self.admin = _hs_admin(self.hs_a)
        self.login(self.admin)

    def login(self, user):
        self.client.force_login(user)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=user,
            defaults={'verification_code': '123456', 'verified': True})

    def post_upload(self, highschool, name='building.pdf', **extra):
        data = {
            'highschool': str(highschool.id), 'term': str(self.term.id),
            'description': 'All fall dual credit students',
            'media': SimpleUploadedFile(name, b'%PDF data'),
        }
        data.update(extra)
        return self.client.post(reverse('highschool_admin:upload_transcript'), data)

    def upload(self, highschool, by):
        return HighSchoolTranscript.objects.create(
            highschool=highschool, term=self.term, uploaded_by=by,
            description='x', media=SimpleUploadedFile('a.pdf', b'x'))


class UploadTests(_Base):
    def test_upload_to_own_school(self):
        resp = self.post_upload(self.hs_a)
        self.assertEqual(resp.status_code, 200, resp.content)
        record = HighSchoolTranscript.objects.get()
        self.assertEqual(record.highschool, self.hs_a)
        self.assertEqual(record.uploaded_by, self.admin)
        self.assertEqual(record.term, self.term)
        self.notify.assert_called_once_with(record)

    def test_other_school_is_rejected_and_nothing_saved(self):
        resp = self.post_upload(self.hs_b)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('highschool', json.loads(resp.content)['errors'])
        self.assertFalse(HighSchoolTranscript.objects.exists())
        self.notify.assert_not_called()

    def test_disallowed_type_shows_the_form_error(self):
        resp = self.post_upload(self.hs_a, name='macro.exe')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('media', json.loads(resp.content)['errors'])
        self.assertFalse(HighSchoolTranscript.objects.exists())

    def test_oversized_file_shows_the_form_error(self):
        from cis.settings.hs_uploads import hs_uploads
        Setting.objects.update_or_create(
            key=hs_uploads.key, defaults={'value': {'max_upload_mb': 1}})
        data = SimpleUploadedFile('big.pdf', b'x' * (1024 * 1024 + 1))
        resp = self.post_upload(self.hs_a, media=data)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('media', json.loads(resp.content)['errors'])

    def test_get_is_refused(self):
        resp = self.client.get(reverse('highschool_admin:upload_transcript'))
        self.assertEqual(resp.status_code, 405)


class ListTests(_Base):
    def test_lists_own_schools_with_term_and_review(self):
        mine = self.upload(self.hs_a, self.admin)
        reviewer = User.objects.create_user(username=f'ce{_sfx()}', email=f'ce{_sfx()}@x.com')
        mine.mark_reviewed(reviewer)
        self.upload(self.hs_b, self.admin)  # another school's file

        resp = self.client.get(reverse('highschool_admin:get_transcripts'))
        rows = json.loads(resp.content)['data']

        self.assertEqual([r['id'] for r in rows], [str(mine.id)])
        self.assertEqual(rows[0]['term'], 'Fall')
        self.assertTrue(rows[0]['reviewed'])
        self.assertFalse(rows[0]['can_delete'])


class DeleteTests(_Base):
    def _delete(self, record):
        return self.client.post(
            reverse('highschool_admin:delete_transcript', args=[record.id]))

    def test_own_unreviewed_upload_can_be_deleted(self):
        record = self.upload(self.hs_a, self.admin)
        self.assertEqual(self._delete(record).status_code, 200)
        self.assertFalse(HighSchoolTranscript.objects.filter(pk=record.pk).exists())

    def test_someone_elses_upload_is_refused(self):
        colleague = _hs_admin(self.hs_a)
        record = self.upload(self.hs_a, colleague)
        self.assertEqual(self._delete(record).status_code, 403)
        self.assertTrue(HighSchoolTranscript.objects.filter(pk=record.pk).exists())

    def test_reviewed_upload_is_refused(self):
        record = self.upload(self.hs_a, self.admin)
        record.mark_reviewed(self.admin)
        self.assertEqual(self._delete(record).status_code, 403)
        self.assertTrue(HighSchoolTranscript.objects.filter(pk=record.pk).exists())

    def test_other_schools_upload_is_not_found(self):
        record = self.upload(self.hs_b, self.admin)
        self.assertEqual(self._delete(record).status_code, 404)

    def test_get_is_refused(self):
        record = self.upload(self.hs_a, self.admin)
        resp = self.client.get(
            reverse('highschool_admin:delete_transcript', args=[record.id]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(HighSchoolTranscript.objects.filter(pk=record.pk).exists())


class GateTests(_Base):
    def test_anonymous_is_redirected(self):
        self.client.logout()
        resp = self.post_upload(self.hs_a)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(HighSchoolTranscript.objects.exists())

    def test_unverified_two_step_is_redirected(self):
        TwoStep.objects.filter(user=self.admin).update(verified=False)
        resp = self.post_upload(self.hs_a)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(HighSchoolTranscript.objects.exists())


class PageTests(_Base):
    def test_page_renders_the_upload_form(self):
        from cis.models.settings import Setting as S
        import json as _json
        S.objects.get_or_create(key='cis.settings.menu', defaults={'value': {
            'highschool_admin_menu': _json.dumps([{'type': 'nav-item', 'name': 'home',
                'label': 'Home', 'url': 'highschool_admin:dashboard'}])}})
        resp = self.client.get(reverse('highschool_admin:transcripts'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="frm_upload_transcript"', html)
        self.assertIn('name="media"', html)
        self.assertIn('name="term"', html)
        # One school: the select is replaced by a hidden input.
        self.assertIn(f'type="hidden" name="highschool" value="{self.hs_a.id}"', html)
