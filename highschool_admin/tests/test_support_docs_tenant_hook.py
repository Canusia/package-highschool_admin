"""Supporting Documents tab tenant seam (package-highschool_admin#11).

A tenant shows extra content (e.g. which documents are still pending for the
student's course requests) above the documents table by overriding
``highschool_admin/_support_docs_extra.html`` from its project templates dir,
optionally fed by ``hsadmin_support_docs_extra`` in its
``services/required_documents.py``.
"""
import copy
import os
import tempfile
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from cis.models.course import Cohort, Course
from cis.models.highschool import HighSchool
from cis.models.section import ClassSection, StudentRegistration
from cis.models.settings import Setting
from cis.models.term import AcademicYear, Term
from two_step.models import TwoStep

from . import PKG
from .test_student_detail_scoping import (
    _NoLoginHistoryMixin, _provision_groups, _provision_menu_setting,
    _make_student, _hs_admin_bound_to,
)

MARKER = 'TENANT-SUPPORT-DOCS-EXTRA'


def _support_docs_pane(html):
    start = html.index('id="support_docs"')
    return html[start:html.index('Upload File', start)]


class SupportDocsTenantHookTests(_NoLoginHistoryMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        _provision_groups()
        _provision_menu_setting()
        # StudentRegistration's save signal writes notes as the `cron` user.
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user(
            username='cron', email='cron@example.com', password='x')
        cls.hs = HighSchool.objects.create(name='HS Hook')
        cls.student = _make_student(cls.hs, 'hook')
        cls.admin = _hs_admin_bound_to('hook', cls.hs)
        ay = AcademicYear.objects.create(name='Hook 2025-2026')
        cls.open_term = Term.objects.create(
            academic_year=ay, code='HKFA', label='Hook Fall')
        cls.closed_term = Term.objects.create(
            academic_year=ay, code='HKSP', label='Hook Spring')
        Setting.objects.update_or_create(
            key=f'{settings.CAMPUS_CODE_PREFIX}_cis_registrations',
            defaults={'value': {'registration_terms': [str(cls.open_term.id)]}})
        cohort = Cohort.objects.create(name='Hook Cohort', designator='HK')
        course = Course.objects.create(
            name='BIOL1408', title='Biology', catalog_number='1408',
            cohort=cohort, credit_hours=4)
        cls.open_reg = StudentRegistration.objects.create(
            student=cls.student, status='applied', status_changed_on={},
            class_section=ClassSection.objects.create(
                class_number='BIOL-1408-CDU09', section_number='CDU09',
                term=cls.open_term, course=course, highschool=cls.hs))
        cls.closed_reg = StudentRegistration.objects.create(
            student=cls.student, status='applied', status_changed_on={},
            class_section=ClassSection.objects.create(
                class_number='BIOL-1408-CDU10', section_number='CDU10',
                term=cls.closed_term, course=course, highschool=cls.hs))

    def setUp(self):
        self.client.force_login(self.admin)
        TwoStep.objects.update_or_create(
            session_id=self.client.session.session_key, user=self.admin,
            defaults={'verification_code': '123456', 'verified': True})

    def _get(self):
        resp = self.client.get(
            reverse('highschool_admin:student', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_default_include_renders_nothing(self):
        resp = self._get()
        self.assertIn('highschool_admin/_support_docs_extra.html',
                      [t.name for t in resp.templates])
        self.assertNotIn(MARKER, resp.content.decode())
        self.assertEqual(resp.context['support_docs_extra'], {})

    def test_context_has_registration_term_registrations_only(self):
        regs = list(self._get().context['support_doc_registrations'])
        self.assertEqual(regs, [self.open_reg])

    def test_tenant_template_override_renders_inside_support_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'highschool_admin'))
            with open(os.path.join(
                    tmp, 'highschool_admin', '_support_docs_extra.html'), 'w') as f:
                f.write(MARKER + ' {{ record.id }} '
                        '{% for r in support_doc_registrations %}'
                        '{{ r.class_section.class_number }}{% endfor %} '
                        '{{ support_docs|length }} {{ support_docs_extra.note }}')
            templates = copy.deepcopy(settings.TEMPLATES)
            templates[0]['DIRS'] = [tmp] + list(templates[0]['DIRS'])
            with override_settings(TEMPLATES=templates), \
                 mock.patch(f'{PKG}.views.students.support_docs_extra',
                            return_value={'note': 'from-service'}):
                pane = _support_docs_pane(self._get().content.decode())
        self.assertIn(
            f'{MARKER} {self.student.id} BIOL-1408-CDU09 0 from-service', pane)


class SupportDocsExtraResolverTests(TestCase):
    def test_defaults_to_empty_dict_without_tenant_override(self):
        from ..services.support_docs import support_docs_extra
        with mock.patch('cis.services.tenant_services.get_tenant_override',
                        return_value=None) as gto:
            self.assertEqual(support_docs_extra(None, [], [], '#support_docs'), {})
        gto.assert_called_once_with(
            'required_documents', 'hsadmin_support_docs_extra')

    def test_tenant_override_receives_arguments_and_wins(self):
        from ..services.support_docs import support_docs_extra
        hook = mock.Mock(return_value={'pending': ['TSI Scores']})
        with mock.patch('cis.services.tenant_services.get_tenant_override',
                        return_value=hook):
            out = support_docs_extra('stu', ['reg'], ['doc'], '/x#support_docs')
        self.assertEqual(out, {'pending': ['TSI Scores']})
        hook.assert_called_once_with(
            student='stu', registrations=['reg'], support_docs=['doc'],
            support_docs_url='/x#support_docs')

    def test_override_returning_none_yields_empty_dict(self):
        from ..services.support_docs import support_docs_extra
        with mock.patch('cis.services.tenant_services.get_tenant_override',
                        return_value=lambda **kw: None):
            self.assertEqual(support_docs_extra(None, [], [], ''), {})
