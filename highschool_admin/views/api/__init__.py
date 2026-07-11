# Re-export all API components for backward compatibility

from .serializers import (
    HSAdminCertificateSerializer,
    HSAdminStudentSerializer,
    PendingRecommendationSerializer,
    PendingReviewSerializer,
    PersonnelSerializer,
    HSAdminTermSerializer,
    HSAdminCourseSerializer,
    HSAdminUserSerializer,
    HSAdminTeacherSerializer,
    HSAdminClassSectionSerializer,
    HSAdminRegistrationSerializer,
)

from .viewsets import (
    HSAdminCertificateViewSet,
    StudentNoteViewSet,
    RegistrationViewSet,
    StudentRegistrationsTableViewSet,
    StudentViewSet,
    PendingRecommendationViewSet,
    PendingReviewViewSet,
    PersonnelViewSet,
    ClassSectionViewSet,
    AdminPositionViewSet,
    CourseRequestViewSet,
    FutureSectionsActionViewSet,
)

__all__ = [
    # Serializers
    'HSAdminCertificateSerializer',
    'HSAdminStudentSerializer',
    'PendingRecommendationSerializer',
    'PendingReviewSerializer',
    'PersonnelSerializer',
    'HSAdminTermSerializer',
    'HSAdminCourseSerializer',
    'HSAdminUserSerializer',
    'HSAdminTeacherSerializer',
    'HSAdminClassSectionSerializer',
    'HSAdminRegistrationSerializer',
    # ViewSets
    'HSAdminCertificateViewSet',
    'StudentNoteViewSet',
    'RegistrationViewSet',
    'StudentRegistrationsTableViewSet',
    'StudentViewSet',
    'PendingRecommendationViewSet',
    'PendingReviewViewSet',
    'PersonnelViewSet',
    'ClassSectionViewSet',
    'AdminPositionViewSet',
    'CourseRequestViewSet',
    'FutureSectionsActionViewSet',
]
