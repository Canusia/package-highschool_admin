from django.shortcuts import get_object_or_404

from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import HSAdministrator
from cis.views.ajax import add_new


def get_current_hsadmin(request):
    """Get the HSAdministrator instance for the current user, or None for anonymous."""
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        return get_object_or_404(HSAdministrator, user__id=user.id)
    except Exception:
        return None


def get_user_highschools(request):
    """Get highschools the current user can manage. Empty queryset for anonymous."""
    hsadmin = get_current_hsadmin(request)
    if hsadmin is None:
        return HighSchool.objects.none()
    return hsadmin.get_highschools()


def get_user_recommendation_highschools(request):
    """Highschools where the current user may manage student recommendations.

    Narrower than :func:`get_user_highschools` — use it anywhere pending
    recommendation work is listed or counted, so an admin is not shown work
    they hold no permission to act on.
    """
    hsadmin = get_current_hsadmin(request)
    if hsadmin is None:
        return HighSchool.objects.none()
    return hsadmin.get_recommendation_highschools()


def get_hsadmin_menu():
    """Resolve the highschool_admin portal menu from the ``cis.settings.menu``
    Setting, falling back to the legacy :data:`cis.menu.HS_ADMIN_MENU` list when
    the Setting is missing or its stored JSON is unparseable.

    Returned as a list of nav-item dicts. Pass it to ``draw_menu`` as the data
    argument and use it for the dashboard ``nav_items`` tiles so both share one
    source of truth.
    """
    import json

    from cis.menu import HS_ADMIN_MENU
    from cis.settings.menu import menu as menu_settings

    conf = menu_settings.from_db()
    try:
        return json.loads(conf.get('highschool_admin_menu'))
    except (TypeError, ValueError):
        return HS_ADMIN_MENU


def ajax_requests(request):
    """Generic AJAX handler for adding new records."""
    return add_new(request)
