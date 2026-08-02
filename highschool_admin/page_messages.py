"""highschool_admin page-message providers (auto-discovered by cis.apps.ready)."""
import importlib.util

from cis.page_messages import page_message, PageMessage
from .views.utils import get_user_highschools, get_user_recommendation_highschools
from .settings.student_tabs import student_tabs


def _pending_recommendation_count(request):
    from cis.models.section import StudentRegistration
    highschools = get_user_recommendation_highschools(request)
    return StudentRegistration.get_pending_recommendations(
        highschool_ids=[hs.id for hs in highschools]
    ).count()


@page_message('highschool_admin', 'dashboard')
def pending_recommendations(request):
    if not student_tabs.show_recommendation():
        return None
    if _pending_recommendation_count(request) > 0:
        return PageMessage(
            text='There are student application(s) needing recommendation.',
            level='danger', tile_id='id_tile_students')
    return None


@page_message('highschool_admin', 'dashboard')
def pending_pay_type(request):
    from cis.models.section import StudentRegistration
    highschools = get_user_highschools(request)
    count = StudentRegistration.objects.filter(
        student__highschool__id__in=highschools.values_list('id', flat=True),
        pay_type__in=['', None],
        status__in=['applied'],
    ).count()
    if count > 0:
        return PageMessage(
            text='There are student application(s) needing payment type review.',
            level='danger', tile_id='id_tile_students')
    return None


@page_message('highschool_admin', 'dashboard')
def pending_drop_requests(request):
    if importlib.util.find_spec('drop_wd.drop_wd'):
        from drop_wd.drop_wd.models import DropWDRequest
    else:
        from drop_wd.models import DropWDRequest
    highschools = get_user_highschools(request)
    count = DropWDRequest.objects.filter(
        registration__student__highschool__id__in=highschools.values_list('id', flat=True),
        status__in=['requested'],
    ).count()
    if count > 0:
        return PageMessage(
            text='There are student drop request(s) needing review.',
            level='danger', tile_id='id_tile_drop_wd_requests')
    return None


def _future_course():
    """Resolve FutureCourse via the editable-submodule conditional import."""
    if importlib.util.find_spec('future_sections.future_sections'):
        from future_sections.future_sections.models import FutureCourse
    else:
        from future_sections.models import FutureCourse
    return FutureCourse


@page_message('highschool_admin', 'future_sections')
def projection_window_closed(request):
    if not _future_course().is_window_open():
        return PageMessage(
            text='The course projection window is currently closed.',
            level='warning')
    return None
