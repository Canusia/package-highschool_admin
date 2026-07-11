from django.test import TestCase

from cis.models.settings import Setting
from ..settings.student_tabs import student_tabs

KEY = 'highschool_admin.settings.student_tabs'


class StudentTabsSettingTests(TestCase):
    def test_defaults_all_true_when_unset(self):
        Setting.objects.filter(key=KEY).delete()
        self.assertEqual(
            student_tabs.tabs(),
            {'show_recommendation': True, 'show_review': True, 'show_pay_type': True},
        )
        self.assertTrue(student_tabs.show_recommendation())
        self.assertTrue(student_tabs.show_review())
        self.assertTrue(student_tabs.show_pay_type())

    def test_reads_stored_booleans(self):
        Setting.objects.update_or_create(
            key=KEY,
            defaults={'value': {
                'show_recommendation': False,
                'show_review': True,
                'show_pay_type': False,
            }},
        )
        self.assertEqual(student_tabs.tabs(), {
            'show_recommendation': False, 'show_review': True, 'show_pay_type': False,
        })
        self.assertFalse(student_tabs.show_recommendation())
        self.assertTrue(student_tabs.show_review())
        self.assertFalse(student_tabs.show_pay_type())

    def test_missing_key_defaults_true(self):
        # a partially-populated value still defaults absent keys to True
        Setting.objects.update_or_create(
            key=KEY, defaults={'value': {'show_review': False}})
        self.assertTrue(student_tabs.show_recommendation())
        self.assertFalse(student_tabs.show_review())
        self.assertTrue(student_tabs.show_pay_type())

    def test_install_seeds_all_true_without_clobbering(self):
        Setting.objects.filter(key=KEY).delete()
        student_tabs(request=None).install()
        v = Setting.objects.get(key=KEY).value
        self.assertEqual(v, {
            'show_recommendation': True, 'show_review': True, 'show_pay_type': True,
        })
        # re-install must not clobber an admin's saved value
        Setting.objects.update_or_create(
            key=KEY, defaults={'value': {'show_recommendation': False,
                                         'show_review': False, 'show_pay_type': False}})
        student_tabs(request=None).install()
        self.assertFalse(student_tabs.show_recommendation())
