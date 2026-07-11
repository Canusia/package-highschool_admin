import json

from django.test import TestCase

from cis.menu import HS_ADMIN_MENU
from cis.models.settings import Setting
from ..views.utils import get_hsadmin_menu


class GetHsadminMenuTests(TestCase):
    """The helper is the single source of truth for the HS-admin portal menu:
    settings first, legacy dict as a safety net."""

    MENU_KEY = 'cis.settings.menu'

    def test_returns_parsed_list_from_setting(self):
        items = [
            {'type': 'nav-item', 'name': 'home', 'label': 'Home',
             'url': 'highschool_admin:dashboard'},
            {'type': 'nav-item', 'name': 'students', 'label': 'Students',
             'url': 'highschool_admin:students'},
        ]
        Setting.objects.update_or_create(
            key=self.MENU_KEY,
            defaults={'value': {'highschool_admin_menu': json.dumps(items)}},
        )
        self.assertEqual(get_hsadmin_menu(), items)

    def test_falls_back_to_legacy_dict_when_setting_missing(self):
        Setting.objects.filter(key=self.MENU_KEY).delete()
        self.assertEqual(get_hsadmin_menu(), HS_ADMIN_MENU)

    def test_falls_back_to_legacy_dict_when_json_malformed(self):
        Setting.objects.update_or_create(
            key=self.MENU_KEY,
            defaults={'value': {'highschool_admin_menu': 'not-json{'}},
        )
        self.assertEqual(get_hsadmin_menu(), HS_ADMIN_MENU)
