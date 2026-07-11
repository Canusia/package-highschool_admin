"""The 'Bulk Enroll' item must render in the highschool_admin sidebar and
highlight as active on the bulk-enroll page. draw_menu() reads the menu JSON
from the cis.settings.menu Setting, so the test seeds it via install()."""
from django.test import TestCase, RequestFactory

from cis.menu import draw_menu, HS_ADMIN_MENU
from cis.settings.menu import menu as menu_setting


class BulkEnrollMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # install() seeds Setting(key='cis.settings.menu') from the defaults
        # blob (which Task 4 Step 3 updates to include the Bulk Enroll item).
        request = RequestFactory().get('/')
        menu_setting(request=request).install()

    def test_bulk_enroll_item_renders_and_links(self):
        html = draw_menu(HS_ADMIN_MENU, 'bulk_enroll', '', 'highschool_admin')
        self.assertIn('Bulk Enroll', html)
        self.assertIn('/highschool_admin/bulk_enroll/', html)

    def test_bulk_enroll_item_active_on_page(self):
        html = draw_menu(HS_ADMIN_MENU, 'bulk_enroll', '', 'highschool_admin')
        self.assertIn("id='id_nav_item_bulk_enroll'", html)
        before_anchor = html.split("id_nav_item_bulk_enroll")[0].rsplit('nav-item', 1)[1]
        self.assertIn('active', before_anchor)
