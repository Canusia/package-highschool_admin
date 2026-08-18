"""Recommendation scope and permission are tenant policy.

cis already exposes `needs_recommendation` / `has_recommendation` /
`student_needs_recommendation` as overrides, but the student-detail view
reimplemented the policy *around* them inline: which registrations a
recommendation covers (registration_terms()-filtered) and whether the caller
may recommend for this student (keyed to the STUDENT's high school rather than
the section's host school -- a deliberate choice, and therefore one another
tenant could reasonably invert).

Defaults are unchanged.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from ..services.registration import (
    can_manage_recommendation, recommendation_registrations,
)


class CanManageRecommendationTests(SimpleTestCase):
    def test_default_delegates_to_the_students_school(self):
        student = MagicMock()
        student.highschool.id = 7
        hsadmin = MagicMock()
        hsadmin.can_manage_student_recommendation.return_value = True
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertTrue(can_manage_recommendation(hsadmin, student))
        hsadmin.can_manage_student_recommendation.assert_called_once_with(7)

    def test_default_passes_none_when_student_has_no_school(self):
        student = MagicMock()
        student.highschool = None
        hsadmin = MagicMock()
        hsadmin.can_manage_student_recommendation.return_value = False
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            can_manage_recommendation(hsadmin, student)
        hsadmin.can_manage_student_recommendation.assert_called_once_with(None)

    def test_anonymous_caller_is_denied_without_consulting_the_model(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None):
            self.assertFalse(can_manage_recommendation(None, MagicMock()))

    def test_tenant_override_wins(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda user, student: True):
            self.assertTrue(can_manage_recommendation(None, MagicMock()))

    def test_override_is_looked_up_under_an_hsadmin_scoped_name(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None) as gto:
            can_manage_recommendation(MagicMock(), MagicMock())
        gto.assert_called_once_with(
            'registration', 'hsadmin_can_manage_recommendation')


class RecommendationRegistrationsTests(TestCase):
    def test_default_scopes_to_registration_terms(self):
        student = MagicMock()
        terms = [MagicMock()]
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None), \
             patch(f'{recommendation_registrations.__module__}.registration_terms',
                   return_value=terms), \
             patch('cis.models.section.StudentRegistration.objects') as manager:
            recommendation_registrations(student)
        manager.filter.assert_called_once_with(
            student=student, class_section__term__in=terms)

    def test_unset_registration_terms_yields_nothing_rather_than_raising(self):
        """registration_terms() returns None -- not an empty queryset -- when
        the setting row is absent. Passing that straight into __in raises
        TypeError, which the view surfaced as a 500 on any tenant that had not
        configured registration terms yet. cis fixed the same trap in
        StudentRecommendation.has_recommendation."""
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None), \
             patch(f'{recommendation_registrations.__module__}.registration_terms',
                   return_value=None), \
             patch('cis.models.section.StudentRegistration.objects') as manager:
            recommendation_registrations(MagicMock())
        _, kwargs = manager.filter.call_args
        self.assertEqual(list(kwargs['class_section__term__in']), [])

    def test_tenant_override_wins(self):
        sentinel = object()
        student = MagicMock()
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=lambda s: sentinel):
            self.assertIs(recommendation_registrations(student), sentinel)

    def test_override_is_looked_up_under_an_hsadmin_scoped_name(self):
        with patch('cis.services.tenant_services.get_tenant_override',
                   return_value=None) as gto, \
             patch(f'{recommendation_registrations.__module__}.registration_terms',
                   return_value=[]), \
             patch('cis.models.section.StudentRegistration.objects'):
            recommendation_registrations(MagicMock())
        gto.assert_called_once_with(
            'registration', 'hsadmin_recommendation_registrations')
