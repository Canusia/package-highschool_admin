import csv
import io

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from cis.menu import draw_menu
from .utils import get_hsadmin_menu
from cis.models.student_import import StudentImportBatch
from cis.forms.student_import import StudentImportUploadForm
from cis.services.importers.student_importer import StudentImporter
from cis.services.importers.student_import_schema import StudentImportColumns
from .utils import get_user_highschools

TEMPLATE = 'highschool_admin/student_import.html'
SCOPE = 'highschool_admin'


def _importer(request):
    return StudentImporter(
        highschools=get_user_highschools(request), scope=SCOPE)


def _base_context(request, **extra):
    ctx = {
        'menu': draw_menu(get_hsadmin_menu(), 'student_import', '', 'highschool_admin'),
        'field_definitions': StudentImportColumns.field_definitions(),
        'my_highschools': get_user_highschools(request),
    }
    ctx.update(extra)
    return ctx


def download_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
    csv.writer(response).writerow(StudentImportColumns.headers())
    return response


def student_import(request):
    form = StudentImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        decoded = request.FILES['file'].read().decode('utf-8-sig', errors='ignore')
        reader = csv.DictReader(io.StringIO(decoded))
        importer = _importer(request)
        header_errors = importer.header_errors(reader.fieldnames)
        if header_errors:
            return render(request, TEMPLATE, _base_context(
                request, header_errors=header_errors, upload_form=StudentImportUploadForm()))
        batch = importer.parse_into_batch(
            reader, created_by=request.user, source_filename=request.FILES['file'].name)
        return redirect('highschool_admin:student_import_preview', batch_id=batch.id)
    return render(request, TEMPLATE, _base_context(request, upload_form=form))


def student_import_preview(request, batch_id):
    batch = get_object_or_404(
        StudentImportBatch, pk=batch_id, scope=SCOPE, created_by=request.user)
    return render(request, TEMPLATE, _base_context(
        request, batch=batch, rows=batch.rows.all(),
        confirm_url='highschool_admin:student_import_confirm'))


def student_import_confirm(request, batch_id):
    if request.method != 'POST':
        return redirect('highschool_admin:student_import_preview', batch_id=batch_id)
    batch = get_object_or_404(
        StudentImportBatch, pk=batch_id, scope=SCOPE, created_by=request.user)
    if batch.status == 'committed':
        summary = {'created': 0, 'skipped': batch.rows.count(), 'failed': 0}
    else:
        summary = _importer(request).commit(batch, request.POST.getlist('selected_rows'))
    return render(request, TEMPLATE, _base_context(
        request, batch=batch, rows=batch.rows.all(), summary=summary, committed=True,
        confirm_url='highschool_admin:student_import_confirm'))
