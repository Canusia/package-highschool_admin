import json

from django.shortcuts import (
    render, get_object_or_404,
    redirect
)
from django.utils.safestring import mark_safe
from django.db import IntegrityError
from django.conf import settings
from django.contrib import messages, auth
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.http import HttpResponseNotFound
from django.contrib.auth import logout
from django.views.decorators.clickjacking import xframe_options_exempt

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db import IntegrityError, transaction
from django.forms.formsets import formset_factory

from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

from cis.models.customuser import CustomUser
from cis.models.student import Student, StudentRecommendation
from cis.models.highschool_administrator import HSAdministrator
from cis.models.highschool import HighSchool, HighSchoolClassOffering, HighSchoolTranscript
from cis.models.highschool_administrator import HSAdministrator, HSAdministratorPosition

from cis.models.section import (
    ClassSection, StudentRegistration
)
from cis.models.term import Term
from cis.models.note import StudentNote
from cis.models.settings import Setting

from cis.menu import draw_menu
from .utils import get_hsadmin_menu
from cis.forms.student import(
    StudentForm, StudentProfileForm,
    UserPasswordChangeForm,
    StudentRecommendationForm
)

from cis.forms.future_sections import (
    TeacherCourseBaseLinkFormSet,
    TeacherCourseSectionForm,
    TeacherCourseTeachingForm
)


from cis.serializers.registration import StudentRegistrationSerializer
from cis.serializers.note import StudentNoteSerializer
from cis.utils import (
    registration_terms, is_student_registration_open,
    active_term, HSADMIN_user_only
)
from cis.views.ajax import add_new

import importlib.util
if importlib.util.find_spec('future_sections.future_sections'):
    from future_sections.future_sections.models import FutureCourse, FutureSection
else:
    from future_sections.models import FutureCourse, FutureSection
from cis.models.teacher import TeacherCourseCertificate
from cis.models.term import AcademicYear

class StudentNoteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentNoteSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        student_id = self.request.GET.get('student_id')
        
        if student_id:
            records = StudentNote.objects.filter(
                student__id=student_id,
                meta__type__contains='to_counselor'
            )
        else:
            # get notes for students in high school
            try:
                user = HSAdministrator.objects.get(user__id=self.request.user.id)
                highschools = user.get_highschools()
            except:
                return StudentNote.objects.none()

            student_ids = StudentRegistration.objects.filter(
                student__highschool__in=highschools
            ).values_list('student__id', flat=True)

            records = StudentNote.objects.filter(
                student__id__in=student_ids,
                meta__type__contains='to_counselor'
            )

        # get notes that are replies
        replies = StudentNote.objects.filter(
            parent__in=records.values_list('id', flat=True)
        )
        records = records | replies

        return records

class RegistrationViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = StudentRegistrationSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        user = HSAdministrator.objects.get(user__id=self.request.user.id)
        term_id = self.request.GET.get('term', active_term().id)
        highschools = user.get_highschools()

        try:
            term = get_object_or_404(Term, pk=term_id)
        except:
            term = active_term()

        registrations = StudentRegistration.objects.filter(
            student__highschool__in=highschools,
            class_section__term=term
        )
        return registrations

def download_transcript(request, record_id):
    file = get_object_or_404(
        HighSchoolTranscript,
        pk=record_id
    )

    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    if not file.highschool in highschools:
        return HttpResponseNotFound('File not found')
    
    from cis.backends.storage_backend import PrivateMediaStorage
    from django.http import FileResponse

    media_storage = PrivateMediaStorage()
    response = FileResponse(
        media_storage.open(str(file.media), 'rb'),
        content_type='application/force-download'
    )

    response['Content-Disposition'] = f'attachment; filename="{file.file_name}"'
    return response

def ajax_requests(request):
    return add_new(request)

