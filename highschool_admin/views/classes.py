from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseNotFound

from cis.models.section import ClassSection
from cis.models.term import Term
from cis.menu import draw_menu
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang
from cis.utils import registration_terms, active_term

from ..services.section_scope import visible_sections
from .utils import get_hsadmin_menu


def class_section(request, record_id):
    """Individual class section detail page."""
    menu = draw_menu(get_hsadmin_menu(), 'classes', '', 'highschool_admin')

    class_section_info = get_object_or_404(ClassSection, pk=record_id)

    # The list and this guard share one predicate, so a listed section always
    # opens and an unlisted one always 404s (#3).
    if not visible_sections(request).filter(pk=class_section_info.pk).exists():
        return HttpResponseNotFound('Class section not found')

    students_in_class = class_section_info.get_students()

    if request.GET.get('action') == 'download_roster_pdf':
        return class_section_info.download_roster_pdf()

    return render(
        request,
        'highschool_admin/class_section.html',
        {
            'menu': menu,
            'record': class_section_info,
            'intro': portal_lang(request).from_db().get('class_blurb', 'Change me'),
            'registered_students': students_in_class
        })


def classes(request):
    """Classes list page."""
    menu = draw_menu(get_hsadmin_menu(), 'classes', 'classes', 'highschool_admin')

    return render(
        request,
        'highschool_admin/classes.html',
        {
            'menu': menu,
            'classes_api': '/highschool_admin/api/class-section/?format=datatables',
            'intro': portal_lang(request).from_db().get('classes_blurb', 'Change me'),
            'terms': Term.objects.all().order_by('-code'),
            'active_term': active_term(),
        })


def course_search(request):
    """Course search page."""
    return render(
        request,
        'highschool_admin/course_search.html',
        {
            'is_registration_open': True,
            'registration_terms': registration_terms(),
            'intro': portal_lang(request).from_db().get('course_search_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'course_search', '', 'highschool_admin')
        })
