# Re-export all views for backward compatibility

# Utilities
from .utils import (
    get_current_hsadmin,
    get_user_highschools,
    ajax_requests,
)

# API ViewSets
from .api import (
    HSAdminCertificateViewSet,
    HSAdminCertificateSerializer,
    StudentNoteViewSet,
    RegistrationViewSet,
    StudentViewSet,
    HSAdminStudentSerializer,
    PendingRecommendationViewSet,
    PendingRecommendationSerializer,
    PendingReviewViewSet,
    PendingReviewSerializer,
    PersonnelViewSet,
    PersonnelSerializer,
    ClassSectionViewSet,
    HSAdminClassSectionSerializer,
    HSAdminRegistrationSerializer,
    AdminPositionViewSet,
    CourseRequestViewSet,
    FutureSectionsActionViewSet,
)

# Dashboard views
from .dashboard import (
    dashboard,
    profile,
    manage_password,
)

# Student views
from .students import (
    student,
    students,
    student_notes,
)

# Class views
from .classes import (
    class_section,
    classes,
    course_search,
)

# Future sections views
from .future_sections import (
    future_sections,
)

# Registration views
from .registrations import (
    get_registrations_for_term,
    update_registration_status,
    get_pending_pay_type,
)

# Personnel views
from .personnel import (
    personnel,
)

# Transcript views
from .transcripts import (
    transcripts,
    get_transcripts,
    download_transcript,
)

# Certificate views
from .certificates import index as certificates_index

# Student importer views
from .student_import import (
    student_import,
    student_import_preview,
    student_import_confirm,
    download_template as student_import_template,
)

# Bulk enroll views
from .bulk_enroll import (
    bulk_enroll,
    bulk_enroll_preview,
    bulk_enroll_confirm,
    bulk_enroll_report,
    bulk_enroll_template,
)

__all__ = [
    # Utilities
    'get_current_hsadmin',
    'get_user_highschools',
    'ajax_requests',
    # API
    'HSAdminCertificateViewSet',
    'HSAdminCertificateSerializer',
    'StudentNoteViewSet',
    'RegistrationViewSet',
    'StudentViewSet',
    'HSAdminStudentSerializer',
    'PendingRecommendationViewSet',
    'PendingRecommendationSerializer',
    'PendingReviewViewSet',
    'PendingReviewSerializer',
    'PersonnelViewSet',
    'PersonnelSerializer',
    'ClassSectionViewSet',
    'HSAdminClassSectionSerializer',
    'HSAdminRegistrationSerializer',
    'AdminPositionViewSet',
    'CourseRequestViewSet',
    'FutureSectionsActionViewSet',
    # Dashboard
    'dashboard',
    'profile',
    'manage_password',
    # Students
    'student',
    'students',
    'student_notes',
    # Classes
    'class_section',
    'classes',
    'course_search',
    # Future sections
    'future_sections',
    # Registrations
    'get_registrations_for_term',
    'update_registration_status',
    'get_pending_pay_type',
    # Personnel
    'personnel',
    # Transcripts
    'transcripts',
    'get_transcripts',
    'download_transcript',
    # Certificates
    'certificates_index',
    # Student importer
    'student_import',
    'student_import_preview',
    'student_import_confirm',
    'student_import_template',
    # Bulk enroll
    'bulk_enroll',
    'bulk_enroll_preview',
    'bulk_enroll_confirm',
    'bulk_enroll_report',
    'bulk_enroll_template',
]
