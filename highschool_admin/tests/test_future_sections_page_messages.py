from unittest.mock import patch

from django.test import SimpleTestCase

from cis.page_messages import get_page_messages
from .. import page_messages  # noqa: F401  (ensure providers registered)


class FutureSectionsProviderTests(SimpleTestCase):
    def test_window_closed_emits_warning(self):
        # Patch is_window_open where the provider looks it up.
        with patch('highschool_admin.highschool_admin.page_messages._future_course') as fc:
            fc.return_value.is_window_open.return_value = False
            msgs = get_page_messages('highschool_admin', 'future_sections', request=None)
        self.assertTrue(any('window' in m.text.lower() for m in msgs))
        self.assertTrue(all(m.level == 'warning' for m in msgs if 'window' in m.text.lower()))

    def test_window_open_emits_nothing_for_window_provider(self):
        with patch('highschool_admin.highschool_admin.page_messages._future_course') as fc:
            fc.return_value.is_window_open.return_value = True
            msgs = get_page_messages('highschool_admin', 'future_sections', request=None)
        self.assertFalse(any('window' in m.text.lower() for m in msgs))
