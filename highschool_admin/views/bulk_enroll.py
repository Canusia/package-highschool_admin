import csv
import io
import uuid

from django import forms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from cis.menu import draw_menu
from .utils import get_hsadmin_menu
from cis.models.bulk_enroll import BulkEnrollBatch
from cis.models.section import ClassSection
from cis.models.term import Term
from cis.services.tenant_services import get_tenant_service
from cis.utils import is_student_registration_open, registration_terms
from .utils import get_user_highschools

# BulkEnroller lives in the tenant-configs app (settings.TENANT_SERVICES_APP),
# resolved here the same way cis/ethos resolve sis_importer / ethos_identity.
_bulk_enroller = get_tenant_service('bulk_enroller')
BulkEnroller = _bulk_enroller.BulkEnroller
EMAIL_HEADER = _bulk_enroller.EMAIL_HEADER
build_report = _bulk_enroller.build_report

TEMPLATE = 'highschool_admin/bulk_enroll.html'


class BulkEnrollUploadForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'accept': 'text/csv'}))


def _terms():
    terms = registration_terms()
    if not terms:
        terms = Term.objects.all()
    return terms


def _safe_uuid(value):
    """Return a UUID for a well-formed value, else None. Guards query/POST
    params that feed UUID PK lookups so malformed input is ignored (404/empty)
    rather than raising ValidationError -> 500."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _scoped_sections(request, term):
    if term is None:
        return ClassSection.objects.none()
    return ClassSection.objects.filter(
        term=term, status='A',
        highschool__in=get_user_highschools(request),
    ).order_by('course__name', 'section_number')


def _resolve_term(request, terms):
    term_id = _safe_uuid(request.POST.get('term') or request.GET.get('term'))
    if term_id:
        return get_object_or_404(Term, pk=term_id)
    return terms.first() if terms else None


def _base_context(request, **extra):
    ctx = {
        'menu': draw_menu(get_hsadmin_menu(), 'bulk_enroll', '', 'highschool_admin'),
        'registration_open': is_student_registration_open(),
    }
    ctx.update(extra)
    return ctx


def bulk_enroll(request):
    terms = _terms()
    term = _resolve_term(request, terms)
    sections = _scoped_sections(request, term)

    if request.method == 'POST' and request.FILES.get('file'):
        if not is_student_registration_open():
            return render(request, TEMPLATE, _base_context(
                request, terms=terms, term=term, sections=sections,
                upload_form=BulkEnrollUploadForm(),
                error='Registration is currently closed; no students were enrolled.'))

        chosen_ids = [u for u in (
            _safe_uuid(s) for s in request.POST.getlist('sections')) if u]
        chosen = sections.filter(id__in=chosen_ids)
        if not chosen.exists():
            return render(request, TEMPLATE, _base_context(
                request, terms=terms, term=term, sections=sections,
                upload_form=BulkEnrollUploadForm(),
                error='Select at least one section.'))

        decoded = request.FILES['file'].read().decode('utf-8-sig', errors='ignore')
        reader = csv.DictReader(io.StringIO(decoded))
        enroller = BulkEnroller(get_user_highschools(request), created_by=request.user)
        header_errors = enroller.header_errors(reader.fieldnames)
        if header_errors:
            return render(request, TEMPLATE, _base_context(
                request, terms=terms, term=term, sections=sections,
                upload_form=BulkEnrollUploadForm(), header_errors=header_errors))

        batch = enroller.parse_into_batch(
            reader, sections=list(chosen), term=term,
            source_filename=request.FILES['file'].name)
        return redirect('highschool_admin:bulk_enroll_preview', batch_id=batch.id)

    return render(request, TEMPLATE, _base_context(
        request, terms=terms, term=term, sections=sections,
        upload_form=BulkEnrollUploadForm()))


def bulk_enroll_preview(request, batch_id):
    batch = get_object_or_404(BulkEnrollBatch, pk=batch_id, created_by=request.user)
    return render(request, TEMPLATE, _base_context(
        request, batch=batch, rows=batch.rows.all()))


def bulk_enroll_confirm(request, batch_id):
    if request.method != 'POST':
        return redirect('highschool_admin:bulk_enroll_preview', batch_id=batch_id)
    batch = get_object_or_404(BulkEnrollBatch, pk=batch_id, created_by=request.user)
    if batch.status == 'committed':
        summary = {'created': 0, 'skipped': batch.rows.count(), 'failed': 0}
    else:
        enroller = BulkEnroller(get_user_highschools(request), created_by=request.user)
        summary = enroller.commit(batch, request.POST.getlist('selected_rows'))
    return render(request, TEMPLATE, _base_context(
        request, batch=batch, rows=batch.rows.all(), summary=summary, committed=True))


def bulk_enroll_report(request, batch_id):
    batch = get_object_or_404(BulkEnrollBatch, pk=batch_id, created_by=request.user)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="bulk_enroll_report_%s.csv"' % batch_id)
    writer = csv.writer(response)
    for line in build_report(batch):
        writer.writerow(line)
    return response


def bulk_enroll_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="bulk_enroll_template.csv"'
    csv.writer(response).writerow([EMAIL_HEADER])
    return response
