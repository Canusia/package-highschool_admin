"""HS-admin Instructor Course Certificates page: the viewset must be scoped to
the calling admin's administered high schools (via get_user_highschools)."""
import datetime

from django.test import TestCase
from django.utils import timezone

from cis.models.customuser import CustomUser
from cis.models.teacher import Teacher, TeacherHighSchool, TeacherCourseCertificate
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.course import Course, Cohort
from ..views.api.viewsets import HSAdminCertificateViewSet


class _Req:
    def __init__(self, user, params=None):
        self.user = user
        self.GET = params or {}


class HSAdminCertificateViewSetTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        for _g in ('instructor', 'highschool_admin', 'teacher', 'faculty'):
            Group.objects.get_or_create(name=_g)

        self.admin_user = CustomUser.objects.create(username='hsa', email='hsa@x.com')
        self.hs_a = HighSchool.objects.create(name='HS A', status='Active')
        self.hs_b = HighSchool.objects.create(name='HS B', status='Active')
        self.admin = HSAdministrator.objects.create(user=self.admin_user)

        # Associate self.admin with hs_a ONLY. HSAdministrator.get_highschools()
        # returns HighSchools that have an HSAdministratorPosition with
        # status='Active' for this admin, so create exactly that link to hs_a.
        position = HSPosition.objects.create(name='Counselor')
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs_a,
            position=position, status='Active',
        )

        tuser = CustomUser.objects.create(username='t', email='t@x.com',
                                          first_name='T', last_name='R')
        teacher = Teacher.objects.create(user=tuser, status='active')
        cohort = Cohort.objects.create(name='Eng', designator='ENGL&')
        course = Course.objects.create(
            name='ENGL& 101', status='Active', cohort=cohort,
            title='Eng', catalog_number='101')
        cohort2 = Cohort.objects.create(name='Math', designator='MATH&')
        course2 = Course.objects.create(
            name='MATH& 141', status='Active', cohort=cohort2,
            title='Math', catalog_number='141')
        ths_a = TeacherHighSchool.objects.create(
            teacher=teacher, highschool=self.hs_a, status='In the Program')
        ths_b = TeacherHighSchool.objects.create(
            teacher=teacher, highschool=self.hs_b, status='In the Program')
        self.in_scope = TeacherCourseCertificate.objects.create(
            teacher_highschool=ths_a, course=course, status='Teaching',
            expires_on=timezone.localdate() + datetime.timedelta(days=30))
        self.out_scope = TeacherCourseCertificate.objects.create(
            teacher_highschool=ths_b, course=course2, status='Teaching')

    def test_only_my_highschool_certificates(self):
        vs = HSAdminCertificateViewSet()
        vs.request = _Req(self.admin_user)
        ids = set(vs.get_queryset().values_list('id', flat=True))
        self.assertEqual(ids, {self.in_scope.id})
