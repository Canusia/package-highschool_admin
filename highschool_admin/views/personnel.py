from django.shortcuts import render

from cis.menu import draw_menu
from .utils import get_hsadmin_menu
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang


def personnel(request):
    """Personnel list page."""
    return render(
        request,
        'highschool_admin/personnel.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'administrators', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('administrators_blurb', 'Change me'),
        })
