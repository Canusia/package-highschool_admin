"""Note visibility for the HS-admin portal, with an opt-in tenant override.

Which note types a counselor may read is tenant visibility policy. It was
hardcoded as ``meta__type__contains='to_counselor'`` twice inside a single
method — ``StudentNoteViewSet.get_queryset``, once for the student-scoped
branch and once for the school-wide one — so the two could drift apart, and a
tenant using a different marker had no seam at all.

A tenant opts out of the default by defining ``hsadmin_visible_note_types()``
in its ``services/notes.py``. As with the registration overrides, the name is
prefixed: this governs what *this portal* shows counselors, not note
visibility generally.
"""
from django.db.models import Q

DEFAULT_HSADMIN_NOTE_TYPES = ('to_counselor',)


def hsadmin_visible_note_types():
    """Note-type markers an HS admin may read. Fresh list each call."""
    # Imported inside the function: a tenant's services module imports
    # cis.models.* at its own module level, so resolving one during a cis model
    # import risks AppRegistryNotReady.
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override('notes', 'hsadmin_visible_note_types')
    if override is not None:
        return list(override())

    return list(DEFAULT_HSADMIN_NOTE_TYPES)


def hsadmin_visible_notes_q():
    """The visible-note-type filter, as a Q for StudentNote querysets.

    An empty type list means "counselors see no notes". It must therefore
    produce a match-nothing Q — a bare ``Q()`` is the identity for AND and
    would widen the queryset to every note in scope, turning a lockdown into a
    disclosure.
    """
    types = hsadmin_visible_note_types()
    if not types:
        return Q(pk__in=[])

    q = Q(meta__type__contains=types[0])
    for note_type in types[1:]:
        q |= Q(meta__type__contains=note_type)
    return q
