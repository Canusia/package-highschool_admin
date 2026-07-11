import os

from django.apps import AppConfig


class HighschoolAdminConfig(AppConfig):
    """Production config — used when this package is pip-installed as the
    top-level `highschool_admin`."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'highschool_admin'
    label = 'highschool_admin'
    verbose_name = 'High School Admin'
    path = os.path.dirname(os.path.abspath(__file__))

    CONFIGURATORS = [
        {
            'app': 'highschool_admin',
            'name': 'student_tabs',
            'title': 'Student Page Tabs',
            'description': 'Show/hide the Recommendation, Review, and Pay Type '
                           'tabs on the students pages.',
            'categories': ['1'],
        },
    ]


class DevHighschoolAdminConfig(HighschoolAdminConfig):
    """Development config — used when this submodule is checked out under
    `webapp/highschool_admin/`, making the inner package importable as
    `highschool_admin.highschool_admin`."""
    name = 'highschool_admin.highschool_admin'
    label = 'highschool_admin'
    verbose_name = 'Dev - High School Admin'

    CONFIGURATORS = [
        {
            'app': 'highschool_admin.highschool_admin',
            'name': 'student_tabs',
            'title': 'Student Page Tabs',
            'description': 'Show/hide the Recommendation, Review, and Pay Type '
                           'tabs on the students pages.',
            'categories': ['1'],
        },
    ]