def class_section(request, record_id):
    """
    Return class information
    """
    menu = draw_menu(get_hsadmin_menu(), 'classes', '', 'highschool_admin')
    
    class_section_info = get_object_or_404(ClassSection, pk=record_id)
    students_in_class = class_section_info.get_students()
    print(students_in_class)

    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    if class_section_info.highschool.id not in highschools.values_list('id', flat=True):
        return ''
    
    if request.GET.get('action') == 'download_roster_pdf':
        return class_section_info.download_roster_pdf()

    return render(
        request,
        'highschool_admin/class_section.html',
        {
            'menu': menu,
            'record': class_section_info,
            'intro': portal_lang(request).from_db().get('class_blurb', 'Change me'),
            'registered_students': students_in_class
        })


def si_applications(request):

    from cis.settings.inst_app_language import inst_app_language
    from cis.models.teacher_applicant import TeacherApplication

    app_settings = inst_app_language.from_db()

    menu = draw_menu(get_hsadmin_menu(), 'course_apps', '', 'highschool_admin')
    
    if request.method == 'POST':
        new_app = TeacherApplication.create_new(request.user)
        messages.add_message(
            request,
            messages.SUCCESS,
            f'Your new application has been started. Please continue below',
            'list-group-item-success'
        )
        return redirect(
            'instructor_app:manage_courses',
            record_id=new_app.id
        )

    applications = TeacherApplication.objects.filter(
        user__id=request.user.id
    ).order_by('-createdon')

    return render(
        request,
        'highschool_admin/si_apps.html',
        {
            'menu': menu,
            'applications': applications,
            'intro': app_settings.get('instructor_dashboard_blurb'),
            'is_accepting_new': app_settings.get('is_accepting_new')
        })

def future_sections_actions(request):

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'teaching-section':
            return mark_as_teaching(
                request,
                request.POST.get('teacher_course_certificate_id'),
                request.POST.get('academic_year_id')
            )

        if action == 'add_new_teacher':
            return add_new_teacher(
                request,
                request.POST.get('academic_year_id')
            )

    if request.method == 'GET':
        action = request.GET.get('action')

        if action == 'remove-not-teaching-section':
            return remove_marked_as_not_teaching(
                request,
                request.GET.get('course_certificate'),
                request.GET.get('academic_year_id')
            )
        elif action == 'not-teaching-section':
            return mark_as_not_teaching(
                request,
                request.GET.get('course_certificate'),
                request.GET.get('academic_year_id')
            )
        elif action == 'add_new_teacher':
            return add_new_teacher(
                request,
                request.GET.get('academic_year_id')
            )
        elif action == 'teaching-section':
            return mark_as_teaching(
                request,
                request.GET.get('course_certificate'),
                request.GET.get('academic_year_id')
            )

def add_new_teacher(request, academic_year_id):

    from cis.settings.future_sections import future_sections as fs_settings
    fs_config = fs_settings.from_db()
    from cis.forms.future_sections import AddNewTeacherForm

    academic_year = get_object_or_404(
        AcademicYear,
        pk=academic_year_id
    )

    form = AddNewTeacherForm(request, academic_year)

    if request.method == 'POST':
        form = AddNewTeacherForm(request, academic_year, data=request.POST)

        if form.is_valid():
            record = form.save(request, academic_year)

            data = {
                'status':'Success',
                'message':'Successfully added new teacher',
                'action': 'reload'
            }
            return JsonResponse(data)
        else:
            return JsonResponse({
                'message': 'Please correct the errors and try again.',
                'details': '',
                'errors': form.errors.as_json(),
                'status': 'error'
            }, status=400)
    context = {
        'academic_year': academic_year,
        'form': form,
        'new_teacher_message': fs_config.get('new_teacher_message', 'change me')
    }

    return render(request, 'highschool_admin/add_new_teacher.html', context)

