"""The dashboard pay-type message must honour `student_tabs.show_pay_type`.

A tenant that hides the Pay Type tab has no screen to review pay types on, so
the "needing payment type review" message would send counselors nowhere
(package-highschool_admin#8).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from . import PKG
from ..page_messages import pending_pay_type


class PendingPayTypeGatingTests(SimpleTestCase):

    def _run(self, show_pay_type, count):
        qs = MagicMock()
        qs.count.return_value = count
        manager = MagicMock()
        manager.filter.return_value = qs
        with patch(f'{PKG}.page_messages.student_tabs') as tabs, \
             patch(f'{PKG}.page_messages.get_user_highschools'), \
             patch('cis.models.section.StudentRegistration.objects', manager):
            tabs.show_pay_type.return_value = show_pay_type
            return pending_pay_type(MagicMock()), manager

    def test_message_suppressed_when_pay_type_tab_hidden(self):
        msg, manager = self._run(show_pay_type=False, count=3)
        self.assertIsNone(msg)
        manager.filter.assert_not_called()

    def test_message_shown_when_enabled_and_pending(self):
        msg, _ = self._run(show_pay_type=True, count=3)
        self.assertIn('payment type review', msg.text)

    def test_no_message_when_enabled_but_nothing_pending(self):
        msg, _ = self._run(show_pay_type=True, count=0)
        self.assertIsNone(msg)
