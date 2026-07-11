import importlib.util
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy

from cis.models.customuser import CustomUser
from cis.models.student import Student
from cis.menu import draw_menu
from cis.forms.student import StudentProfileForm, UserPasswordChangeForm
from cis.page_messages import get_page_messages
from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang

from .utils import get_current_hsadmin, get_user_highschools, get_hsadmin_menu


def dashboard(request):
    """High school admin dashboard/home page."""
    user = get_current_hsadmin(request)

    menu = get_hsadmin_menu()

    import importlib.util
    if importlib.util.find_spec('announcement.announcement'):
        from announcement.announcement.views.views import get_announcements
    else:
        from announcement.views.views import get_announcements
    announcements = get_announcements(request, 'highschool_admin')

    from cis.views.password_management import cisForceSetPasswordForm
    dashboard_url = reverse_lazy('highschool_admin:dashboard')
    form = cisForceSetPasswordForm(user.user, form_action=dashboard_url, use_ajax=False)

    if request.method == 'POST':
        form = cisForceSetPasswordForm(request.user, request.POST, form_action=dashboard_url, use_ajax=False)
        if form.is_valid():
            form.save(request.user)
            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated password.',
                'list-group-item-success'
            )
            return redirect('highschool_admin:dashboard')

    return render(
        request,
        'highschool_admin/dashboard.html',
        {
            'menu': draw_menu(menu, 'home', '', 'highschool_admin'),
            'page_messages': get_page_messages('highschool_admin', 'dashboard', request),
            'form': form,
            'side_bar': portal_lang(request).from_db().get('side_bar_blurb', 'Change me'),
            'intro': portal_lang(request).from_db().get('home_blurb', 'Change me'),
            'announcements': announcements,
            'nav_items': menu
        })


def profile(request):
    """Profile management page."""
    student = Student.objects.get(user__id=request.user.id)
    form = StudentProfileForm(student, request)

    if request.method == 'POST' and request.POST.get('update_profile') == 'Update Profile':
        form = StudentProfileForm(student, request, request.POST)
        if form.is_valid():
            student.update_profile(form)
            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated profile.',
                'list-group-item-success')
            return redirect('student:profile')

    return render(
        request,
        'student/profile.html',
        {
            'form': form,
            'intro': portal_lang(request).from_db().get('profile_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'profile', '', 'highschool_admin')
        })


def manage_password(request):
    """Password change page."""
    hsadmin = get_current_hsadmin(request)
    form = UserPasswordChangeForm()

    if request.method == 'POST' and request.POST.get('update_password') == 'Update Password':
        user = CustomUser.objects.get(pk=hsadmin.user.id)
        form = UserPasswordChangeForm(user, request.POST)

        if form.is_valid():
            user.set_password(form.cleaned_data['password'])
            user.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated password. Please login again.',
                'list-group-item-success')
            return redirect('highschool_admin:manage_password')

    return render(
        request,
        'highschool_admin/manage_password.html',
        {
            'form': form,
            'intro': portal_lang(request).from_db().get('manage_password_blurb', 'Change me'),
            'menu': draw_menu(get_hsadmin_menu(), 'manage_password', '', 'highschool_admin')
        })
