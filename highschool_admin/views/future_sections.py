import datetime

from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q

from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang
from cis.settings.future_sections import future_sections as fs_settings

import importlib.util
if importlib.util.find_spec('future_sections.future_sections'):
    from future_sections.future_sections.models import FutureProjection, FutureCourse
else:
    from future_sections.models import FutureProjection, FutureCourse
from cis.models.highschool_administrator import HSAdministrator, HSPosition
from cis.models.highschool import HighSchool
from cis.models.teacher import TeacherCourseCertificate
from cis.models.term import AcademicYear

from cis.menu import draw_menu
from cis.page_messages import get_page_messages
from .utils import get_hsadmin_menu

from cis.forms.future_sections import (
    ConfirmHighSchoolAdministratorsForm,
    ConfirmClassSectionsForm
)


# =============================================================================
# Helper Functions
# =============================================================================

def get_fs_config():
    """Get future sections configuration from database."""
    return fs_settings.from_db()


def get_or_create_future_projection(highschool_id, user):
    """
    Get or create a FutureProjection for a highschool and academic year.

    Args:
        highschool_id: UUID of the highschool
        user: The user creating the projection

    Returns:
        FutureProjection instance
    """
    fs_config = get_fs_config()
    academic_year_id = fs_config.get('academic_year')

    projection = FutureProjection.objects.filter(
        highschool__id=highschool_id,
        academic_year__id=academic_year_id
    ).first()

    if not projection:
        projection = FutureProjection.objects.create(
            highschool=HighSchool.objects.get(pk=highschool_id),
            academic_year=AcademicYear.objects.get(pk=academic_year_id),
            created_by=user,
            meta={
                'confirmed_administrators': 'No',
                'confirmed_class_sections': 'No',
                'history': []
            }
        )

    return projection


def add_history_entry(obj, user, action):
    """
    Add a history entry to an object's meta field.

    Args:
        obj: Object with a meta JSONField (FutureCourse or FutureProjection)
        user: User performing the action
        action: Description of the action
    """
    if not obj.meta:
        obj.meta = {'history': []}

    if 'history' not in obj.meta:
        obj.meta['history'] = []

    obj.meta['history'].append({
        'user': str(user),
        'action': action,
        'on': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


def future_sections(request):
    from cis.settings.future_sections import future_sections as fs_settings

    fs_config = fs_settings.from_db()
    menu = draw_menu(get_hsadmin_menu(), 'section_requests', '', 'highschool_admin')

    user = HSAdministrator.objects.get(user__id=request.user.id)
    highschools = user.get_highschools()
    
    confirm_admins_form = ConfirmHighSchoolAdministratorsForm(
        highschools=highschools
    )

    confirm_sections_form = ConfirmClassSectionsForm(
        highschools=highschools,
        action='confirmed_class_sections'
    )

    hs_courses = TeacherCourseCertificate.objects.filter(
        teacher_highschool__highschool__in=highschools,
        course__status__in=fs_config.get('course_status'),
        status__in=fs_config.get('teacher_course_status')
    )

    choice_courses = TeacherCourseCertificate.objects.none()
    facilitator_courses = TeacherCourseCertificate.objects.none()
    
    academic_year = AcademicYear.objects.get(
        pk=fs_config.get('academic_year', AcademicYear.objects.first().id)
    )

    window_is_open = FutureCourse.is_window_open()
    if request.method == 'POST':
        if request.POST.get('action') in ['confirmed_class_sections']:
            confirm_sections_form = ConfirmClassSectionsForm(
                highschools=highschools,
                action=request.POST.get('action'),
                data=request.POST
            )

            if confirm_sections_form.is_valid():
                confirm_sections_form.save(request)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f'Successfully confirmed class sections',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f'Please fix the errors and try again.',
                    'list-group-item-warning'
                )

        # if request.POST.get('action') in ['confirmed_choice_class_sections']:
        #     confirm_choice_sections_form = ConfirmClassSectionsForm(
        #         highschools=highschools,
        #         action=request.POST.get('action'),
        #         data=request.POST
        #     )

        #     if confirm_choice_sections_form.is_valid():
        #         confirm_choice_sections_form.save(request)
        #         messages.add_message(
        #             request,
        #             messages.SUCCESS,
        #             f'Successfully confirmed class sections',
        #             'list-group-item-success'
        #         )
        #     else:
        #         messages.add_message(
        #             request,
        #             messages.SUCCESS,
        #             f'Please fix the errors and try again.',
        #             'list-group-item-warning'
        #         )

        # if request.POST.get('action') in ['confirmed_facilitator_class_sections']:
        #     confirm_facilitator_sections_form = ConfirmClassSectionsForm(
        #         highschools=highschools,
        #         action=request.POST.get('action'),
        #         data=request.POST
        #     )

        #     if confirm_facilitator_sections_form.is_valid():
        #         confirm_facilitator_sections_form.save(request)
        #         messages.add_message(
        #             request,
        #             messages.SUCCESS,
        #             f'Successfully confirmed class sections',
        #             'list-group-item-success'
        #         )
        #     else:
        #         messages.add_message(
        #             request,
        #             messages.SUCCESS,
        #             f'Please fix the errors and try again.',
        #             'list-group-item-warning'
        #         )

        if request.POST.get('action') == 'confirmed_administrators':
            confirm_admins_form = ConfirmHighSchoolAdministratorsForm(
                highschools=highschools,
                data=request.POST
            )

            if confirm_admins_form.is_valid():
                confirm_admins_form.save(request)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f'Successfully confirmed school administrators',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f'Please fix the errors and try again.',
                    'list-group-item-warning'
                )

    if request.GET.get('future_section_info'):
        future_sections = FutureCourse.objects.filter(
            (
                Q(teacher_course__in=hs_courses) | Q(
                teacher_course__in=choice_courses ) | Q(
                teacher_course__in=facilitator_courses )
            ),
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

    hs_roles = HSPosition.objects.filter(
        id__in=fs_config.get('school_admin_roles', [])
    ).order_by('name')
    
    return render(
        request,
        'highschool_admin/future_sections.html',
        {
            'menu': menu,
            'window_is_open': window_is_open,
            'allow_teacher_create': True if fs_config.get('allow_new_teacher_create', '1') == '1' else False,
            'new_teacher_create_label': fs_config.get('new_teacher_create_label', 'Change me'),
            'window_closed_message': fs_config.get('window_closed_message'),
            'welcome_message': FutureCourse.welcome_message(highschools),
            'welcome_message_personnel': fs_config.get('welcome_message_personnel', 'Change Me'),
            'confirm_administrators_header': fs_config.get('confirm_administrators_header', 'Change Me'),
            'intro': portal_lang(request).from_db().get('section_requests_blurb', 'Change me'),
            'academic_year': academic_year,
            'hs_courses': hs_courses,
            # 'choice_courses': choice_courses,
            # 'facilitator_courses': facilitator_courses,
            'hs_roles': hs_roles,
            'highschools': highschools,
            'confirm_admins_form': confirm_admins_form,
            'confirm_sections_form': confirm_sections_form,
            # 'confirm_choice_sections_form': confirm_choice_sections_form,
            # 'confirm_facilitator_sections_form': confirm_facilitator_sections_form,
            'page_messages': get_page_messages('highschool_admin', 'future_sections', request),
        })

