"""Pluggable class-section scoping for the Classes list and detail page (#3).

Both ask services.section_scope.visible_sections(), so a listed section always
opens and an unlisted one always 404s. The rule is 'hosted' by default,
'hosted_or_own_students' via MY_CE, or a tenant override.
"""
import types
import uuid
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

try:
    from django_login_history.models import post_login as _login_history_post_login
except Exception:  # pragma: no cover
    _login_history_post_login = None

from cis.models.course import Cohort, College, Course, Department
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.section import ClassSection, StudentRegistration
from cis.models.student import Student
from cis.models.term import AcademicYear, Term
from two_step.models import TwoStep

from . import PKG

User = get_user_model()
API_URL = '/highschool_admin/api/class-section/?format=datatables&term={term}'


def _u(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


def _my_ce(rule):
    return {**(getattr(settings, 'MY_CE', None) or {}),
            'highschool_admin': {'class_section_scope': rule}}


class ClassSectionScopeTests(TestCase):
    @classmethod
    def setUpClass(cls):
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
        for name in ('highschool_admin', 'student'):
            Group.objects.get_or_create(name=name)
        User.objects.get_or_create(username='cron', defaults={'email': 'cron@example.com'})

        ay = AcademicYear.objects.create(name=_u('AY'))
        cls.term = Term.objects.create(academic_year=ay, code='FA', label=_u('Fall'))
        college = College.objects.create(name=_u('College'))
        dept = Department.objects.create(name=_u('Dept'), college=college)
        cohort = Cohort.objects.create(name=_u('Cohort'), designator='CO')
        course = Course.objects.create(
            catalog_number='101', title='Intro', department=dept, cohort=cohort, credit_hours=3)

        cls.liberty = HighSchool.objects.create(name=_u('Liberty'))
        cls.victory = HighSchool.objects.create(name=_u('Victory'))

        def section(hs):
            return ClassSection.objects.create(
                class_number=_u('CN'), section_number='01', term=cls.term,
                course=course, highschool=hs)

        cls.hosted = section(cls.liberty)
        cls.consortium = section(cls.victory)    # a Liberty student is enrolled here
        cls.unrelated = section(cls.victory)

        for last in ('One', 'Two'):  # two students in one section: must list it once
            user = User.objects.create_user(
                username=_u(last), email=f'{_u(last)}@x.com', password='x', last_name=last)
            student = Student.objects.create(user=user, highschool=cls.liberty)
            StudentRegistration.objects.create(
                student=student, class_section=cls.consortium,
                status='registered', status_changed_on={})

        cls.admin_user = User.objects.create_user(
            username=_u('admin'), email=f'{_u("admin")}@x.com', password='x')
        cls.admin_user.groups.add(Group.objects.get(name='highschool_admin'))
        admin = HSAdministrator.objects.create(user=cls.admin_user)
        HSAdministratorPosition.objects.create(
            hsadmin=admin, highschool=cls.liberty,
            position=HSPosition.objects.create(name=_u('Pos')), status='Active')

    def _client(self):
        client = APIClient()
        client.force_login(self.admin_user)
        TwoStep.objects.update_or_create(
            session_id=client.session.session_key, user=self.admin_user,
            defaults={'verification_code': '123456', 'verified': True})
        return client

    def _listed(self):
        rows = self._client().get(API_URL.format(term=self.term.id)).json()['data']
        return [row['id'] for row in rows]

    def _opens(self, section):
        return self._client().get(reverse(
            'highschool_admin:class_section', kwargs={'record_id': section.id})).status_code

    def test_default_is_hosted_only(self):
        self.assertEqual(self._listed(), [str(self.hosted.id)])
        self.assertEqual(self._opens(self.hosted), 200)
        self.assertEqual(self._opens(self.consortium), 404)

    def test_hosted_or_own_students_includes_consortium_once(self):
        with override_settings(MY_CE=_my_ce('hosted_or_own_students')):
            listed = self._listed()
            self.assertEqual(sorted(listed), sorted([str(self.hosted.id), str(self.consortium.id)]))
            self.assertEqual(self._opens(self.consortium), 200)
            self.assertEqual(self._opens(self.unrelated), 404)

    def test_term_filter_still_applies(self):
        other = Term.objects.create(academic_year=self.term.academic_year, code='SP', label=_u('Spr'))
        with override_settings(MY_CE=_my_ce('hosted_or_own_students')):
            rows = self._client().get(API_URL.format(term=other.id)).json()['data']
        self.assertEqual(rows, [])

    def test_unknown_rule_falls_back_to_hosted(self):
        with override_settings(MY_CE=_my_ce('nonsense')):
            self.assertEqual(self._listed(), [str(self.hosted.id)])

    def test_tenant_override_wins(self):
        def only_unrelated(request, highschools):
            return ClassSection.objects.filter(pk=self.unrelated.pk)

        with mock.patch('cis.services.tenant_services.get_tenant_override',
                        return_value=only_unrelated), \
                override_settings(MY_CE=_my_ce('hosted_or_own_students')):
            self.assertEqual(self._listed(), [str(self.unrelated.id)])
            self.assertEqual(self._opens(self.unrelated), 200)
            self.assertEqual(self._opens(self.hosted), 404)

    def test_tenant_module_without_the_attribute_uses_default(self):
        from cis.services import tenant_services
        with mock.patch.object(tenant_services, 'get_tenant_service',
                               return_value=types.ModuleType('hs')):
            self.assertEqual(self._listed(), [str(self.hosted.id)])
