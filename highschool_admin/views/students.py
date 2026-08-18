from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.views.decorators.clickjacking import xframe_options_exempt

from cis.models.student import (
    Student, StudentRecommendation, StudentSupportingDocument,
)
from cis.models.section import StudentRegistration
from cis.models.term import Term
from cis.menu import draw_menu
from cis.forms.student import (
    StudentRecommendationForm, StudentSupportingDocumentForm,
)
from cis.services.table_configs import get_table_config
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang
from cis.utils import registration_terms, active_term

from ..services.registration import (
    can_manage_recommendation, recommendation_registrations,
)
from .utils import get_current_hsadmin, get_user_highschools, get_hsadmin_menu
from ..settings.student_tabs import student_tabs


@xframe_options_exempt
def student(request, record_id):
    """Individual student detail page with recommendations."""
    user = get_current_hsadmin(request)
    menu = draw_menu(get_hsadmin_menu(), 'students', '', 'highschool_admin')
    record = get_object_or_404(
        Student, pk=record_id,
        highschool__in=get_user_highschools(request),
    )
    # `or []`: registration_terms() returns None when the setting row is
    # absent, and the loop below iterates it. Same guard cis applies in
    # StudentRecommendation.has_recommendation.
    current_registration_terms = registration_terms() or []

    # get all registered classes
    registered_classes = StudentRegistration.objects.filter(
        student=record
    )

    support_doc_form = StudentSupportingDocumentForm(record)

    # This will store term keyed recommendation form instance
    # if a form is submitted. This is used to prevent reinitializing
    # rec form instance further down in the method
    submitted_rec_form = {}

    # `record` is already scoped to the admin's schools by the lookup above;
    # this is the second, finer gate. Which school it keys to is tenant policy
    # -- see can_manage_recommendation.
    can_recommend = can_manage_recommendation(user, record)

    support_docs_url = reverse(
        'highschool_admin:student', args=[record.id]) + '#support_docs'

    # Supporting-document upload / delete (own tab). Handled before the
    # recommendation POST below so the two forms don't collide.
    if request.method == 'POST' and request.POST.get('action') == 'upload_support_doc':
        support_doc_form = StudentSupportingDocumentForm(
            record, data=request.POST, files=request.FILES)
        if support_doc_form.is_valid():
            doc = support_doc_form.save(commit=False)
            doc.student = record  # enforce scope; ignore any tampered hidden field
            doc.save()
            record.add_note(request.user, 'Uploaded supporting doc ' + doc.filename)
            messages.add_message(
                request, messages.SUCCESS,
                'Successfully uploaded supporting document.',
                'list-group-item-success')
            return redirect(support_docs_url)
        messages.add_message(
            request, messages.SUCCESS,
            'Please correct the errors and try again.',
            'list-group-item-danger')

    elif request.method == 'POST' and request.POST.get('action') == 'delete_support_doc':
        doc = StudentSupportingDocument.objects.filter(
            student=record, id=request.POST.get('id')).first()
        if doc:
            filename = doc.filename
            doc.delete()
            record.add_note(request.user, 'Deleted supporting doc ' + filename)
            messages.add_message(
                request, messages.SUCCESS,
                'Deleted supporting document.',
                'list-group-item-success')
        return redirect(support_docs_url)

    if request.method == 'POST' and request.POST.get('action') not in (
            'upload_support_doc', 'delete_support_doc'):
        # Refuse the whole POST before any write. recommendation_form.save()
        # writes the StudentRecommendation *and* flips each registration's
        # status, so a gate applied per-registration would still let the
        # recommendation record itself through.
        if not can_recommend:
            messages.add_message(
                request, messages.SUCCESS,
                'You do not have permission to submit recommendations for this student.',
                'list-group-item-danger')
            return redirect('highschool_admin:student', record_id=record.id)

        rec_registrations = recommendation_registrations(record)
        recommendation_form = StudentRecommendationForm(
            record, rec_registrations, request.POST, request.FILES)

        if recommendation_form.is_valid():
            recommendation_form.save(
                request, record, rec_registrations, set_reviewer=True,
                reviewer=get_current_hsadmin(request))
            messages.add_message(
                request, messages.SUCCESS,
                'Successfully submitted recommendation.', 'list-group-item-success')
            return redirect('highschool_admin:student', record_id=record.id)
        else:
            messages.add_message(
                request, messages.SUCCESS,
                'Unable to complete your request. Please review the form and try again.',
                'list-group-item-danger')
            submitted_rec_form['unified'] = recommendation_form

    rec_registrations = recommendation_registrations(record).order_by(
        'class_section__term__label')

    initial = {
        'student': record.id,
        'student_state_id': record.state_id,
        'student_bridge': '2',
    }
    # The Pre-Upload Blurb is configuration, not per-recommendation data. It
    # used to be set only inside the `if existing:` branch below, so it
    # rendered blank on a counselor's first visit to a student (ewu#46).
    initial['upload_label'] = StudentRecommendation.get_form_message()

    # Derived from the record or from configuration, so they win over anything
    # in the stored blob.
    view_owned = {'student', 'student_state_id', 'upload_label'}

    existing = None
    for term in current_registration_terms:
        if record.has_recommendation(term.id):
            existing = record.get_recommendation(term.id)
            break
    if existing:
        # Prefill follows the tenant form's own declared fields. A fixed list
        # here carried one tenant's Pennsylvania vocabulary (Keystone Exam,
        # PSSA, GEIP), so any tenant whose rec form declares different fields
        # got them rendered blank on reopen -- and silently overwritten on the
        # next submit, since the blank control still validates. The form is
        # resolved through get_tenant_service('recommendation_form'), so its
        # base_fields are the tenant's contract and this needs no knowledge of
        # any tenant's names (ewu#46).
        stored = existing.recommendation or {}
        initial.update({
            name: stored[name]
            for name in StudentRecommendationForm.base_fields
            if name in stored and name not in view_owned
        })

    if submitted_rec_form.get('unified'):
        recommendation_form = submitted_rec_form['unified']
        recommendation_form.fields['upload_label'].label = StudentRecommendation.get_form_message()
    else:
        recommendation_form = StudentRecommendationForm(
            student=record, current_registrations=rec_registrations, initial=initial)

    return render(
        request,
        'highschool_admin/student.html',
        {
            'menu': menu,
            'record': record,
            'classes': registered_classes,
            'registrations_table': get_table_config('registrations_table').build_config(
                variant='hs_student_detail',
                api_url=(f'/highschool_admin/api/student-registrations/'
                         f'?format=datatables&student={record.id}'),
            ),
            'recommendation_form': recommendation_form,
            'recommendation_registrations': rec_registrations,
            'can_recommend': can_recommend,
            'intro': portal_lang(request).from_db().get('student_blurb', 'Change me'),
            'notes_api_url': f'/highschool_admin/api/student_notes/?format=datatables&student_id={record.id}',
            'support_doc_form': support_doc_form,
            'support_docs': StudentSupportingDocument.objects.filter(
                student=record).order_by('-uploaded_on'),
            'tab_setting': student_tabs.tabs(),
        })


def students(request):
    """Students list page."""
    return render(
        request,
        'highschool_admin/students-rec.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'students', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('students_blurb', 'Change me'),
            'terms': Term.objects.all().order_by('-code'),
            'active_term': active_term(),
            'tab_setting': student_tabs.tabs(),
        })


def student_notes(request):
    """Student notes list page."""
    return render(
        request,
        'highschool_admin/student_notes.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'notes', '', 'highschool_admin'),
            'terms': Term.objects.all().order_by('-code'),
            'active_term': active_term(),
            'intro': portal_lang(request).from_db().get('notes_blurb', 'Change me'),
            'api_url': '/highschool_admin/api/student_notes/?format=datatables',
        })
