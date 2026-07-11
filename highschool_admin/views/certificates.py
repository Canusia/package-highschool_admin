from django.shortcuts import render

from cis.menu import draw_menu
from .utils import get_hsadmin_menu
from cis.services.table_configs import get_table_config
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

build_credentials_table = get_table_config('credentials_table').build_config


def index(request):
    """Course certificates for all instructors at the admin's high school(s).

    Reuses the CE credentials table (CredentialExpiryViewSet scopes to the
    caller's high schools for highschool_admin callers) via a read-only variant
    that includes the Instructor column.
    """
    return render(
        request,
        'highschool_admin/certificates.html',
        {
            'menu': draw_menu(get_hsadmin_menu(), 'certificates', '', 'highschool_admin'),
            'intro': portal_lang(request).from_db().get('certificates_blurb', 'Change me'),
            'credentials_table': build_credentials_table(
                variant='credentials_hsadmin',
                api_url='/ce/api/credential-expiry?format=datatables',
            ),
        })