def mark_as_teaching(request, course_certificate_id, academic_year_id):
    teacher_course = get_object_or_404(
        TeacherCourseCertificate,
        certificate_id=course_certificate_id
    )

    academic_year = get_object_or_404(
        AcademicYear,
        pk=academic_year_id
    )

    TeachingFormSet = formset_factory(
        TeacherCourseSectionForm,
        formset=TeacherCourseBaseLinkFormSet,
        extra=1
    )
    
    future_course = FutureCourse.get_or_add(
        teacher_course,
        academic_year,
        submitter=request.user
    )

    if future_course.section_info:
        initial_data = future_course.section_info.get('sections')
    else:
        initial_data = []

    if request.method == 'POST':
        teacher_course_teaching_form = TeacherCourseTeachingForm(
            request.POST
        )

        teaching_formset = TeachingFormSet(request.POST)

        if teacher_course_teaching_form.is_valid() and teaching_formset.is_valid():
            section_info = []
            for teaching_form in teaching_formset:
                
                if teaching_form.cleaned_data:
                    data = teaching_form.cleaned_data
                    if data.get('term'):
                        section_info.append(teaching_form.cleaned_data)
                
            future_course.section_info = {'teaching':'yes', 'sections':section_info}
            future_course.save()

            data = {
                'status': 'success',
                'message':'Successfully saved course information',
                'action': 'reload_table'
            }
            return JsonResponse(data)
        else:
            errors = {}
            index = 0
            for err in teaching_formset.errors:
                for field, error_message in err.items():
                    errors[
                        "form-" + str(index) + "-" + field
                    ] = [{
                            'message': error_message
                        }]

                index += 1

            return JsonResponse({
                'message': 'Please correct the errors and try again.',
                'details': mark_safe(str(teaching_formset.non_form_errors())),
                'errors': json.dumps(errors),
                'status': 'error'
            }, status=400)
    else:
        teacher_course_teaching_form = TeacherCourseTeachingForm(
            initial={
                'teacher_course_certificate_id': teacher_course.certificate_id,
                'academic_year_id': academic_year.id,
                'highschool_course_name': teacher_course.highschool_course_name,
            }
        )

        teaching_formset = TeachingFormSet(
            initial=initial_data
        )
    
    from cis.settings.future_sections import future_sections as fs_settings
    fs_config = fs_settings.from_db()

    context = {
        'teacher_course_teaching_form': teacher_course_teaching_form,
        'teaching_formset': teaching_formset,
        'teacher_course': teacher_course,
        'academic_year': academic_year,
        'teaching_message': fs_config.get('teaching_message', 'change me')
    }

    return render(request, 'highschool_admin/teaching_course.html', context)

def remove_marked_as_not_teaching(request, course_certificate_id, academic_year_id):

    future_course = FutureCourse.objects.filter(
        teacher_course__certificate_id=course_certificate_id,
        academic_year__id=academic_year_id
    ).delete()

    data = {
        'display': 'swal',
        'status':'success',
        'message':'Successfully removed course information',
        'action': 'reload_future_courses'
    }
    return JsonResponse(data)

def mark_as_not_teaching(request, course_certificate_id, academic_year_id):

    teacher_course = get_object_or_404(
        TeacherCourseCertificate,
        certificate_id=course_certificate_id
    )

    academic_year = get_object_or_404(
        AcademicYear,
        pk=academic_year_id
    )

    future_course = FutureCourse.get_or_add(
        teacher_course,
        academic_year,
        {
            'teaching': 'no'
        },
        submitter=request.user
    )

    data = {
        'display': 'swal',
        'status':'success',
        'message':'Successfully marked course as not teaching',
        'action': 'reload_future_courses'
    }
    return JsonResponse(data)


