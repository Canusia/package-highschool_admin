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
    current_registration_terms = registration_terms()

    # get all registered classes
    registered_classes = StudentRegistration.objects.filter(
        student=record
    )

    support_doc_form = StudentSupportingDocumentForm(record)

    # This will store term keyed recommendation form instance
    # if a form is submitted. This is used to prevent reinitializing
    # rec form instance further down in the method
    submitted_rec_form = {}

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
        current_registrations = registered_classes.filter(
            class_section__term__id=request.POST.get('term')
        )

        recommendation_form = StudentRecommendationForm(
            record,
            current_registrations,
            request.POST,
            request.FILES
        )

        if recommendation_form.is_valid():

            for registration in current_registrations:
                if registration.status == 'applied':
                    if request.POST.get(f'registration_{registration.id}'):
                        registration.status = request.POST.get(f'registration_{registration.id}')
                        registration.reviewer = user

                        if registration.status == 'approved':
                            ...
                        elif registration.status == 'not_approved':
                            registration.non_student_pay_amount = 0.00
                            registration.pay_type = 'none'

                        registration.save()

            recommendation = None
            if record.has_recommendation(recommendation_form.cleaned_data['term']):
                recommendation = record.get_recommendation(
                    recommendation_form.cleaned_data['term'])

            if not recommendation:
                recommendation = StudentRecommendation(
                    student=record,
                    term=Term.objects.get(pk=recommendation_form.cleaned_data['term'])
                )
            recommendation.recommendation = {
                'student_gpa': recommendation_form.cleaned_data['student_gpa'],
                'student_grade_level': recommendation_form.cleaned_data['student_grade_level'],
                'student_prereq': recommendation_form.cleaned_data['student_prereq'],
                'grade_earned': recommendation_form.cleaned_data['grade_earned'],
                'school_assessment': recommendation_form.cleaned_data['school_assessment'],
                'keystone_exam': recommendation_form.cleaned_data['keystone_exam'],
                'geip': recommendation_form.cleaned_data['geip'],
                'enrolled_in_honors': recommendation_form.cleaned_data['enrolled_in_honors'],
            }

            if request.FILES:
                recommendation.upload = request.FILES['file']

            recommendation.submitted_by = request.user
            recommendation.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully submitted recommendation.',
                'list-group-item-success')
            return redirect('highschool_admin:student', record_id=record.id)
        else:
            messages.add_message(
                request,
                messages.SUCCESS,
                'Unable to complete your request. Please review the form and try again.',
                'list-group-item-danger')

        submitted_rec_form[
            recommendation_form.cleaned_data['term']
        ] = recommendation_form

    term_data = []
    for term in current_registration_terms:
        # print(123)
        c_term_data = {}
        current_registrations = registered_classes.filter(
            class_section__term=term
        )

        if not current_registrations:
            continue
        c_term_data['registrations'] = current_registrations

        initial = {
            'student': record.id,
            'term': term.id,
            'student_state_id': record.state_id,
            'student_bridge': '2'
        }

        recommendation = None
        if record.has_recommendation(term.id):
            recommendation = record.get_recommendation(term.id)

            initial['student_gpa'] = recommendation.recommendation['student_gpa']
            initial['student_prereq'] = recommendation.recommendation['student_prereq']
            initial['student_grade_level'] = recommendation.recommendation['student_grade_level']
            initial['student_bridge'] = recommendation.recommendation.get('student_bridge', '2')

            initial['grade_earned'] = recommendation.recommendation.get('grade_earned')
            initial['school_assessment'] = recommendation.recommendation.get('school_assessment')
            initial['keystone_exam'] = recommendation.recommendation.get('keystone_exam')
            initial['geip'] = recommendation.recommendation.get('geip')
            initial['enrolled_in_honors'] = recommendation.recommendation.get('enrolled_in_honors')

            initial['upload_label'] = StudentRecommendation.get_form_message()

        if submitted_rec_form.get(str(term.id)):
            recommendation_form = submitted_rec_form[str(term.id)]
            recommendation_form.fields['upload_label'].label = StudentRecommendation.get_form_message()
        else:
            recommendation_form = StudentRecommendationForm(
                student=record,
                current_registrations=current_registrations,
                initial=initial
            )

        c_term_data['recommendation_form'] = recommendation_form
        c_term_data['term'] = term

        term_data.append(c_term_data)

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
            'term_data': term_data,
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
