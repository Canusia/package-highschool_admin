"""highschool_admin student-page tab visibility setting.

Stored in the Setting model under key ``highschool_admin.settings.student_tabs``::

    {'show_recommendation': bool, 'show_review': bool, 'show_pay_type': bool}

Controls the Recommendation / Review / Pay Type tabs on the students list page
and the student detail page, and the "pending recommendation" dashboard message.
Absent keys default to True (backward compatible — tabs stay visible until an
admin unchecks them).
"""
from django import forms
from django.http import JsonResponse
from django.urls import reverse_lazy

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.settings import Setting

_FIELDS = ('show_recommendation', 'show_review', 'show_pay_type')


class SettingForm(forms.Form):
    show_recommendation = forms.BooleanField(
        required=False, label='Show Recommendation tab',
        help_text='Show the Pending Recommendation tab and the dashboard '
                  '"pending recommendation" message.')
    show_review = forms.BooleanField(
        required=False, label='Show Review tab',
        help_text='Show the application Review tab.')
    show_pay_type = forms.BooleanField(
        required=False, label='Show Pay Type tab',
        help_text='Show the Pending Pay Type tab.')

    def _to_python(self):
        return {f: bool(self.cleaned_data.get(f)) for f in _FIELDS}


class student_tabs(SettingForm):
    # Pinned literal (NOT str(__name__)): the module path changes under the
    # nested dev layout, but the Setting DB key must stay stable so existing
    # rows and the prod/dev configs agree.
    key = 'highschool_admin.settings.student_tabs'

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse_lazy(
            'setting:run_record', args=[request.GET.get('report_id')]) if request else ''
        self.helper.add_input(Submit('submit', 'Save Setting'))

    @classmethod
    def get_config(cls):
        """Raw stored dict ({} if unset)."""
        try:
            return Setting.objects.get(key=cls.key).value or {}
        except Setting.DoesNotExist:
            return {}

    @classmethod
    def tabs(cls):
        """The three resolved booleans; absent keys default to True."""
        cfg = cls.get_config()
        return {f: bool(cfg.get(f, True)) for f in _FIELDS}

    @classmethod
    def show_recommendation(cls):
        return cls.tabs()['show_recommendation']

    @classmethod
    def show_review(cls):
        return cls.tabs()['show_review']

    @classmethod
    def show_pay_type(cls):
        return cls.tabs()['show_pay_type']

    @classmethod
    def from_db(cls):
        """Form-population initials (checkbox states)."""
        return cls.tabs()

    def install(self):
        if Setting.objects.filter(key=self.key).exists():
            return
        Setting.objects.create(
            key=self.key,
            value={f: True for f in _FIELDS})

    def run_record(self):
        setting, _ = Setting.objects.get_or_create(key=self.key)
        setting.value = self._to_python()
        setting.save()
        return JsonResponse({'message': 'Successfully saved settings',
                             'status': 'success'})
