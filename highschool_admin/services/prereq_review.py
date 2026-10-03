"""Read-only view of the college's prerequisite review, for HS admins (#7).

The CE office records, per student per term, whether the transcript was
received and which test score is still needed, and, per class, whether the
prerequisite is met. Those values live in the tenant's ``prereq_tracking``
service (e.g. RVCC's ``myce_tenant_configs/services/prereq_tracking.py``),
which owns the storage shape. This module only *reads* them through that
service's public accessors and never writes.

Exactly three values ever leave here: ``transcript_received``, ``prereq_met``
and ``test_score_needed``. Anything else the service stores (the CE-internal
``note``, audit stamps) is never passed to a high school.

A tenant without the service gets ``None`` everywhere, and the portal shows nothing.
"""
from django.conf import settings

FLAGS = ('transcript_received', 'prereq_met', 'test_score_needed')
SERVICE = 'prereq_tracking'


def tracking_service():
    """The tenant's prereq_tracking module, or None when it has none."""
    app = getattr(settings, 'TENANT_SERVICES_APP', None)
    if not app:
        return None
    try:
        from cis.services.tenant_services import get_tenant_service
        module = get_tenant_service(SERVICE)
    except ModuleNotFoundError as exc:
        # Only a missing module means "no service". An ImportError raised
        # inside an existing module is a real breakage and propagates.
        if exc.name in (f'{app}.services.{SERVICE}', f'{app}.services', app):
            return None
        raise
    return module if hasattr(module, 'get_review') else None


def _display_test_score(service, value):
    display = getattr(service, 'test_score_display', None)
    return display(value) if display else (value or '')


def registration_flags(service, registration):
    """The three flags for one registration (its term's values + its own prereq_met)."""
    student = registration.student
    term = registration.class_section.term
    term_review = service.get_review(student, term) or {}
    per_class = {}
    if hasattr(service, 'get_registration_review'):
        per_class = service.get_registration_review(student, term, registration) or {}
    return {
        'transcript_received': term_review.get('transcript_received', '') or '',
        # Per-class when recorded; a term-level value is the older layout.
        'prereq_met': per_class.get('prereq_met') or term_review.get('prereq_met', '') or '',
        'test_score_needed': _display_test_score(
            service, term_review.get('test_score_needed', '')),
    }


def student_review(service, registrations):
    """Rows for the student page, grouped by term, newest term first.

    ``[{'term': term, 'transcript_received': ..., 'test_score_needed': ...,
        'classes': [{'registration': r, 'prereq_met': ...}, ...]}, ...]``
    """
    by_term = {}
    for registration in registrations:
        term = registration.class_section.term
        flags = registration_flags(service, registration)
        entry = by_term.setdefault(term.id, {
            'term': term,
            'transcript_received': flags['transcript_received'],
            'test_score_needed': flags['test_score_needed'],
            'classes': [],
        })
        entry['classes'].append({'registration': registration,
                                 'prereq_met': flags['prereq_met']})
    return sorted(by_term.values(), key=lambda e: e['term'].code or '', reverse=True)
