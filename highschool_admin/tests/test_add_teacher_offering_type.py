"""The add-teacher offering filter must not be fed the tenant's course_type.

`future_sections` renamed this wire parameter to `offering_type` because the
add-teacher form now carries a *tenant-configured* `course_type` select of its
own (ewu: articulated / dual / cpl), and the two collide in the POST body --
see the comment in future_sections/js/future_sections.js and the
AddNewTeacherForm.__init__ docstring. This portal still sent and read
`course_type`, so on submit the user's answer to "Type of course" was passed
through as the course-list filter.

`pathways` / `cccl` / `facilitator` are portal vocabulary and stay hardcoded;
only the parameter name and the POST-body read are wrong.
"""
import os
import re
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from . import PKG


class OfferingTypeResolutionTests(SimpleTestCase):
    def _captured_offering_type(self, method, get_params, post_data=None):
        from ..views.api.viewsets import FutureSectionsActionViewSet

        seen = {}

        class _Errors(dict):
            def as_json(self):
                return '{}'

        class _Form:
            def __init__(self, request, academic_year, offering_type,
                         *args, **kwargs):
                seen['offering_type'] = offering_type
                self.errors = _Errors()

            def is_valid(self):
                return False

        request = MagicMock()
        request.method = method
        request.GET = get_params
        request.data = post_data or {}
        request.POST = post_data or {}

        view = FutureSectionsActionViewSet()
        with patch(f'{PKG}.views.api.viewsets.AddNewTeacherForm', _Form), \
             patch(f'{PKG}.views.api.viewsets.get_object_or_404',
                   return_value=MagicMock()), \
             patch(f'{PKG}.views.api.viewsets._get_fs_config', return_value={}), \
             patch(f'{PKG}.views.api.viewsets.render', return_value=MagicMock()):
            view.add_teacher(request)
        return seen.get('offering_type')

    def test_get_reads_offering_type(self):
        self.assertEqual(
            self._captured_offering_type(
                'GET', {'academic_year_id': 'ay', 'offering_type': 'facilitator'}),
            'facilitator')

    def test_get_still_accepts_the_legacy_course_type_param(self):
        """Older cached pages and bookmarked URLs still send course_type."""
        self.assertEqual(
            self._captured_offering_type(
                'GET', {'academic_year_id': 'ay', 'course_type': 'cccl'}),
            'cccl')

    def test_get_defaults_to_pathways(self):
        self.assertEqual(
            self._captured_offering_type('GET', {'academic_year_id': 'ay'}),
            'pathways')

    def test_post_ignores_the_forms_tenant_course_type_field(self):
        """The regression: the form posts course_type='articulated' (a tenant
        value); it must not become the offering filter."""
        self.assertEqual(
            self._captured_offering_type(
                'POST', {'academic_year_id': 'ay'},
                {'academic_year_id': 'ay', 'course_type': 'articulated'}),
            'pathways')

    def test_post_takes_offering_type_from_the_form_action_query_string(self):
        """The rendered form's action URL is request.build_absolute_uri() from
        the GET, so the offering type rides its query string."""
        self.assertEqual(
            self._captured_offering_type(
                'POST', {'academic_year_id': 'ay', 'offering_type': 'cccl'},
                {'academic_year_id': 'ay', 'course_type': 'articulated'}),
            'cccl')

    def test_post_body_may_still_carry_an_explicit_offering_type(self):
        self.assertEqual(
            self._captured_offering_type(
                'POST', {'academic_year_id': 'ay'},
                {'academic_year_id': 'ay', 'offering_type': 'facilitator',
                 'course_type': 'articulated'}),
            'facilitator')


class ClientSendsOfferingTypeTests(SimpleTestCase):
    JS = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'staticfiles', 'highschool_admin', 'js', 'future_sections.js')

    def test_js_sends_offering_type_not_course_type(self):
        with open(self.JS, encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn("data['course_type']", source)
        for value in ('cccl', 'facilitator', 'pathways'):
            self.assertIn(f"data['offering_type'] = '{value}'", source)


class SerializerNamesTheParameterTests(SimpleTestCase):
    def test_request_serializer_documents_offering_type(self):
        from ..views.api.serializers import AddTeacherRequestSerializer
        fields = AddTeacherRequestSerializer().fields
        self.assertIn('offering_type', fields)
        self.assertNotIn('course_type', fields)
        self.assertEqual(
            sorted(dict(fields['offering_type'].choices)),
            ['cccl', 'facilitator', 'pathways'])
