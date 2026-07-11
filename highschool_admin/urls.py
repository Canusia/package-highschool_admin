"""
    High School Admin URL Configuration
"""
from django.urls import path, include
from django.contrib.auth.decorators import user_passes_test

from cis.utils import user_has_highschool_admin_role
from two_step.decorators import verification_required


def hsadmin_view(view):
    """Gate a highschool_admin page view with BOTH the role check AND
    two-step verification (PT-19). Order matters: role first, then second
    factor, so an authenticated highschool_admin who has not completed the
    second factor is redirected to two_step:verify instead of the page."""
    role_gated = user_passes_test(
        user_has_highschool_admin_role, login_url='/'
    )(view)
    return verification_required(role_gated)

from .views import (
    # Dashboard
    dashboard,
    profile,
    manage_password,
    # Students
    student,
    students,
    student_notes,
    # Classes
    class_section,
    classes,
    course_search,
    # Registrations
    get_registrations_for_term,
    update_registration_status,
    get_pending_pay_type,
    # Personnel
    personnel,
    # Transcripts
    transcripts,
    get_transcripts,
    download_transcript,
    # Certificates
    certificates_index,
    # Student importer
    student_import,
    student_import_preview,
    student_import_confirm,
    student_import_template,
    # Bulk enroll
    bulk_enroll,
    bulk_enroll_preview,
    bulk_enroll_confirm,
    bulk_enroll_report,
    bulk_enroll_template,
    # Utilities
    ajax_requests,
    # API ViewSets
    HSAdminCertificateViewSet,
    RegistrationViewSet,
    StudentRegistrationsTableViewSet,
    StudentNoteViewSet,
    StudentViewSet,
    PendingRecommendationViewSet,
    PendingReviewViewSet,
    PersonnelViewSet,
    ClassSectionViewSet,
    AdminPositionViewSet,
    CourseRequestViewSet,
    FutureSectionsActionViewSet,
)


from rest_framework import routers

router = routers.DefaultRouter()
router_viewsets = {
    'registration': RegistrationViewSet,
    'student-registrations': StudentRegistrationsTableViewSet,
    'student_notes': StudentNoteViewSet,
    'class-section': ClassSectionViewSet,
    'students': StudentViewSet,
    'pending-recommendations': PendingRecommendationViewSet,
    'pending-reviews': PendingReviewViewSet,
    'personnel': PersonnelViewSet,
    'admin-positions': AdminPositionViewSet,
    'course-requests': CourseRequestViewSet,
    'course-actions': FutureSectionsActionViewSet,
    'certificates': HSAdminCertificateViewSet,
}

app_name = 'highschool_admin'

for router_key in router_viewsets.keys():
    router.register(
        router_key,
        router_viewsets[router_key],
        basename=router_key
    )

urlpatterns = [
    path('api/', include(router.urls)),

    # Note: future_sections is now served from future_sections.urls.highschool_admin
    # via myce/urls.py at /highschool_admin/future_sections/

    path('update_registration_status/', hsadmin_view(update_registration_status), name='update_registration_status'),
    path('get_pending_pay_type/', hsadmin_view(get_pending_pay_type), name='get_pending_pay_type'),
    path('ajax/', hsadmin_view(ajax_requests), name='ajax'),
    path('class_section/<uuid:record_id>', hsadmin_view(class_section), name='class_section'),
    path('classes/', hsadmin_view(classes), name='classes'),
    path('course_search/', hsadmin_view(course_search), name='course_search'),
    path('students/notes', hsadmin_view(student_notes), name='student_notes'),
    path('registrations/term', hsadmin_view(get_registrations_for_term), name='registrations_for_term'),
    path('personnel/', hsadmin_view(personnel), name='personnel'),
    path('students/', hsadmin_view(students), name='students'),
    path('transcripts/', hsadmin_view(transcripts), name='transcripts'),
    path('transcripts/get', hsadmin_view(get_transcripts), name='get_transcripts'),
    path('transcript/<uuid:record_id>', hsadmin_view(download_transcript), name='download_transcript'),
    path('certificates/', hsadmin_view(certificates_index), name='certificates'),
    path('student_import/', hsadmin_view(student_import), name='student_import'),
    path('student_import/template', hsadmin_view(student_import_template), name='student_import_template'),
    path('student_import/<uuid:batch_id>/preview', hsadmin_view(student_import_preview), name='student_import_preview'),
    path('student_import/<uuid:batch_id>/confirm', hsadmin_view(student_import_confirm), name='student_import_confirm'),
    path('bulk_enroll/', hsadmin_view(bulk_enroll), name='bulk_enroll'),
    path('bulk_enroll/template', hsadmin_view(bulk_enroll_template), name='bulk_enroll_template'),
    path('bulk_enroll/<uuid:batch_id>/preview', hsadmin_view(bulk_enroll_preview), name='bulk_enroll_preview'),
    path('bulk_enroll/<uuid:batch_id>/confirm', hsadmin_view(bulk_enroll_confirm), name='bulk_enroll_confirm'),
    path('bulk_enroll/<uuid:batch_id>/report', hsadmin_view(bulk_enroll_report), name='bulk_enroll_report'),
    path('student/<uuid:record_id>', hsadmin_view(student), name='student'),
    path('profile/', hsadmin_view(profile), name='profile'),
    path('manage_password/', hsadmin_view(manage_password), name='manage_password'),
    path('dashboard/', hsadmin_view(dashboard), name='dashboard'),
]
