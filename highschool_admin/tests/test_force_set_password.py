"""Forced password change on the HS admin dashboard keeps the session (#14, package-cis#55).

`set_password()` rotates the session auth hash; unless the view calls
`update_session_auth_hash()`, Django drops the session on the next request and
the HS admin lands on the login page. That call also cycles the session key,
and two-step verification is stored per session key, so the view must carry
the verification over or the HS admin is sent back to /two_step/verify.
"""
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from cis.models.customuser import CustomUser
from cis.models.highschool_administrator import HSAdministrator
from two_step.models import TwoStep

NEW_PASSWORD = 'Tr1cky-Horse-Battery-42'


class HSAdminForceSetPasswordTests(TestCase):
    def setUp(self):
        self._saved_receivers = list(user_logged_in.receivers)
        user_logged_in.receivers = []
        group, _ = Group.objects.get_or_create(name='highschool_admin')
        self.user = CustomUser.objects.create(
            username='hsa', email='hsa@example.com', require_password_reset=True)
        self.user.set_password('Old-Passw0rd-xyz')
        self.user.save()
        self.user.groups.add(group)
        HSAdministrator.objects.create(user=self.user)
        self.client.force_login(self.user)
        TwoStep.objects.create(
            session_id=self.client.session.session_key, user=self.user,
            verification_code='123456', verified=True)
        self.url = reverse('highschool_admin:dashboard')

    def tearDown(self):
        user_logged_in.receivers = self._saved_receivers

    def _change_password(self):
        return self.client.post(self.url, {
            'action': 'force_set_password',
            'new_password1': NEW_PASSWORD,
            'new_password2': NEW_PASSWORD,
        })

    def test_saving_keeps_the_session_valid(self):
        resp = self._change_password()
        self.assertRedirects(resp, self.url, fetch_redirect_response=False)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.require_password_reset)
        # the hash stored in the session must match the new password's hash,
        # or the next request is treated as logged out
        self.assertEqual(self.client.session[HASH_SESSION_KEY],
                         self.user.get_session_auth_hash())

    def test_two_step_verification_survives_the_session_key_change(self):
        old_key = self.client.session.session_key
        self._change_password()
        new_key = self.client.session.session_key
        self.assertNotEqual(new_key, old_key)
        self.assertTrue(TwoStep.objects.filter(
            session_id=new_key, user=self.user, verified=True).exists())

        # the next dashboard request is not bounced to two-step verification
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.get('Location'), reverse('two_step:verify'))

    def test_saving_tags_the_message_for_the_popup(self):
        resp = self._change_password()
        tags = [m.extra_tags for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('password_changed' in (t or '') for t in tags), tags)
