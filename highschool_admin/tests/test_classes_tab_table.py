"""The student-detail #classes tab renders the shared registrations table."""
import uuid

from django.test import TestCase
from django.urls import reverse

from highschool_admin.highschool_admin.tests.test_student_detail_tabs import (
    _login, _provision_groups, _provision_menu, _provision_registration_setting,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.student import Student

User = get_user_model()


class ClassesTabTableTests(TestCase):
    def setUp(self):
        _provision_groups()
        _provision_registration_setting()
        self.hs = HighSchool.objects.create(name='HS')
        self.user = User.objects.create(email='a@x.com', username='a@x.com')
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.hsadmin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
        HSAdministratorPosition.objects.create(
            hsadmin=self.hsadmin, highschool=self.hs,
            position=position, status='Active',
        )
        su = User.objects.create(email='s@x.com', username='s@x.com')
        self.student = Student.objects.create(user=su, highschool=self.hs)
        _provision_menu()

    def test_classes_pane_uses_shared_partial(self):
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:student', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        # New shared table + AJAX endpoint present:
        self.assertContains(resp, 'id="tbl_hs_student_registrations"')
        self.assertContains(
            resp,
            f'/highschool_admin/api/student-registrations/?format=datatables&student={self.student.id}')
        # Old hand-rolled table gone:
        self.assertNotContains(resp, 'id="student_classes"')
