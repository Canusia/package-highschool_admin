from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from cis.page_messages import get_page_messages
from . import PKG
from .. import page_messages  # noqa: F401  (register providers)


class PendingRecommendationGatingTests(SimpleTestCase):
    @patch(f'{PKG}.page_messages.student_tabs')
    @patch(f'{PKG}.page_messages.get_user_highschools')
    def test_message_suppressed_when_recommendation_tab_hidden(self, _hs, tabs):
        tabs.show_recommendation.return_value = False
        msgs = get_page_messages('highschool_admin', 'dashboard', request=MagicMock())
        self.assertFalse(any('recommendation' in m.text.lower() for m in msgs))

    @patch(f'{PKG}.page_messages.student_tabs')
    @patch(f'{PKG}.page_messages._pending_recommendation_count', return_value=3)
    @patch(f'{PKG}.page_messages.get_user_highschools')
    def test_message_shown_when_enabled_and_pending(self, _hs, _cnt, tabs):
        tabs.show_recommendation.return_value = True
        msgs = get_page_messages('highschool_admin', 'dashboard', request=MagicMock())
        self.assertTrue(any('recommendation' in m.text.lower() for m in msgs))
