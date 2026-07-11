import datetime
import json
import uuid

from django.db import transaction
from django.forms.formsets import formset_factory
from django.shortcuts import render, get_object_or_404
from django.utils.safestring import mark_safe

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from cis.models.highschool_administrator import HSAdministrator, HSAdministratorPosition
from cis.models.note import StudentNote
from cis.models.student import Student
from cis.models.section import StudentRegistration, ClassSection
from cis.models.term import Term
from cis.models.teacher import TeacherCourseCertificate
import importlib.util
if importlib.util.find_spec('future_sections.future_sections'):
    from future_sections.future_sections.models import FutureCourse, FutureProjection
else:
    from future_sections.models import FutureCourse, FutureProjection
from cis.models.term import AcademicYear
from cis.models.highschool import HighSchool
from cis.serializers.note import StudentNoteSerializer
from cis.serializers.highschool_admin import HSAdministratorPositionSerializer
from cis.serializers.registration import StudentRegistrationSerializer
from cis.utils import active_term, registration_terms, HSADMIN_user_only
from cis.settings.future_sections import future_sections as fs_settings
from cis.forms.future_sections import (
    TeacherCourseBaseLinkFormSet,
    TeacherCourseSectionForm,
    TeacherCourseTeachingForm,
    AddNewTeacherForm,
    HSAdministratorPositionForm,
)

from ..utils import get_user_highschools
from .serializers import (
    HSAdminCertificateSerializer,
    HSAdminStudentSerializer,
    PendingRecommendationSerializer,
    PendingReviewSerializer,
    PersonnelSerializer,
    HSAdminClassSectionSerializer,
    HSAdminRegistrationSerializer,
    CourseRequestSerializer,
    MarkTeachingRequestSerializer,
    MarkNotTeachingRequestSerializer,
    RemoveTeachingStatusRequestSerializer,
    AddTeacherRequestSerializer,
    AssignAdminPositionRequestSerializer,
)


# =============================================================================
# Student ViewSets
# =============================================================================

class StudentNoteViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for student notes visible to HS administrators."""
    serializer_class = StudentNoteSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        student_id = self.request.GET.get('student_id')

        if student_id:
            records = StudentNote.objects.filter(
                student__id=student_id,
                student__highschool__in=get_user_highschools(self.request),
                meta__type__contains='to_counselor'
            )
        else:
            # get notes for students in high school
            try:
                highschools = get_user_highschools(self.request)
            except HSAdministrator.DoesNotExist:
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


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for students list visible to HS administrators."""
    serializer_class = HSAdminStudentSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)
        term_id = self.request.GET.get('term', str(active_term().id))

        # Build base registration query
        registrations = StudentRegistration.objects.filter(
            student__highschool__in=highschools
        )

        # Filter by term unless -1 (all terms)
        if term_id != '-1':
            # PT-fuzz: reject any non-UUID term before it reaches the UUID-typed
            # pk lookup. A bad value (e.g. '-2', a term code) would otherwise make
            # get_object_or_404 raise ValidationError -> HTTP 500. Mirror the PT-1
            # idiom (cis/views/student.py): invalid term -> empty result set.
            try:
                uuid.UUID(term_id)
            except (ValueError, AttributeError, TypeError):
                return Student.objects.none()

            term = get_object_or_404(Term, pk=term_id)
            registrations = registrations.filter(class_section__term=term)

        # Get distinct student IDs from registrations
        student_ids = registrations.distinct('student').values_list('student__id', flat=True)

        # Return students with registrations
        return Student.objects.filter(
            highschool__in=highschools,
            pk__in=student_ids
        ).select_related('user', 'highschool')


# =============================================================================
# Registration ViewSets
# =============================================================================

class RegistrationViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for student registrations visible to HS administrators."""
    serializer_class = HSAdminRegistrationSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        term_id = self.request.GET.get('term', None)
        if term_id == '-2':
            term_id = None
        else:
            term_id = self.request.GET.get('term', active_term().id)

        highschools = get_user_highschools(self.request)

        records = StudentRegistration.objects.filter(
            student__highschool__in=highschools,
        )

        if term_id:
            # PT-fuzz: term_id here is either the active-term UUID (default) or a
            # caller-supplied value. Reject anything that is not a well-formed
            # UUID before it reaches the UUID-typed term filter, which would
            # otherwise raise ValidationError -> HTTP 500. Mirror the PT-1 idiom
            # (cis/views/student.py): invalid term -> empty result set. The '-2'
            # sentinel still means "no term filter" because it set term_id = None
            # above and never enters this branch.
            try:
                uuid.UUID(str(term_id))
            except (ValueError, AttributeError, TypeError):
                return StudentRegistration.objects.none()

            records = records.filter(
                class_section__term__id=term_id
        )

        records = records.select_related(
            'student__user',
            'class_section__course',
            'reviewer__user'
        )
        return records


class StudentRegistrationsTableViewSet(viewsets.ReadOnlyModelViewSet):
    """DataTables feed for the HS-admin student-detail Class(es) table.

    Returns the shared cis ``StudentRegistrationSerializer`` shape (rendered by
    myce_tenant_configs/js/registrations_table.js), scoped to the requesting HS
    admin's high schools and the ``student`` query param. Separate from
    ``RegistrationViewSet`` (which the students-list page consumes) so its shape
    can differ without regressing that page.
    """
    serializer_class = StudentRegistrationSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)
        records = StudentRegistration.objects.filter(
            student__highschool__in=highschools,
        )
        student = self.request.GET.get('student', '').strip()
        if student:
            # PT: `student` feeds a UUIDField lookup (Student.id). Reject
            # non-UUIDs before the ORM (invalid -> empty set, not HTTP 500).
            try:
                uuid.UUID(str(student))
            except (ValueError, AttributeError, TypeError):
                return StudentRegistration.objects.none()
            records = records.filter(student__id=student)
        return records.select_related(
            'student__user', 'student__highschool',
            'class_section__course', 'class_section__term',
            'reviewer__user',
        )


class PendingRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for pending recommendations visible to HS administrators."""
    serializer_class = PendingRecommendationSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)

        return StudentRegistration.get_pending_recommendations(
            highschool_ids=[hs.id for hs in highschools]
        ).distinct('student').select_related(
            'student__user',
            'student__highschool',
            'class_section__course'
        )


class PendingReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for pending reviews visible to HS administrators."""
    serializer_class = PendingReviewSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)

        registrations = StudentRegistration.objects.filter(
            student__highschool__in=highschools
        )

        pending_type = self.request.GET.get('pending_type')
        term_id = self.request.GET.get('term')

        if pending_type == 'by_term':
            if term_id == '-2':
                registrations = registrations.filter(
                    class_section__term__in=registration_terms()
                )
            elif term_id:
                try:
                    registrations = registrations.filter(
                        class_section__term__id=term_id
                    )
                except Exception:
                    return StudentRegistration.objects.none()
        else:
            registrations = registrations.filter(status__in=['applied'])

        return registrations.select_related(
            'student__user',
            'student__highschool',
            'class_section'
        )


# =============================================================================
# Personnel ViewSets
# =============================================================================

class PersonnelViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for personnel visible to HS administrators."""
    serializer_class = PersonnelSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)
        status = self.request.GET.get('status', 'active')

        return HSAdministratorPosition.objects.filter(
            status__iexact=status,
            highschool__in=highschools
        ).select_related(
            'hsadmin__user',
            'highschool',
            'position'
        )


# =============================================================================
# Class Section ViewSets
# =============================================================================

class ClassSectionViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for class sections visible to HS administrators."""
    serializer_class = HSAdminClassSectionSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)
        term_id = self.request.GET.get('term', str(active_term().id)).strip()

        if term_id == '-1' or term_id == '':
            term_id = None

        records = ClassSection.objects.filter(
            highschool__in=highschools
        )

        if term_id:
            records = records.filter(term__id=term_id)

        return records.select_related(
            'course',
            'term',
            'highschool',
            'teacher__user'
        )


# =============================================================================
# Administrator Position ViewSets
# =============================================================================

class AdminPositionViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for administrator positions - returns all highschool/role combinations."""
    serializer_class = HSAdministratorPositionSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        role_ids = self.request.GET.getlist('role_ids')

        highschools = get_user_highschools(self.request)
        queryset = HSAdministratorPosition.objects.filter(
            status__iexact='active',
            highschool__in=highschools
        )

        if role_ids:
            queryset = queryset.filter(position__id__in=role_ids)

        return queryset.select_related('hsadmin__user', 'highschool', 'position')

    def list(self, request, *args, **kwargs):
        """Return all highschool x role combinations, including empty slots."""
        from rest_framework.response import Response
        from cis.models.highschool_administrator import HSPosition

        role_ids = request.GET.getlist('role_ids')
        highschools = get_user_highschools(request)
        roles = HSPosition.objects.filter(id__in=role_ids) if role_ids else HSPosition.objects.none()

        # Build lookup of existing positions by highschool_id + position_id
        existing_positions = {}
        for pos in self.get_queryset():
            key = f"{pos.highschool_id}_{pos.position_id}"
            existing_positions[key] = pos

        # Generate all combinations
        data = []
        for highschool in highschools:
            for role in roles:
                key = f"{highschool.id}_{role.id}"
                pos = existing_positions.get(key)

                if pos:
                    data.append({
                        'id': str(pos.id),
                        'highschool_id': str(pos.highschool_id),
                        'highschool_name': pos.highschool.name,
                        'position_id': str(pos.position_id),
                        'position_name': pos.position.name,
                        'admin_name': f"{pos.hsadmin.user.last_name}, {pos.hsadmin.user.first_name}",
                        'admin_email': pos.hsadmin.user.email,
                        'status': pos.status,
                    })
                else:
                    data.append({
                        'id': None,
                        'highschool_id': str(highschool.id),
                        'highschool_name': highschool.name,
                        'position_id': str(role.id),
                        'position_name': role.name,
                        'admin_name': None,
                        'admin_email': None,
                        'status': None,
                    })

        return Response(data)

    @action(detail=False, methods=['get', 'post'], url_path='assign')
    def assign(self, request):
        """Assign an administrator to a highschool/role position."""
        if request.method == 'GET':
            highschool_id = request.GET.get('highschool_id')
            role_id = request.GET.get('role_id')
            administrator_id = request.GET.get('administrator_id')
        else:
            highschool_id = request.data.get('highschool_id') or request.data.get('highschool')
            role_id = request.data.get('role_id') or request.data.get('position')
            administrator_id = request.data.get('administrator_id') or request.data.get('administrator')

        if not highschool_id or not role_id:
            return Response({
                'status': 'error',
                'message': 'highschool_id and role_id are required'
            }, status=400)

        # Verify user has access to this highschool
        highschools = get_user_highschools(request)
        highschool = get_object_or_404(HighSchool, pk=highschool_id)
        if highschool not in highschools:
            raise PermissionDenied("No access to this highschool")

        fs_config = _get_fs_config()
        form = HSAdministratorPositionForm(request, highschool_id, role_id, administrator_id)

        if request.method == 'POST':
            # Ensure FutureProjection exists for tracking
            _get_or_create_future_projection(highschool_id, request.user)

            form = HSAdministratorPositionForm(
                request, highschool_id, role_id, administrator_id, data=request.POST
            )

            if form.is_valid():
                form.save(request)
                return Response({
                    'status': 'Success',
                    'message': 'Successfully assigned high school administrator',
                    'action': 'reload_table'
                })
            else:
                return Response({
                    'message': 'Please correct the errors and try again.',
                    'details': '',
                    'errors': form.errors.as_json(),
                    'status': 'error'
                }, status=400)

        context = {
            'form': form,
            'new_teacher_message': fs_config.get('edit_role_message', 'change me'),
            'form_action_url': request.build_absolute_uri(),
        }
        return render(request, 'highschool_admin/add_new_teacher.html', context)


# =============================================================================
# Course Request ViewSets
# =============================================================================

class CourseRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for course requests - TeacherCourseCertificate with offering status."""
    serializer_class = CourseRequestSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        from cis.settings.future_sections import future_sections as fs_settings
        fs_config = fs_settings.from_db()

        highschools = get_user_highschools(self.request)

        return TeacherCourseCertificate.objects.filter(
            teacher_highschool__highschool__in=highschools,
            course__status__in=fs_config.get('course_status', []),
            status__in=fs_config.get('teacher_course_status', [])
        ).select_related(
            'course',
            'teacher_highschool__teacher__user',
            'teacher_highschool__highschool'
        )

    def list(self, request, *args, **kwargs):
        """Return course requests with merged offering status from FutureCourse."""
        from rest_framework.response import Response
        from cis.settings.future_sections import future_sections as fs_settings

        fs_config = fs_settings.from_db()
        academic_year_id = fs_config.get('academic_year')
        academic_year = AcademicYear.objects.filter(pk=academic_year_id).first()
        window_is_open = FutureCourse.is_window_open()

        # Get course certificates
        queryset = self.get_queryset()

        # Build lookup of FutureCourse by teacher_course certificate_id
        future_courses = FutureCourse.objects.filter(
            teacher_course__in=queryset,
            academic_year=academic_year
        ).select_related('teacher_course')

        offering_lookup = {}
        for fc in future_courses:
            offering_lookup[str(fc.teacher_course.certificate_id)] = {
                'teaching': fc.section_info.get('teaching') if fc.section_info else None,
                'sections': fc.section_info.get('sections', []) if fc.section_info else [],
                'section_display': fc.section_display,  # Pre-formatted display from settings
            }

        # Build response data
        data = []
        for course in queryset:
            cert_id = str(course.certificate_id)
            offering = offering_lookup.get(cert_id, {})

            data.append({
                'certificate_id': cert_id,
                'course_title': course.course.title,
                'teacher_name': str(course.teacher_highschool.teacher),
                'status': course.status,
                'highschool_name': course.teacher_highschool.highschool.name,
                'academic_year_id': str(academic_year.id) if academic_year else None,
                'window_is_open': window_is_open,
                'offering_status': offering.get('teaching'),
                'sections': offering.get('sections', []),
                'section_display': offering.get('section_display', []),
            })

        return Response(data)


# =============================================================================
# Certificate ViewSets
# =============================================================================

class HSAdminCertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """API ViewSet for instructor course certificates visible to HS admins,
    scoped to the admin's administered high schools."""
    serializer_class = HSAdminCertificateSerializer
    permission_classes = [HSADMIN_user_only]

    def get_queryset(self):
        highschools = get_user_highschools(self.request)
        return TeacherCourseCertificate.objects.filter(
            teacher_highschool__highschool__in=highschools
        ).select_related(
            'course', 'teacher_highschool__teacher__user',
            'teacher_highschool__highschool'
        ).order_by('expires_on')


# =============================================================================
# Future Sections Action ViewSets
# =============================================================================

def _get_fs_config():
    """Get future sections configuration from database."""
    return fs_settings.from_db()


def _get_or_create_future_projection(highschool_id, user):
    """
    Get or create a FutureProjection for a highschool and academic year.

    Args:
        highschool_id: UUID of the highschool
        user: The user creating the projection

    Returns:
        FutureProjection instance
    """
    fs_config = _get_fs_config()
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


def _add_history_entry(obj, user, action):
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


