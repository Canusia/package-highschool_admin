from django.urls import reverse

from rest_framework import serializers

from cis.models.highschool_administrator import HSAdministratorPosition
from cis.models.student import Student
from cis.models.section import StudentRegistration, ClassSection
from cis.models.teacher import TeacherCourseCertificate


# =============================================================================
# Student Serializers
# =============================================================================

class HSAdminStudentSerializer(serializers.ModelSerializer):
    """Lightweight serializer for HS Admin student list."""
    name = serializers.SerializerMethodField()
    highschool = serializers.CharField(source='highschool.name')
    username = serializers.CharField(source='user.username')
    details = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ['id', 'name', 'highschool', 'username', 'graduation_year', 'details']
        datatables_always_serialize = ['id', 'name', 'highschool', 'username', 'graduation_year', 'details']

    def get_name(self, obj):
        return f'{obj.user.last_name}, {obj.user.first_name}'

    def get_details(self, obj):
        return reverse('highschool_admin:student', kwargs={'record_id': obj.id})


# =============================================================================
# Registration Serializers
# =============================================================================

class PendingRecommendationSerializer(serializers.ModelSerializer):
    """Serializer for pending recommendations (StudentRegistration)."""
    name = serializers.SerializerMethodField()
    highschool = serializers.CharField(source='student.highschool.name')
    username = serializers.CharField(source='student.user.username')
    email = serializers.CharField(source='student.user.email')
    graduation_year = serializers.IntegerField(source='student.graduation_year')
    status = serializers.CharField(source='sexy_status')
    next_step = serializers.CharField()
    action = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    psid = serializers.CharField(source='student.user.psid')

    class Meta:
        model = StudentRegistration
        fields = [
            'id', 'name', 'highschool', 'username', 'email',
            'graduation_year', 'status', 'next_step', 'action', 'details', 'psid'
        ]
        datatables_always_serialize = [
            'id', 'name', 'highschool', 'username', 'email',
            'graduation_year', 'status', 'next_step', 'action', 'details', 'psid'
        ]

    def get_name(self, obj):
        return f'{obj.student.user.last_name}, {obj.student.user.first_name}'

    def get_action(self, obj):
        return ''

    def get_details(self, obj):
        return reverse('highschool_admin:student', kwargs={'record_id': obj.student.id})