def future_sections(request):
    from cis.settings.future_sections import future_sections as fs_settings

    fs_config = fs_settings.from_db()
    menu = draw_menu(get_hsadmin_menu(), 'section_requests', '', 'highschool_admin')

    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()
    
    hs_courses = TeacherCourseCertificate.objects.filter(
        teacher_highschool__highschool__in=highschools,
        course__status__in=fs_config.get('course_status'),
        status__in=fs_config.get('teacher_course_status')
    )
    
    academic_year = AcademicYear.objects.get(
        pk=fs_config.get('academic_year', AcademicYear.objects.first().id)
    )

    window_is_open = FutureCourse.is_window_open()
    if request.GET.get('future_section_info'):
        future_sections = FutureCourse.objects.filter(
            teacher_course__in=hs_courses,
            academic_year=academic_year
        )

        result = []
        for future_section in future_sections:
            result.append({
                'window_is_open': window_is_open,
                'id': future_section.teacher_course.certificate_id,
                'academic_year_id': future_section.academic_year.id,
                'teaching': future_section.section_info.get('teaching'),
                'sections': future_section.section_info.get('sections', 0)
            })
        return JsonResponse({
            'data': result
        })

    return render(
        request,
        'highschool_admin/section_requests.html',
        {
            'menu': menu,
            'window_is_open': window_is_open,
            'allow_teacher_create': True if fs_config.get('allow_new_teacher_create', '1') == '1' else False,
            'new_teacher_create_label': fs_config.get('new_teacher_create_label', 'Change me'),
            'window_closed_message': fs_config.get('window_closed_message'),
            'welcome_message': FutureCourse.welcome_message(highschools),
            'intro': portal_lang(request).from_db().get('section_requests_blurb', 'Change me'),
            'academic_year': academic_year,
            'hs_courses': hs_courses
        })

def classes(request):

    menu = draw_menu(get_hsadmin_menu(), 'classes', 'classes', 'highschool_admin')
    sections_assigned = []

    user = HSAdministrator.objects.get(user__id=request.user.id)
    # highschools = user.get_highschools()
    return render(
        request,
        'highschool_admin/classes.html',
        {
            'menu': menu,
            'classes_api': '/highschool_admin/api/class-section/?format=datatables',
            'intro': portal_lang(request).from_db().get('classes_blurb', 'Change me'),
            'terms': Term.objects.all().order_by('-code'),
            'active_term': active_term(),
        })

def course_search(request):
    return render(
        request,
        'highschool_admin/course_search.html',
        {
            'is_registration_open': True,
            'registration_terms': registration_terms(),
            'intro': portal_lang(request).from_db().get('course_search_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'course_search', '', 'highschool_admin')
        })

@xframe_options_exempt
def student(request, record_id):
    """
    Return student information
    """
    user = HSAdministrator.objects.get(user__id=request.user.id)
    menu = draw_menu(get_hsadmin_menu(), 'students', '', 'highschool_admin')
    record = get_object_or_404(Student, pk=record_id)
    current_registration_terms = registration_terms()

    # get all registered classes
    registered_classes = StudentRegistration.objects.filter(
        student=record
    )

    # This will store term keyed recommendation form instance
    # if a form is submitted. This is used to prevent reinitializing
    # rec form instance further down in the method
    submitted_rec_form = {}

    # The manage_student_recommendation permission is keyed to the STUDENT's
    # high school, not the section's host high school -- those differ when a
    # student takes a section hosted elsewhere, and the recommendation belongs
    # to the school the student attends.
    can_recommend = user.can_manage_student_recommendation(
        record.highschool.id if record.highschool else None
    )

    if request.method == 'POST':
        # Refuse the whole POST before any write. The previous per-registration
        # check only skipped the approve/deny status change -- the
        # StudentRecommendation record itself saved regardless.
        if not can_recommend:
            messages.add_message(
                request,
                messages.SUCCESS,
                'You do not have permission to submit recommendations for this student.',
                'list-group-item-danger')
            return redirect('highschool_admin:student', record_id=record.id)

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
                    # No per-registration permission check here: the whole POST
                    # is already gated on can_recommend above, computed from the
                    # student's high school.
                    if(request.POST.get(f'registration_{registration.id}')):
                        registration.status = request.POST.get(f'registration_{registration.id}')
                        registration.reviewer = user

                        if registration.status == 'approved':
                            # registration.pay_type = request.POST.get(f'registration_pay_type_{registration.id}')
                            
                            # try:
                            #     registration.non_student_pay_amount = float(request.POST.get(f'registration_non_student_pay_amount_{registration.id}', '0'))
                            # except (ValueError, TypeError):
                            #     registration.non_student_pay_amount = 0.00
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

            # initial['student_qualification'] = recommendation.qualification
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
            # print(StudentRecommendation.get_form_message())
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
            'term_data': term_data,
            'can_recommend': can_recommend,
            'intro': portal_lang(request).from_db().get('student_blurb', 'Change me'),
            'notes_api_url': f'/highschool_admin/api/student_notes/?format=datatables&student_id={record.id}'
        })

