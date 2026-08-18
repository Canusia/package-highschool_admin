"""Registration policy for the HS-admin portal, with an opt-in tenant override.

Which registration statuses count as "still awaiting counselor action" is
tenant vocabulary, not a fixed rule. It was written out as
``status__in=['applied']`` in three places — the Pending Review tab, the
Pending Pay Type feed and the dashboard pay-type message — so a tenant with a
different status set had to find all three, and missing one left a screen
quietly showing the wrong rows instead of failing.

One resolver now feeds all three. A tenant opts out of the default by defining
``hsadmin_pending_review_statuses()`` in its ``services/registration.py`` — the
module that already holds the cis-side registration overrides
(``needs_recommendation``, ``get_pending_recommendations``, …). The name is
prefixed because that module is shared with cis: an unprefixed
``pending_review_statuses`` would read as a cis-wide rule when it governs only
this portal.

Deliberately one knob for both the review and pay-type surfaces: their shared
meaning is "the counselor still has something to do with this registration",
and keeping them in lockstep is the point. A tenant that genuinely needs them
to diverge should split this into two overrides rather than reintroduce a
second literal.
"""

from cis.utils import registration_terms

DEFAULT_PENDING_REVIEW_STATUSES = ('applied',)


def pending_review_statuses():
    """Registration statuses the HS-admin portal treats as pending.

    Returns a fresh list each call, so a caller passing it into a queryset
    cannot mutate the default for everyone else.
    """
    # Imported inside the function, matching the cis idiom: a tenant's services
    # module imports cis.models.* at its own module level, so resolving one
    # while a cis model module is still importing risks AppRegistryNotReady.
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override(
        'registration', 'hsadmin_pending_review_statuses')
    if override is not None:
        return list(override())

    return list(DEFAULT_PENDING_REVIEW_STATUSES)


def can_update_pay_type(registration, user):
    """Whether ``user`` may edit this registration's pay type.

    The endpoint already enforces the PT-18 scope guard (the registration
    belongs to a school the caller administers) and the global
    ``is_pay_type_review_open()`` window. This is the per-registration seam on
    top of those: a tenant that limits pay-type edits to applied registrations,
    or to the current registration terms, defines
    ``hsadmin_can_update_pay_type(registration, user)`` in its
    ``services/registration.py``.

    Defaults to True — the behaviour before this seam existed.
    """
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override('registration', 'hsadmin_can_update_pay_type')
    if override is not None:
        return bool(override(registration, user))

    return True


def can_manage_recommendation(user, student):
    """Whether ``user`` (an HSAdministrator, or None) may file a recommendation
    for ``student``.

    The default keys the permission to the STUDENT's high school, not the
    section's host high school — those differ when a student takes a section
    hosted elsewhere, and the recommendation belongs to the school the student
    attends. That is a deliberate tenant-specific reading, so a tenant that
    keys it to the host school instead defines
    ``hsadmin_can_manage_recommendation(user, student)`` in its
    ``services/registration.py``.

    Callers must still scope the student itself to the caller's schools; this
    is the second, finer gate, not a replacement for that lookup.
    """
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override(
        'registration', 'hsadmin_can_manage_recommendation')
    if override is not None:
        return bool(override(user, student))

    if not user:
        return False
    return bool(user.can_manage_student_recommendation(
        student.highschool.id if student.highschool else None))


def recommendation_registrations(student):
    """Registrations a recommendation filed now would cover.

    Default: the student's registrations in the open registration terms. A
    tenant scoping recommendations differently — by status, by course, by a
    single term — defines ``hsadmin_recommendation_registrations(student)`` in
    its ``services/registration.py``.

    Callers add their own ordering; this returns an unordered queryset.
    """
    from cis.models.section import StudentRegistration
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override(
        'registration', 'hsadmin_recommendation_registrations')
    if override is not None:
        return override(student)

    # `registration_terms()` returns None — not an empty queryset — when the
    # registrations setting row is absent, and None passed to __in raises
    # TypeError. No open term means nothing to recommend for. cis guards the
    # same trap in StudentRecommendation.has_recommendation.
    return StudentRegistration.objects.filter(
        student=student,
        class_section__term__in=registration_terms() or [],
    )
