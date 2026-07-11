"""PT-19: enforce two-step verification on highschool_admin views.

Vulnerable behavior (pre-fix): a highschool_admin who has authenticated with
a password but has NOT completed the second factor could load
/highschool_admin/dashboard/ directly. These tests pin the fixed behavior:
unverified -> redirect to two_step:verify; verified -> 200.

Follows the django_login_history disconnect pattern from
highschool_admin/tests/test_student_detail_scoping.py.
"""
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from two_step.models import TwoStep
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.settings import Setting

User = get_user_model()


class PT19TwoStepEnforcementTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # django_login_history's post_login signal handler blows up in tests
        # because the request has no usable IP. Disconnect for the duration.
        if _login_history_post_login is not None:
            user_logged_in.disconnect(_login_history_post_login)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if _login_history_post_login is not None:
            user_logged_in.connect(_login_history_post_login)

    @classmethod
    def setUpTestData(cls):
        cls.group, _ = Group.objects.get_or_create(name='highschool_admin')

        # The dashboard view renders the highschool_admin menu, which reads the
        # `highschool_admin_menu` Setting (a JSON-string list). Without it
        # json.loads(None) raises. A minimal one-item menu satisfies the build.
        Setting.objects.get_or_create(
            key='cis.settings.menu',
            defaults={'value': {'highschool_admin_menu': json.dumps([
                {'type': 'nav-item', 'name': 'home', 'label': 'Home',
                 'url': 'highschool_admin:dashboard'},
            ])}},
        )

        cls.user = User.objects.create_user(
            username='hsadmin_pt19',
            email='hsadmin_pt19@example.com',
            password='correct-horse',
            first_name='Hailey',
            last_name='Admin',
        )
        cls.user.groups.add(cls.group)

        cls.highschool = HighSchool.objects.create(name='PT19 High')
        # HSAdministrator links the user to the highschool(s); the dashboard
        # view calls get_current_hsadmin(request) and user.get_highschools(),
        # which reads Active HSAdministratorPosition rows.
        cls.hsadmin = HSAdministrator.objects.create(user=cls.user)
        position = HSPosition.objects.create(name='Counselor')
        HSAdministratorPosition.objects.create(
            hsadmin=cls.hsadmin, highschool=cls.highschool, position=position,
            status='Active',
        )

        cls.dashboard_url = reverse('highschool_admin:dashboard')
        cls.verify_url = reverse('two_step:verify')

    def _login(self):
        """Password-authenticate the client (single factor only)."""
        ok = self.client.login(
            username='hsadmin_pt19@example.com', password='correct-horse',
        )
        # EmailAuthBackend authenticates by email; if username login fails,
        # fall back to force_login which still leaves the session UNVERIFIED.
        if not ok:
            self.client.force_login(self.user)

    def _mark_session_verified(self):
        """Create a verified TwoStep row for the client's current session."""
        session_key = self.client.session.session_key
        TwoStep.objects.update_or_create(
            session_id=session_key,
            user=self.user,
            defaults={'verification_code': '123456', 'verified': True},
        )

    def test_unverified_session_is_denied_dashboard(self):
        """REPRO of PT-19: authenticated-but-unverified must NOT reach the
        dashboard; it must redirect to the two-step verify step."""
        self._login()
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.verify_url, resp['Location'])

    def test_verified_session_reaches_dashboard(self):
        """A highschool_admin who HAS completed two-step gets through (200)."""
        self._login()
        self._mark_session_verified()
        resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)

    def test_unverified_session_denied_other_protected_view(self):
        """Enforcement is uniform: a second protected page (students list)
        is also gated, not just the dashboard."""
        self._login()
        resp = self.client.get(reverse('highschool_admin:students'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.verify_url, resp['Location'])

    def test_impersonated_session_bypasses_gate(self):
        """impersonate sessions are allowed through by design
        (two_step/decorators.py checks request.user.is_impersonate).

        The `impersonate` middleware sets `is_impersonate` as an instance
        attribute on the request user (defaulting it to False on every
        request, then True for active impersonation sessions). We patch the
        middleware so the resolved request user is flagged as impersonating,
        exercising the decorator's documented carve-out: when is_impersonate
        is True the view runs even with no verified TwoStep row.
        """
        from unittest.mock import patch
        import impersonate.middleware as impersonate_mw

        original_process_request = (
            impersonate_mw.ImpersonateMiddleware.process_request
        )

        def _impersonating_process_request(self, request):
            result = original_process_request(self, request)
            request.user.is_impersonate = True
            return result

        self._login()
        with patch.object(
            impersonate_mw.ImpersonateMiddleware,
            'process_request',
            _impersonating_process_request,
        ):
            resp = self.client.get(self.dashboard_url)
        self.assertEqual(resp.status_code, 200)
