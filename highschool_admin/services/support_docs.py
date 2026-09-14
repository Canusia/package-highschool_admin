"""Supporting Documents tab tenant seam for the HS-admin student page.

The tab is package markup; a tenant adds content above the documents table
(for example, which documents are still pending for the student's course
requests) by overriding ``highschool_admin/_support_docs_extra.html`` from its
project ``templates/`` dir. The package ships that template empty, so tenants
without an override see no change.

Deciding *what* is pending is tenant logic the template cannot do on its own,
so the view also resolves an opt-in hook: ``hsadmin_support_docs_extra`` in the
tenant's ``services/required_documents.py``. Its return value reaches the
include as ``support_docs_extra``. The name is prefixed because the module is
tenant-owned and may serve other surfaces (TVCC's recommendation form reads the
same module).
"""


def support_docs_extra(student, registrations, support_docs, support_docs_url):
    """Tenant-supplied context for ``_support_docs_extra.html`` ({} by default).

    The hook is called with keyword arguments::

        def hsadmin_support_docs_extra(*, student, registrations,
                                       support_docs, support_docs_url): ...

    ``registrations`` are the student's registrations in the current
    registration terms; ``support_docs`` are the student's existing
    ``StudentSupportingDocument`` rows; ``support_docs_url`` links back to the
    tab, for upload shortcuts. Return a dict, or None for nothing.
    """
    # Imported inside the function: a tenant's services module imports
    # cis.models.* at module level (see services/registration.py).
    from cis.services.tenant_services import get_tenant_override

    override = get_tenant_override(
        'required_documents', 'hsadmin_support_docs_extra')
    if override is None:
        return {}
    return override(
        student=student, registrations=registrations,
        support_docs=support_docs, support_docs_url=support_docs_url,
    ) or {}
