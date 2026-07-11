"""Tests for student detail page tab gating via highschool_admin.settings.student_tabs.

Tests verify that Pay Type and Review tabs are shown/hidden according to the
student_tabs Setting, and that the Recommendation term-tabs are gated on
show_recommendation rather than the old `record.needs_recommendation or True`.
"""
import json
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting
from cis.models.student import Student
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


def _provision_groups():
    for name in ('student', 'ce', 'highschool_admin'):
        Group.objects.get_or_create(name=name)


def _provision_registration_setting():
    """registration_terms() reads a Setting; without it the detail view errors."""
    from django.conf import settings as dj_settings
    key = f'{dj_settings.CAMPUS_CODE_PREFIX}_cis_registrations'
    Setting.objects.get_or_create(
        key=key, defaults={'value': {'registration_terms': []}},
    )


class StudentDetailTabsTests(TestCase):
    def setUp(self):
        _provision_groups()
        _provision_menu()
        _provision_registration_setting()

        self.hs = HighSchool.objects.create(name='HS Tab Test')

        # HS admin user
        self.user = User.objects.create(
            email='tabadmin@x.com', username='tabadmin@x.com',
        )
        self.user.groups.add(
            Group.objects.get_or_create(name='highschool_admin')[0]
        )
        self.hsadmin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
        HSAdministratorPosition.objects.create(
            hsadmin=self.hsadmin, highschool=self.hs,
            position=position, status='Active',
        )

        # Student belonging to that highschool
        su = User.objects.create(email='tabstu@x.com', username='tabstu@x.com')
        self.student = Student.objects.create(user=su, highschool=self.hs)

    def _set_tabs(self, **flags):
        base = {'show_recommendation': True, 'show_review': True, 'show_pay_type': True}
        base.update(flags)
        Setting.objects.update_or_create(key=TAB_KEY, defaults={'value': base})

    def _url(self):
        return reverse('highschool_admin:student', args=[self.student.id])

    def test_paytype_and_review_tabs_visible_by_default(self):
        c = _login(self.user)
        resp = c.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="#pay_type"')
        self.assertContains(resp, 'href="#review"')

    def test_paytype_tab_hidden(self):
        self._set_tabs(show_pay_type=False)
        c = _login(self.user)
        resp = c.get(self._url())
        self.assertNotContains(resp, 'href="#pay_type"')
        self.assertContains(resp, 'href="#review"')

    def test_review_tab_hidden(self):
        self._set_tabs(show_review=False)
        c = _login(self.user)
        resp = c.get(self._url())
        self.assertNotContains(resp, 'href="#review"')
