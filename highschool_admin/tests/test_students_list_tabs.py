"""Tests for students list page tab gating via highschool_admin.settings.student_tabs.

Tests verify that the Pending Recommendation, Review, and Pay Type nav-items are
shown/hidden according to the student_tabs Setting, while the ungated tabs
(Registrations by Term, Students by Term) are always present.
"""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting
from two_step.models import TwoStep

User = get_user_model()
TAB_KEY = 'highschool_admin.settings.student_tabs'


def _login(user):
    """Login and mark session as two-step verified."""
    try:
        from django_login_history.models import post_login
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.disconnect(post_login)
        c = Client()
        c.force_login(user)
        user_logged_in.connect(post_login)
    except Exception:
        c = Client()
        c.force_login(user)
    session_key = c.session.session_key
    TwoStep.objects.update_or_create(
        session_id=session_key,
        user=user,
        defaults={'verification_code': '123456', 'verified': True},
    )
    return c


def _provision_menu():
    Setting.objects.get_or_create(
        key='cis.settings.menu',
        defaults={'value': {'highschool_admin_menu': json.dumps([
            {'type': 'nav-item', 'name': 'students', 'label': 'Students',
             'url': 'highschool_admin:students'},
        ])}},
    )


class StudentsListTabsTests(TestCase):
    def setUp(self):
        self.hs = HighSchool.objects.create(name='HS Test')
        self.user = User.objects.create(email='a@x.com', username='a@x.com')
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name='Counselor')
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs, position=position, status='Active',
        )
        _provision_menu()

    def _set_tabs(self, **flags):
        base = {'show_recommendation': True, 'show_review': True, 'show_pay_type': True}
        base.update(flags)
        Setting.objects.update_or_create(key=TAB_KEY, defaults={'value': base})

    def test_all_tabs_visible_by_default(self):
        """Without a tab setting all three gated tabs are visible (default True)."""
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:students'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="#pending_recommendation"')
        self.assertContains(resp, 'href="#pending_pay_type"')
        self.assertContains(resp, 'href="#pending_review"')

    def test_recommendation_tab_hidden(self):
        """show_recommendation=False removes the nav-item; review still shows."""
        self._set_tabs(show_recommendation=False)
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:students'))
        self.assertNotContains(resp, 'href="#pending_recommendation"')
        self.assertContains(resp, 'href="#pending_review"')

    def test_review_and_paytype_hidden(self):
        """show_review=False and show_pay_type=False hide those two tabs."""
        self._set_tabs(show_review=False, show_pay_type=False)
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:students'))
        self.assertNotContains(resp, 'href="#pending_review"')
        self.assertNotContains(resp, 'href="#pending_pay_type"')
        self.assertContains(resp, 'href="#pending_recommendation"')

    def test_ungated_tabs_always_present(self):
        """Registrations by Term and Students by Term are always rendered."""
        self._set_tabs(show_recommendation=False, show_review=False, show_pay_type=False)
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:students'))
        self.assertContains(resp, 'href="#student_registrations"')
        self.assertContains(resp, 'href="#students"')