class FutureSectionsActionViewSet(viewsets.ViewSet):
    """API ViewSet for future sections actions (mark teaching, not teaching, etc.)."""
    permission_classes = [HSADMIN_user_only]

    def _validate_highschool_access(self, request, teacher_course):
        """Verify user has access to the teacher's highschool."""
        highschools = get_user_highschools(request)
        if teacher_course.teacher_highschool.highschool not in highschools:
            raise PermissionDenied("No access to this highschool")

    @action(detail=False, methods=['get', 'post'], url_path='mark-teaching')
    def mark_teaching(self, request):
        """Mark a course as teaching with section details."""
        # Handle both GET (form params) and POST (data params)
        # Also handle legacy field name 'teacher_course_certificate_id' from form
        if request.method == 'GET':
            course_certificate_id = request.GET.get('course_certificate_id')
            academic_year_id = request.GET.get('academic_year_id')
        else:
            course_certificate_id = (
                request.data.get('course_certificate_id') or
                request.data.get('teacher_course_certificate_id') or
                request.POST.get('teacher_course_certificate_id')
            )
            academic_year_id = (
                request.data.get('academic_year_id') or
                request.POST.get('academic_year_id')
            )

        if not course_certificate_id or not academic_year_id:
            return Response({
                'status': 'error',
                'message': 'course_certificate_id and academic_year_id are required'
            }, status=400)

        teacher_course = get_object_or_404(
            TeacherCourseCertificate,
            certificate_id=course_certificate_id
        )
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)

        # Verify access
        self._validate_highschool_access(request, teacher_course)

        TeachingFormSet = formset_factory(
            TeacherCourseSectionForm,
            formset=TeacherCourseBaseLinkFormSet,
            extra=1
        )

        future_course = FutureCourse.get_or_add(teacher_course, academic_year, submitter=request.user)

        if future_course.section_info == {}:
            future_course.section_info = {'teaching': 'yes', 'sections': []}
            future_course.save()

        initial_data = future_course.section_info.get('sections', []) if future_course.section_info else []

        if request.method == 'POST':
            teacher_course_teaching_form = TeacherCourseTeachingForm(request.POST)
            teaching_formset = TeachingFormSet(request.POST)

            # Get or create FutureProjection
            highschool_id = teacher_course.teacher_highschool.highschool.id
            fp = _get_or_create_future_projection(highschool_id, request.user)

            if teacher_course_teaching_form.is_valid() and teaching_formset.is_valid():
                section_info = []

                for index, teaching_form in enumerate(teaching_formset):
                    if teaching_form.cleaned_data and teaching_form.cleaned_data.get('term'):
                        # Handle file upload
                        uploaded_file = request.FILES.get(f'form-{index}-syllabus')
                        if uploaded_file:
                            from cis.backends.storage_backend import PrivateMediaStorage
                            from django.utils.text import get_valid_filename

                            media_storage = PrivateMediaStorage()
                            safe_filename = get_valid_filename(uploaded_file.name)
                            path = f"future_section/{future_course.id}/{safe_filename}"
                            path = media_storage.save(path, uploaded_file)
                            teaching_form.cleaned_data['file'] = media_storage.url(path)

                        section_info.append(teaching_form.cleaned_data)

                # Update future course
                future_course.section_info = {'teaching': 'yes', 'sections': section_info}
                if not future_course.meta:
                    future_course.meta = {'fp': str(fp.id), 'history': []}
                else:
                    future_course.meta['fp'] = str(fp.id)

                _add_history_entry(
                    future_course, request.user,
                    f'Marked as teaching - {future_course} {len(section_info)} section(s)'
                )
                future_course.save()

                # Update projection history
                _add_history_entry(fp, request.user, f'Marked as teaching - {future_course}')
                fp.save()

                return Response({
                    'status': 'Success',
                    'message': 'Successfully saved course information',
                    'action': 'reload_table'
                })
            else:
                # Build error response
                errors = {}
                for index, err in enumerate(teaching_formset.errors):
                    for field, error_message in err.items():
                        errors[f"form-{index}-{field}"] = [{'message': error_message}]

                return Response({
                    'message': 'Please correct the errors and try again.',
                    'details': mark_safe(str(teaching_formset.non_form_errors())),
                    'errors': json.dumps(errors),
                    'status': 'error'
                }, status=400)
        else:
            # GET request - render form
            teacher_course_teaching_form = TeacherCourseTeachingForm(
                initial={
                    'teacher_course_certificate_id': teacher_course.certificate_id,
                    'academic_year_id': academic_year.id,
                }
            )
            teaching_formset = TeachingFormSet(initial=initial_data)

        fs_config = _get_fs_config()
        context = {
            'teacher_course_teaching_form': teacher_course_teaching_form,
            'teaching_formset': teaching_formset,
            'teacher_course': teacher_course,
            'academic_year': academic_year,
            'teaching_message': fs_config.get('teaching_message', 'change me')
        }
        return render(request, 'highschool_admin/teaching_course.html', context)

    @action(detail=False, methods=['get', 'post'], url_path='mark-not-teaching')
    def mark_not_teaching(self, request):
        """Mark a course as not being taught for an academic year."""
        # Handle both GET (form params) and POST (data params)
        if request.method == 'GET':
            course_certificate_id = request.GET.get('course_certificate_id')
            academic_year_id = request.GET.get('academic_year_id')
        else:
            course_certificate_id = request.data.get('course_certificate_id')
            academic_year_id = request.data.get('academic_year_id')

        if not course_certificate_id or not academic_year_id:
            return Response({
                'status': 'error',
                'message': 'course_certificate_id and academic_year_id are required'
            }, status=400)

        teacher_course = get_object_or_404(
            TeacherCourseCertificate,
            certificate_id=course_certificate_id
        )
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)

        # Verify access
        self._validate_highschool_access(request, teacher_course)

        highschool_id = teacher_course.teacher_highschool.highschool.id
        fp = _get_or_create_future_projection(highschool_id, request.user)

        future_course = FutureCourse.get_or_add(
            teacher_course,
            academic_year,
            {'teaching': 'no'},
            submitter=request.user
        )

        if not future_course.meta:
            future_course.meta = {'fp': str(fp.id), 'history': []}

        _add_history_entry(future_course, request.user, 'Marked as not teaching')
        future_course.save()

        _add_history_entry(fp, request.user, f'Marked as not teaching course {future_course}')
        fp.save()

        return Response({
            'display': 'swal',
            'status': 'success',
            'message': 'Successfully marked course as not teaching',
            'action': 'reload_future_courses'
        })

    @action(detail=False, methods=['get', 'post', 'delete'], url_path='remove-teaching-status')
    def remove_teaching_status(self, request):
        """Remove teaching/not-teaching status for a course."""
        # PT-38: enforce the Future Sections submission window on the server.
        # The UI hides these controls when the window is closed, but a direct
        # request must also be rejected so offering data cannot be removed
        # outside the intended window. Reuses FutureCourse.is_window_open()
        # (the same check the course-requests list endpoint and page views use).
        if not FutureCourse.is_window_open():
            return Response({
                'display': 'swal',
                'status': 'error',
                'message': 'The submission window is closed. Changes are not allowed.',
            }, status=403)

        # Handle both GET (form params) and POST/DELETE (data params)
        if request.method == 'GET':
            course_certificate_id = request.GET.get('course_certificate_id')
            academic_year_id = request.GET.get('academic_year_id')
        else:
            course_certificate_id = request.data.get('course_certificate_id')
            academic_year_id = request.data.get('academic_year_id')

        if not course_certificate_id or not academic_year_id:
            return Response({
                'status': 'error',
                'message': 'course_certificate_id and academic_year_id are required'
            }, status=400)

        # Check teacher course exists and user has access
        teacher_course = get_object_or_404(
            TeacherCourseCertificate,
            certificate_id=course_certificate_id
        )
        self._validate_highschool_access(request, teacher_course)

        future_course_qs = FutureCourse.objects.filter(
            teacher_course__certificate_id=course_certificate_id,
            academic_year__id=academic_year_id
        )

        if future_course_qs.exists():
            future_course = future_course_qs.first()
            fp_id = future_course.meta.get('fp') if future_course.meta else None

            if fp_id:
                fp = FutureProjection.objects.filter(pk=fp_id).first()
                if fp:
                    _add_history_entry(fp, request.user, f'Removed course info {future_course}')
                    fp.save()

            future_course_qs.delete()

        return Response({
            'display': 'swal',
            'status': 'success',
            'message': 'Successfully removed course information',
            'action': 'reload_future_courses'
        })

    @action(detail=False, methods=['get', 'post'], url_path='add-teacher')
    def add_teacher(self, request):
        """Add a new teacher course certificate."""
        # Handle both GET (form params) and POST (data params)
        if request.method == 'GET':
            academic_year_id = request.GET.get('academic_year_id')
            course_type = request.GET.get('course_type', 'pathways')
        else:
            academic_year_id = request.data.get('academic_year_id')
            course_type = request.data.get('course_type', 'pathways')

        if not academic_year_id:
            return Response({
                'status': 'error',
                'message': 'academic_year_id is required'
            }, status=400)

        fs_config = _get_fs_config()
        academic_year = get_object_or_404(AcademicYear, pk=academic_year_id)
        form = AddNewTeacherForm(request, academic_year, course_type)

        if request.method == 'POST':
            form = AddNewTeacherForm(request, academic_year, course_type, data=request.POST)

            if form.is_valid():
                record = form.save(request, academic_year)

                if record.teacher_course.status in fs_config.get('create_new_instructor_app', []):
                    record.create_teacher_application()

                # Ensure FutureProjection exists
                highschool_id = record.teacher_course.teacher_highschool.highschool.id
                _get_or_create_future_projection(highschool_id, request.user)

                return Response({
                    'status': 'Success',
                    'message': 'Successfully added course',
                    'action': 'reload'
                })
            else:
                return Response({
                    'message': 'Please correct the errors and try again.',
                    'details': '',
                    'errors': form.errors.as_json(),
                    'status': 'error'
                }, status=400)

        context = {
            'academic_year': academic_year,
            'form': form,
            'new_teacher_message': fs_config.get('new_teacher_message', 'change me'),
            'form_action_url': request.build_absolute_uri(),
        }
        return render(request, 'highschool_admin/add_new_teacher.html', context)