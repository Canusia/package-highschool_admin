"""Bulk per-student document upload for a term (#6).

The per-student path (student page, Supporting Documents tab) already stores
StudentSupportingDocument rows through cis's StudentSupportingDocumentForm.
This is a second entry point to the same form and model: pick a term and a
document type once, then attach a file to any number of the admin's students
on one page. Each file posts on its own (one request per student), so a school
sending hundreds of transcripts never builds one giant request, and one bad
file does not cost the others.

Scope is enforced on every upload: the student must be at one of the admin's
high schools (get_user_highschools), not merely absent from the dropdown.
"""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from cis.forms.student import StudentSupportingDocumentForm
from cis.menu import draw_menu
from cis.models.section import StudentRegistration
from cis.models.student import Student, StudentSupportingDocument
from cis.models.term import Term
from cis.utils import active_term

from .utils import get_hsadmin_menu, get_user_highschools


def _term_from(value):
    if not value:
        return None
    try:
        return Term.objects.filter(pk=value).first()
    except Exception:  # malformed UUID
        return None


def document_types(term):
    """The CE-configured upload vocabulary for this term (shared with the student page)."""
    return StudentSupportingDocumentForm._document_type_labels(term)


@xframe_options_exempt
def student_documents(request):
    """Pick a term + document type, then attach files to students on one page.

    Exempt from X-Frame-Options, like the student page, so it can open inside
    the portal's iframe modal.
    """
    term = _term_from(request.GET.get('term')) or active_term()
    include_all = request.GET.get('all') == '1'
    highschools = get_user_highschools(request)

    students = Student.objects.filter(highschool__in=highschools)
    if not include_all and term is not None:
        registered = StudentRegistration.objects.filter(
            class_section__term=term).values('student_id')
        students = students.filter(pk__in=registered)
    students = students.select_related('user', 'highschool').order_by(
        'user__last_name', 'user__first_name')

    existing = {}
    if term is not None:
        for doc in StudentSupportingDocument.objects.filter(
                term=term, student__in=students).order_by('uploaded_on'):
            existing.setdefault(doc.student_id, []).append(doc)

    rows = [{'student': s, 'documents': existing.get(s.id, [])} for s in students]

    return render(request, 'highschool_admin/student_documents.html', {
        'menu': draw_menu(get_hsadmin_menu(), 'students', '', 'highschool_admin'),
        'terms': Term.objects.all().order_by('-code'),
        'term': term,
        'include_all': include_all,
        'document_types': document_types(term) if term else [],
        'rows': rows,
    })


@require_POST
def upload_student_document(request):
    """Store one student's file. JSON in, JSON out; 404 for a student outside scope."""
    student_id = request.POST.get('student')
    student = None
    if _is_uuid(student_id):
        student = Student.objects.filter(
            pk=student_id, highschool__in=get_user_highschools(request)).first()
    if student is None:
        return JsonResponse({'status': 'error', 'message': 'Student not found.'}, status=404)

    term = _term_from(request.POST.get('term'))
    if term is None:
        return JsonResponse({'status': 'error', 'message': 'Choose a term.'}, status=400)

    types = document_types(term)
    document_type = request.POST.get('document_type', '')
    if types and document_type not in types:
        return JsonResponse(
            {'status': 'error', 'message': 'Choose a document type.'}, status=400)

    form = StudentSupportingDocumentForm(
        student, term=term,
        data={
            'action': 'upload_support_doc',
            'student': str(student.id),
            'term': str(term.id),
            'document_type': document_type,
            'description': request.POST.get('description', ''),
        },
        files=request.FILES,
    )
    if not form.is_valid():
        return JsonResponse({
            'status': 'error',
            'message': '; '.join(
                f'{field}: {" ".join(str(e) for e in errors)}'
                for field, errors in form.errors.items()),
        }, status=400)

    doc = form.save(commit=False)
    doc.student = student  # the scoped lookup above, never the posted hidden field
    doc.term = term
    doc.save()
    student.add_note(request.user, 'Uploaded supporting doc ' + doc.filename)
    return JsonResponse({'status': 'success', 'message': f'Uploaded {doc.filename}.',
                         'filename': doc.filename})


def _is_uuid(value):
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False