class PendingReviewSerializer(serializers.ModelSerializer):
    """Serializer for pending reviews (StudentRegistration)."""
    name = serializers.SerializerMethodField()
    highschool = serializers.CharField(source='student.highschool.name')
    username = serializers.CharField(source='student.user.username')
    class_section = serializers.SerializerMethodField()
    graduation_year = serializers.IntegerField(source='student.graduation_year')
    status = serializers.CharField(source='sexy_status')
    next_step = serializers.CharField()
    action = serializers.SerializerMethodField()
    psid = serializers.CharField(source='student.user.psid')
    current_balance = serializers.DecimalField(
        source='student.current_balance',
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        model = StudentRegistration
        fields = [
            'id', 'name', 'highschool', 'username', 'class_section',
            'graduation_year', 'status', 'next_step', 'action', 'psid', 'current_balance'
        ]
        datatables_always_serialize = [
            'id', 'name', 'highschool', 'username', 'class_section',
            'graduation_year', 'status', 'next_step', 'action', 'psid', 'current_balance'
        ]

    def get_name(self, obj):
        return f'{obj.student.user.last_name}, {obj.student.user.first_name}'

    def get_class_section(self, obj):
        return str(obj.class_section)

    def get_action(self, obj):
        return obj.instructor_actions_sexy()


# --- Lightweight Registration Serializers for Registrations by Term table ---

class HSAdminRegUserSerializer(serializers.Serializer):
    """Minimal user serializer for registration list."""
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class HSAdminRegStudentSerializer(serializers.Serializer):
    """Minimal student serializer for registration list."""
    user = HSAdminRegUserSerializer()


class HSAdminRegCourseSerializer(serializers.Serializer):
    """Minimal course serializer for registration list."""
    name = serializers.CharField()
    title = serializers.CharField()
    credit_hours = serializers.DecimalField(max_digits=4, decimal_places=2)


class HSAdminRegClassSectionSerializer(serializers.Serializer):
    """Minimal class section serializer for registration list."""
    course = HSAdminRegCourseSerializer()
    section_number = serializers.CharField()
    class_number = serializers.IntegerField()


class HSAdminRegReviewerSerializer(serializers.Serializer):
    """Minimal reviewer (HSAdministrator) serializer for registration list."""
    user = HSAdminRegUserSerializer()


class HSAdminRegistrationSerializer(serializers.ModelSerializer):
    """Lightweight serializer for HS Admin registration list."""
    student = HSAdminRegStudentSerializer()
    class_section = HSAdminRegClassSectionSerializer()
    reviewer = HSAdminRegReviewerSerializer(allow_null=True)
    created_on = serializers.DateTimeField(format='%m/%d/%Y %I:%M %p')
    changed_on = serializers.CharField(source='status_changed')
    status_pretty = serializers.SerializerMethodField()
    pay_type_pretty = serializers.CharField(read_only=True)
    has_signed_student_agreement = serializers.CharField(read_only=True)

    class Meta:
        model = StudentRegistration
        fields = [
            'id', 'created_on', 'pay_type_pretty', 'has_signed_student_agreement',
            'student', 'class_section', 'status_pretty', 'changed_on', 'reviewer'
        ]
        datatables_always_serialize = [
            'id', 'created_on', 'pay_type_pretty', 'has_signed_student_agreement',
            'student', 'class_section', 'status_pretty', 'changed_on', 'reviewer'
        ]

    def get_status_pretty(self, obj):
        return obj.get_status


# =============================================================================
# Personnel Serializers
# =============================================================================

class PersonnelSerializer(serializers.ModelSerializer):
    """Serializer for HS Administrator positions."""
    name = serializers.SerializerMethodField()
    highschool = serializers.CharField(source='highschool.name')
    position = serializers.CharField(source='position.name')
    parent_id = serializers.IntegerField(source='hsadmin.id')

    class Meta:
        model = HSAdministratorPosition
        fields = ['id', 'name', 'highschool', 'position', 'status', 'parent_id']
        datatables_always_serialize = ['id', 'name', 'highschool', 'position', 'status', 'parent_id']

    def get_name(self, obj):
        return f'{obj.hsadmin.user.last_name}, {obj.hsadmin.user.first_name}'


# =============================================================================
# Class Section Serializers
# =============================================================================

class HSAdminTermSerializer(serializers.Serializer):
    """Minimal term serializer for HS Admin class list."""
    label = serializers.CharField()
    code = serializers.CharField()


class HSAdminCourseSerializer(serializers.Serializer):
    """Minimal course serializer for HS Admin class list."""
    name = serializers.CharField()
    title = serializers.CharField()


class HSAdminUserSerializer(serializers.Serializer):
    """Minimal user serializer for HS Admin class list."""
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class HSAdminTeacherSerializer(serializers.Serializer):
    """Minimal teacher serializer for HS Admin class list."""
    user = HSAdminUserSerializer()


class HSAdminClassSectionSerializer(serializers.ModelSerializer):
    """Lightweight serializer for HS Admin class section list."""
    term = HSAdminTermSerializer()
    course = HSAdminCourseSerializer()
    teacher = HSAdminTeacherSerializer(allow_null=True)

    class Meta:
        model = ClassSection
        fields = [
            'id', 'term', 'course', 'highschool_course_name',
            'teacher', 'class_number', 'section_number',
            'roster_status', 'status'
        ]
        datatables_always_serialize = [
            'id', 'term', 'course', 'highschool_course_name',
            'teacher', 'class_number', 'section_number',
            'roster_status', 'status'
        ]


# =============================================================================
# Course Request Serializers
# =============================================================================

class CourseRequestSerializer(serializers.ModelSerializer):
    """Serializer for course requests (TeacherCourseCertificate) with offering status."""
    certificate_id = serializers.UUIDField(read_only=True)
    course_title = serializers.CharField(source='course.title')
    teacher_name = serializers.SerializerMethodField()
    highschool_name = serializers.CharField(source='teacher_highschool.highschool.name')

    class Meta:
        model = TeacherCourseCertificate
        fields = [
            'certificate_id',
            'course_title',
            'teacher_name',
            'status',
            'highschool_name',
        ]
        datatables_always_serialize = [
            'certificate_id',
            'course_title',
            'teacher_name',
            'status',
            'highschool_name',
        ]

    def get_teacher_name(self, obj):
        return str(obj.teacher_highschool.teacher)


# =============================================================================
# Certificate Serializers
# =============================================================================

class HSAdminCertificateSerializer(serializers.ModelSerializer):
    """Serializer for the HS Admin Instructor Course Certificates list."""
    instructor_name = serializers.SerializerMethodField()
    course_name = serializers.CharField(source='course.name', read_only=True)
    highschool_name = serializers.CharField(
        source='teacher_highschool.highschool.name', read_only=True)
    renewal_due_date = serializers.DateField(format='%m/%d/%Y', read_only=True)
    expires_on = serializers.DateField(format='%m/%d/%Y', read_only=True)
    renewal_required_by = serializers.DateField(format='%m/%d/%Y', read_only=True)
    last_renewed_on = serializers.DateField(format='%m/%d/%Y', read_only=True)

    class Meta:
        model = TeacherCourseCertificate
        fields = [
            'id', 'instructor_name', 'course_name', 'highschool_name', 'status',
            'renewal_due_date', 'renewal_required_by', 'expires_on', 'last_renewed_on',
        ]
        # The hs-admin certificates table uses positional render columns, so
        # every field must always serialize (the datatables backend would
        # otherwise drop unreferenced columns and render blanks).
        datatables_always_serialize = [
            'id', 'instructor_name', 'course_name', 'highschool_name', 'status',
            'renewal_due_date', 'renewal_required_by', 'expires_on', 'last_renewed_on',
        ]

    def get_instructor_name(self, obj):
        u = obj.teacher_highschool.teacher.user
        return f'{u.last_name}, {u.first_name}'


# =============================================================================
# Action Request/Response Serializers
# =============================================================================

class MarkTeachingRequestSerializer(serializers.Serializer):
    """Serializer for mark as teaching request validation."""
    course_certificate_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)


