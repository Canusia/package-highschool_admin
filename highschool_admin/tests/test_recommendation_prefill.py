"""Reopening a submitted recommendation must prefill the tenant's own fields.

The view rebuilt `initial` from a fixed list of field names, five of which are
Pennsylvania-specific (Keystone Exam, PSSA, GEIP) and belong to a tenant's
`myce_tenant_configs/services/recommendation_form.py`, not to this package.
Any tenant whose rec form declares different fields lost them:

1. counselor submits with the field set -- stored correctly;
2. counselor reopens the student -- the control renders blank;
3. counselor submits again -- the form is valid and the stored value is
   silently overwritten with whatever the blank control resolved to.

Data loss, no error shown. See ewu#46.

These tests drive the view through a stand-in form declaring a field name no
tenant uses, so they assert the *mechanism* (prefill follows the form's own
declared fields) rather than any tenant's vocabulary.
"""
import uuid
from unittest import mock

from django import forms
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting
from cis.models.student import Student, StudentRecommendation
from cis.models.term import AcademicYear, Term

from highschool_admin.highschool_admin.tests.test_student_detail_tabs import (
    _login, _provision_groups, _provision_menu, _provision_registration_setting,
)

User = get_user_model()

VIEW_MODULE = 'highschool_admin.highschool_admin.views.students'


class StandInRecommendationForm(forms.Form):
    """A tenant rec form whose vocabulary is nobody's hardcoded list."""

    student = forms.CharField(required=True, widget=forms.HiddenInput())
    term = forms.CharField(required=False, widget=forms.HiddenInput())
    student_state_id = forms.CharField(required=False, widget=forms.HiddenInput())
    upload_label = forms.CharField(required=False)
    student_gpa = forms.CharField(required=False, label="Student's GPA")
    student_bridge = forms.CharField(required=False)
    tenant_specific_marker = forms.ChoiceField(
        required=False,
        label='Free/Reduced Lunch',
        choices=[('', 'Select'), ('yes', 'Yes'), ('no', 'No')],
    )

    def __init__(self, student=None, current_registrations=None, *args, **kwargs):
        super().__init__(*args, **kwargs)


class RecommendationPrefillTests(TestCase):
    def setUp(self):
        _provision_groups()
        _provision_menu()
        _provision_registration_setting()

        self.hs = HighSchool.objects.create(name='HS')
        self.blurb = 'Upload the signed form.'
        Setting.objects.update_or_create(
            key=f'{dj_settings.CAMPUS_CODE_PREFIX}_counselor_language',
            defaults={'value': {'upload_label': self.blurb}})
        self.user = User.objects.create(
            email=f'a-{uuid.uuid4().hex[:6]}@x.com',
            username=f'a-{uuid.uuid4().hex[:6]}')
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs,
            position=position, status='Active')

        su = User.objects.create(
            email=f's-{uuid.uuid4().hex[:6]}@x.com',
            username=f's-{uuid.uuid4().hex[:6]}')
        self.student = Student.objects.create(user=su, highschool=self.hs)

        # registration_terms() reads this Setting; the term must be listed or
        # the view never finds the stored recommendation to prefill from.
        ay = AcademicYear.objects.create(name=f'AY-{uuid.uuid4().hex[:6]}')
        self.term = Term.objects.create(
            academic_year=ay, code='F25', label=f'Fall-{uuid.uuid4().hex[:6]}')
        Setting.objects.update_or_create(
            key=f'{dj_settings.CAMPUS_CODE_PREFIX}_cis_registrations',
            defaults={'value': {'registration_terms': [str(self.term.id)]}})

    def _store_recommendation(self, payload):
        return StudentRecommendation.objects.create(
            student=self.student, term=self.term, recommendation=payload)

    def _get_form(self):
        client = _login(self.user)
        with mock.patch(f'{VIEW_MODULE}.StudentRecommendationForm',
                        StandInRecommendationForm):
            resp = client.get(
                reverse('highschool_admin:student', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        return resp.context['recommendation_form']

    def test_stored_value_for_a_tenant_declared_field_is_prefilled(self):
        self._store_recommendation({
            'student_gpa': '3.4',
            'tenant_specific_marker': 'yes',
        })

        form = self._get_form()

        self.assertEqual(form.initial.get('tenant_specific_marker'), 'yes')

    def test_stored_values_outside_the_form_are_not_prefilled(self):
        """A field the tenant has since dropped must not leak back in -- the
        form's declared fields are the contract, not whatever the blob holds."""
        self._store_recommendation({
            'student_gpa': '3.4',
            'retired_field_from_an_older_form': 'stale',
        })

        form = self._get_form()

        self.assertNotIn('retired_field_from_an_older_form', form.initial)

    def test_view_supplied_initial_is_not_overwritten_by_the_blob(self):
        """`student` and `student_state_id` are set from the record itself and
        must win over anything stored."""
        self._store_recommendation({'student': 'bogus', 'student_gpa': '3.4'})

        form = self._get_form()

        self.assertEqual(str(form.initial.get('student')), str(self.student.id))

    def test_stored_value_wins_over_a_view_supplied_default(self):
        """Guard for the refactor: the view seeds `student_bridge` with '2' as
        a default, and a stored value has always overridden it. Deriving the
        prefill from the form's fields must not turn that default into an
        override."""
        self._store_recommendation({'student_bridge': '1'})

        form = self._get_form()

        self.assertEqual(form.initial.get('student_bridge'), '1')

    def test_upload_label_is_set_on_a_first_visit(self):
        """`initial['upload_label']` was set only inside the `if existing:`
        branch, so the configured Pre-Upload Blurb rendered blank until a
        recommendation already existed."""
        form = self._get_form()

        self.assertEqual(form.initial.get('upload_label'), self.blurb)
