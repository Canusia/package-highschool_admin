"""Campus-scoped school picker on the transcript upload form (cis HighSchoolCampus)."""
import uuid

from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context
from cis.models.course import Campus
from cis.models.highschool import HighSchool, HighSchoolCampus
from cis.models.term import Term

from ..views.transcripts import HSAdminTranscriptUploadForm


def _campus():
    return Campus.objects.create(
        name=f'C-{uuid.uuid4().hex[:8]}',
        code=f'{settings.CAMPUS_CODE_PREFIX}_{uuid.uuid4().hex[:6]}')


def _hs(name, campus=None, status='Active'):
    hs = HighSchool.objects.create(name=name, code=uuid.uuid4().hex[:8])
    HighSchoolCampus.objects.filter(highschool=hs).delete()
    if campus is not None:
        HighSchoolCampus.objects.create(
            highschool=hs, campus=campus, status=status)
    return hs


class TranscriptSchoolPickerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = _campus(), _campus()
        self.mine = _hs('Mine', self.a)
        self.foreign = _hs('Foreign', self.b)
        self.inactive = _hs('Dormant', self.a, 'Inactive')
        # The admin manages all three; the campus decides what is offered.
        self.managed = HighSchool.objects.filter(
            pk__in=[self.mine.pk, self.foreign.pk, self.inactive.pk])

        # The term choices need an active term; the school field is under test.
        patcher = mock.patch(
            'cis.forms.highschool.upload_terms', lambda: Term.objects.none())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _form(self, data=None):
        return HSAdminTranscriptUploadForm(self.managed, data)

    # Spec section 2: the HS admin portal is unchanged. The admin's own
    # schools are offered whatever their campus links say.

    @override_settings(MULTI_CAMPUS=True)
    def test_multi_campus_offers_every_managed_school(self):
        with campus_context(self.a):
            qs = self._form().fields['highschool'].queryset
            self.assertEqual(
                {h.pk for h in qs}, {self.mine.pk, self.foreign.pk, self.inactive.pk})

    @override_settings(MULTI_CAMPUS=True)
    def test_inactive_linked_school_admin_gets_upload_form(self):
        only = HighSchool.objects.filter(pk=self.inactive.pk)
        with campus_context(self.a):
            form = HSAdminTranscriptUploadForm(only)
            self.assertEqual(list(form.fields['highschool'].queryset), [self.inactive])
            form = HSAdminTranscriptUploadForm(
                only, {'highschool': str(self.inactive.pk)})
            form.is_valid()
            self.assertNotIn('highschool', form.errors)

    @override_settings(MULTI_CAMPUS=True)
    def test_unmanaged_school_post_is_rejected(self):
        stranger = _hs('Stranger', self.a)
        with campus_context(self.a):
            form = self._form({'highschool': str(stranger.pk)})
            self.assertFalse(form.is_valid())
            self.assertIn('highschool', form.errors)

    @override_settings(MULTI_CAMPUS=False)
    def test_single_campus_offers_every_managed_school(self):
        qs = self._form().fields['highschool'].queryset
        self.assertEqual(
            {h.pk for h in qs}, {self.mine.pk, self.foreign.pk, self.inactive.pk})