class MarkNotTeachingRequestSerializer(serializers.Serializer):
    """Serializer for mark as not teaching request validation."""
    course_certificate_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)


class RemoveTeachingStatusRequestSerializer(serializers.Serializer):
    """Serializer for remove teaching status request validation."""
    course_certificate_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)


class AddTeacherRequestSerializer(serializers.Serializer):
    """Serializer for add teacher request validation."""
    academic_year_id = serializers.UUIDField(required=True)
    course_type = serializers.ChoiceField(
        choices=['pathways', 'cccl', 'facilitator'],
        default='pathways'
    )


class AssignAdminPositionRequestSerializer(serializers.Serializer):
    """Serializer for assigning administrator to position."""
    highschool_id = serializers.UUIDField(required=True)
    role_id = serializers.UUIDField(required=True)
    administrator_id = serializers.UUIDField(required=False, allow_null=True)


class ActionResponseSerializer(serializers.Serializer):
    """Standard response serializer for actions."""
    status = serializers.CharField()
    message = serializers.CharField()
    action = serializers.CharField(required=False)
    display = serializers.CharField(required=False)


# =============================================================================
# Teaching Section Serializers
# =============================================================================

class TeachingSectionSerializer(serializers.Serializer):
    """Serializer for individual teaching section data."""
    term = serializers.UUIDField(required=True)
    starting_date = serializers.DateField(required=False, allow_null=True)
    ending_date = serializers.DateField(required=False, allow_null=True)
    number_of_sections = serializers.IntegerField(required=False, default=1)
    estimated_enrollment = serializers.IntegerField(required=False, allow_null=True)
    length_change = serializers.CharField(required=False, allow_blank=True)
    access_to_resources = serializers.CharField(required=False, allow_blank=True)
    access_needed_date = serializers.DateField(required=False, allow_null=True)
    taught_by_another = serializers.ChoiceField(
        choices=[('yes', 'Yes'), ('no', 'No')],
        required=False,
        allow_blank=True
    )
    other_instructor = serializers.CharField(required=False, allow_blank=True)
    syllabus = serializers.FileField(required=False, allow_null=True)


class MarkTeachingInputSerializer(serializers.Serializer):
    """Full input for marking course as teaching with sections."""
    course_certificate_id = serializers.UUIDField(required=True)
    academic_year_id = serializers.UUIDField(required=True)
    sections = TeachingSectionSerializer(many=True, required=False)


class FutureCourseResponseSerializer(serializers.Serializer):
    """Response for FutureCourse operations."""
    id = serializers.UUIDField()
    teaching = serializers.CharField(allow_null=True)
    sections_count = serializers.IntegerField()
