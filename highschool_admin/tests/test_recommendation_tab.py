"""The student-detail recommendation UI is a single tab (not per-term)."""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

import uuid

from highschool_admin.highschool_admin.tests.test_student_detail_tabs import (
    _login, _provision_groups, _provision_menu, _provision_registration_setting,
)
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.student import Student

User = get_user_model()


class RecommendationTabTests(TestCase):
    def setUp(self):
        _provision_groups()
        _provision_menu()
        _provision_registration_setting()

        self.hs = HighSchool.objects.create(name='HS')
        self.user = User.objects.create(email='a@x.com', username='a@x.com')
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs,
            position=position, status='Active',
        )
        su = User.objects.create(email='s@x.com', username='s@x.com')
        self.student = Student.objects.create(user=su, highschool=self.hs)

    def test_single_recommendation_tab_no_per_term_tabs(self):
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:student', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        # Page renders without the removed term_data/#term_rec_* machinery:
        self.assertNotContains(resp, 'href="#term_rec_')
