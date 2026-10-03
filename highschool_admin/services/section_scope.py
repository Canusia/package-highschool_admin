"""Which class sections an HS admin may see (#3).

One predicate for both the Classes list and the class-section detail guard,
so a section that is listed always opens and one that isn't always 404s.

Resolution order:

1. A tenant override: ``visible_sections(request, highschools)`` in the tenant
   services app's ``services/highschool_admin.py``, found through
   ``cis.services.tenant_services.get_tenant_override``.
2. The built-in rule named by ``MY_CE['highschool_admin']['class_section_scope']``:
   ``'hosted'`` (default) or ``'hosted_or_own_students'``.
"""
import logging

from django.conf import settings
from django.db.models import Q

from cis.models.section import ClassSection, StudentRegistration

logger = logging.getLogger(__name__)

HOSTED = 'hosted'
HOSTED_OR_OWN_STUDENTS = 'hosted_or_own_students'


def hosted(request, highschools):
    """Sections hosted at the admin's high schools (the original rule)."""
    return ClassSection.objects.filter(highschool__in=highschools)


def hosted_or_own_students(request, highschools):
    """Hosted sections, plus sections the admin's own students are registered in.

    For consortium enrollment, where a student registers for a course hosted by
    another school. Registrations of any status count. A subquery rather than a
    join, so a section is listed once however many of the school's students are in it.
    """
    student_sections = StudentRegistration.objects.filter(
        student__highschool__in=highschools).values('class_section_id')
    return ClassSection.objects.filter(
        Q(highschool__in=highschools) | Q(pk__in=student_sections))


BUILT_IN_RULES = {
    HOSTED: hosted,
    HOSTED_OR_OWN_STUDENTS: hosted_or_own_students,
}


def configured_rule_name():
    config = (getattr(settings, 'MY_CE', None) or {}).get('highschool_admin') or {}
    return config.get('class_section_scope') or HOSTED


def _tenant_override():
    try:
        from cis.services.tenant_services import get_tenant_override
    except ImportError:  # pragma: no cover - cis without the seam
        return None
    if not getattr(settings, 'TENANT_SERVICES_APP', None):
        return None
    return get_tenant_override('highschool_admin', 'visible_sections')


def visible_sections(request):
    """ClassSection queryset the current HS admin may list and open."""
    from ..views.utils import get_user_highschools

    highschools = get_user_highschools(request)

    override = _tenant_override()
    if override is not None:
        return override(request, highschools)

    name = configured_rule_name()
    rule = BUILT_IN_RULES.get(name)
    if rule is None:
        logger.warning('Unknown class_section_scope %r; using %r', name, HOSTED)
        rule = hosted
    return rule(request, highschools)