def get_personnel(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    status = request.GET.get('status', 'active')

    hs_administrators = HSAdministratorPosition.objects.filter(
        status__iexact=status,
        highschool__in=highschools
    )

    result = {
        'data': []
    }
    for personnel in hs_administrators:
        result['data'].append({
            'name': f'{personnel.hsadmin.user.last_name}, {personnel.hsadmin.user.first_name}',
            'highschool': personnel.highschool.name,
            'position': personnel.position.name,
            'status': personnel.status,
            'id': personnel.id,
            'parent_id': personnel.hsadmin.id
        })
    return JsonResponse(result)

def get_students(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()
    term_id = request.GET.get('term', active_term().id)

    term = get_object_or_404(Term, pk=term_id)

    registrations_for_term = StudentRegistration.objects.filter(
        student__highschool__in=highschools,
        class_section__term=term
    ).distinct('student').values_list('student__id', flat=True)

    # Get all high school students in term
    students_in_highschol = Student.objects.filter(
        highschool__in=highschools,
        pk__in=registrations_for_term
    )

    result = {
        'data': []
    }
    for student in students_in_highschol:
        result['data'].append({
            'name': f'{student.user.last_name}, {student.user.first_name}',
            'highschool': student.highschool.name,
            'username': student.user.username,
            'graduation_year': student.graduation_year,
            'details': reverse_lazy('highschool_admin:student', kwargs={
                'record_id':student.id
            })
        })
    return JsonResponse(result)

def get_registrations_for_term(request, term_id=None):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    term_id = request.GET.get('term', active_term().id)
    highschools = user.get_highschools()

    term = get_object_or_404(Term, pk=term_id)

    registrations = StudentRegistration.objects.filter(
        student__highschool__in=highschools,
        class_section__term=term
    )

    result = {
        'data': []
    }
    for registration in registrations:
        result['data'].append({
            'name': f'{registration.student.user.last_name}, {registration.student.user.first_name}',
            'term': f'{registration.class_section.term}',
            'course': f'{registration.class_section.course.name}',
            'course_title': f'{registration.class_section.course.title}',
            'course_credits': f'{registration.class_section.course.credit_hours}',
            'instructor': f'{registration.class_section.teacher}',
            'status': f'{registration.status}',
            'highschool': registration.student.highschool.name,
            'username': registration.student.user.username,
            'details': reverse_lazy('highschool_admin:student', kwargs={
                'record_id':registration.student.id
            })
        })
    return JsonResponse(result)


def update_registration_status(request):
    record = get_object_or_404(StudentRegistration, pk=request.GET.get('id'))
    from cis.utils import is_pay_type_review_open

    # if str(record.class_section.id) != request.GET.get('section_id'):
    #     return JsonResponse({
    #         'status': 'error',
    #         'message': 'Unable to find registration'
    #     }, status=401)

    if is_pay_type_review_open():
        # if request.GET.get('status') == 'approved_by_instructor':
        #     record.status = 'approved'
        # elif request.GET.get('status') == 'not_approved_by_instructor':
        #     record.status = 'not_approved'
        # elif request.GET.get('status', '').startswith('move_to_'):
        #     class_section_id = request.GET.get('status').replace('move_to_', '')

        #     record.move_to_section(class_section_id, request)

        record.pay_type = request.GET.get('pay_type')
        try:
            record.non_student_pay_amount = int(request.GET.get('non_student_pay_amount'))
        except (ValueError, TypeError):
            record.non_student_pay_amount = 0

        record.reviewer = HSAdministrator.objects.get(user=request.user)
        record.save()

        message = f'<td>{record.student}</td><td>{record.student.user.psid}</td><td>{record.student.user.email}</td><td>{record.pay_type_pretty}'
        message += "</td>"

        return JsonResponse(
            {
                'status': 'success',
                'student': str(record.student),
                'class_section': str(record.class_section),
                'psid': record.student.user.psid,
                'pay_type_pretty': record.pay_type_pretty,
                'actions': record.instructor_actions_sexy(),
                'registration_status': record.sexy_status,
                # 'next_step': record.next_step(),
                'html': message,
            },
            status=200
        )

    return JsonResponse({
            'status': 'error',
            'message': 'Review period is not open'
        }, status=401)

def get_pending_review(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    registrations_for_term = StudentRegistration.objects.filter(
        student__highschool__in=highschools
    )

    if request.GET.get('pending_type') == 'by_term':
        if request.GET.get('term') == '-2':
            registrations_for_term = registrations_for_term.filter(
                class_section__term__in=registration_terms()
            )
        else:
            try:
                registrations_for_term = registrations_for_term.filter(
                    class_section__term__id=request.GET.get('term')
                )
            except:
                registrations_for_term = StudentRegistration.objects.none()
    else:
        registrations_for_term = registrations_for_term.filter(
            status__in=['applied']
        )

    result = {
        'data': []
    }
    for registration in registrations_for_term:
        result['data'].append({
            'name': f'{registration.student.user.last_name}, {registration.student.user.first_name}',
            'highschool': registration.student.highschool.name,
            'username': registration.student.user.username,
            'class_section': str(registration.class_section),
            'graduation_year': registration.student.graduation_year,
            'status': registration.sexy_status,
            'next_step': registration.next_step(),
            'id': registration.id,
            'action': registration.instructor_actions_sexy(),
            'psid': registration.student.user.psid,
            'current_balance': registration.student.current_balance
        })
    return JsonResponse(result)

def get_pending_pay_type(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    registrations_for_term = StudentRegistration.objects.filter(
        student__highschool__in=highschools,
        pay_type__in=['', None]
    )

    if request.GET.get('pending_type') == 'by_term':
        if request.GET.get('term') == '-2':
            registrations_for_term = registrations_for_term.filter(
                class_section__term__in=registration_terms()
            )
        else:
            try:
                registrations_for_term = registrations_for_term.filter(
                    class_section__term__id=request.GET.get('term')
                )
            except:
                registrations_for_term = StudentRegistration.objects.none()
    else:
        registrations_for_term = registrations_for_term.filter(
            status__in=['applied']
        )

    result = {
        'data': []
    }
    for registration in registrations_for_term:
        result['data'].append({
            'name': f'{registration.student.user.last_name}, {registration.student.user.first_name}',
            'highschool': registration.student.highschool.name,
            'pay_type': registration.pay_type_pretty,
            'username': registration.student.user.username,
            'class_section': str(registration.class_section),
            'graduation_year': registration.student.graduation_year,
            'status': registration.sexy_status,
            # 'next_step': registration.next_step(),
            'id': registration.id,
            'action': registration.pay_type_actions_sexy(),
            'psid': registration.student.user.psid,
            'current_balance': registration.student.current_balance
        })
    return JsonResponse(result)

def get_pending_recommendations(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    # Only schools where this admin actually holds the recommendation
    # permission, not every school they hold a position at.
    highschools = user.get_recommendation_highschools()

    pending_recommendations = StudentRegistration.get_pending_recommendations(
        highschool_ids=[hs.id for hs in highschools]
    ).distinct('student')
    
    result = {
        'data': []
    }

    for registration in pending_recommendations:
        action = ''

        if not registration.class_section.course.prereq:
            # other_sections = registration.other_sections()

            # action = "<select class='form-control form-control-sm mt-2' style='width: 80%'>"
            # action += "<option value=''>Select</option>"
            # action += "<option value='approved'>Approved</option>"
            # action += "<option value='not_approved'>Not Approved</option>"
            # for os in other_sections:
            #     action += f"<option value={str(os.id)}>Move to Section # {os.class_number}</option>"
            # action += "</select>"

            action = ''

        result['data'].append({
            'name': f'{registration.student.user.last_name}, {registration.student.user.first_name}',
            'highschool': registration.student.highschool.name,
            'username': registration.student.user.username,
            'email': registration.student.user.email,
            
            # 'class_section': f'{registration.class_section.course.name} {registration.class_section.section_number})',
            'graduation_year': registration.student.graduation_year,
            'status': registration.sexy_status,
            'next_step': registration.next_step(),
            # 'course_description': registration.class_section.course.sexy_description(),
            'id': registration.id,
            'action': action,
            'details': reverse_lazy('highschool_admin:student', kwargs={
                'record_id': registration.student.id
            }),
            'psid': registration.student.user.psid
        })
    
    return JsonResponse(result)

def get_transcripts(request):
    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()

    # Get all high school students
    transcripts = HighSchoolTranscript.objects.filter(
        highschool__in=highschools
    )

    result = {
        'data': []
    }
    for record in transcripts:
        result['data'].append({
            'uploaded_on': record.uploaded_on.strftime('%m/%d/%Y') if record.uploaded_on else '',
            'id': record.id,
            'uploaded_by': f'{record.uploaded_by.last_name}, {record.uploaded_by.first_name}',
            'highschool': record.highschool.name,
            'description': record.description,
            'media': record.media.url,
            'file_name': record.file_name
            })
    return JsonResponse(result)

def transcripts(request):
    return render(
        request,
        'highschool_admin/transcripts.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'transcripts', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('transcripts_blurb', 'Change me'),
        })

def personnel(request):
    return render(
        request,
        'highschool_admin/personnel.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'administrators', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('administrators_blurb', 'Change me'),
        })

def students(request):
    return render(
        request,
        'highschool_admin/students-rec.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'students', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('students_blurb', 'Change me'),
            'terms': Term.objects.all().order_by('-code'),
            'active_term': active_term(),
        })

def student_notes(request):
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

def manage_password(request):

    student = HSAdministrator.objects.get(user__id=request.user.id)
    form = UserPasswordChangeForm()

    if request.method == 'POST' and request.POST.get('update_password') == 'Update Password':
        user = CustomUser.objects.get(pk=student.user.id)            
        form = UserPasswordChangeForm(user, request.POST)

        if form.is_valid():
            user.set_password(form.cleaned_data['password'])
            user.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated password. Please login again.',
                'list-group-item-success') 
            return redirect('highschool_admin:manage_password')

    return render(
        request,
        'highschool_admin/manage_password.html',
        {
            'form': form,
            'intro': portal_lang(request).from_db().get('manage_password_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'manage_password', '', 'highschool_admin')
        })

def profile(request):

    student = Student.objects.get(user__id=request.user.id)
    form = StudentProfileForm(student, request)

    if request.method == 'POST' and request.POST.get('update_profile') == 'Update Profile':
        form = StudentProfileForm(student, request, request.POST)
        if form.is_valid():
            student.update_profile(form)
            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated profile.',
                'list-group-item-success') 
            return redirect('student:profile')

    return render(
        request,
        'student/profile.html',
        {
            'form': form,
            'intro': portal_lang(request).from_db().get('profile_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'profile', '', 'highschool_admin')
        })

