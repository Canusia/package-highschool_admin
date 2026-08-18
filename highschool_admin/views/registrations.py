from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse_lazy

from cis.models.highschool_administrator import HSAdministrator
from cis.models.section import StudentRegistration
from cis.models.term import Term
from cis.utils import registration_terms, active_term

from ..services.registration import can_update_pay_type, pending_review_statuses
from .utils import get_user_highschools


def get_registrations_for_term(request, term_id=None):
    """JSON API endpoint for registrations in a term."""
    highschools = get_user_highschools(request)
    term_id = request.GET.get('term', active_term().id)

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
                'record_id': registration.student.id
            })
        })
    return JsonResponse(result)


def update_registration_status(request):
    """Update registration status and pay type."""
    # PT-18: a highschool_admin may only edit registrations whose student
    # belongs to one of the high schools they administer. Deny (403) anything
    # out of scope, missing, or malformed before any mutation.
    from django.core.exceptions import ValidationError
    try:
        record = StudentRegistration.objects.get(
            pk=request.GET.get('id'),
            student__highschool__in=get_user_highschools(request),
        )
    except (StudentRegistration.DoesNotExist, ValidationError, ValueError, TypeError):
        return JsonResponse(
            {'status': 'error', 'message': 'You are not authorized to perform this action.'},
            status=403,
        )

    # Tenant policy gate, applied before the review-window check on purpose:
    # a caller who may not edit this registration gets the same 403 whether or
    # not the window happens to be open, so the response leaks no window state
    # and the denial cannot be timed around.
    if not can_update_pay_type(record, request.user):
        return JsonResponse(
            {'status': 'error', 'message': 'You are not authorized to perform this action.'},
            status=403,
        )

    from cis.utils import is_pay_type_review_open

    if is_pay_type_review_open():
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
                'html': message,
            },
            status=200
        )

    return JsonResponse({
        'status': 'error',
        'message': 'Review period is not open'
    }, status=401)


def get_pending_pay_type(request):
    """JSON API endpoint for registrations pending pay type."""
    highschools = get_user_highschools(request)

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
            except Exception:
                registrations_for_term = StudentRegistration.objects.none()
    else:
        registrations_for_term = registrations_for_term.filter(
            status__in=pending_review_statuses()
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
            'id': registration.id,
            'action': registration.pay_type_actions_sexy(),
            'psid': registration.student.user.psid,
            'current_balance': registration.student.current_balance
        })
    return JsonResponse(result)
