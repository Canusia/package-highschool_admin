"""The student-detail recommendation UI is a single tab (not per-term)."""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

import uuid

from highschool_admin.highschool_admin.tests.test_student_detail_tabs import (
    _login, _provision_groups, _provision_menu, _provision_registration_setting,
)
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition, HSPosition,
)
from cis.models.student import Student
from cis.models.term import AcademicYear, Term
from cis.models.course import Cohort, Course
from cis.models.section import ClassSection, StudentRegistration
from cis.models.settings import Setting

User = get_user_model()


def _u(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


class RecommendationTabTests(TestCase):
    def setUp(self):
        _provision_groups()
        _provision_menu()
        _provision_registration_setting()

        self.hs = HighSchool.objects.create(name='HS')
        self.user = User.objects.create(email='a@x.com', username='a@x.com')
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=f'Pos-{uuid.uuid4().hex[:8]}')
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs,
            position=position, status='Active',
        )
        su = User.objects.create(email='s@x.com', username='s@x.com')
        self.student = Student.objects.create(user=su, highschool=self.hs)

    def test_single_recommendation_tab_no_per_term_tabs(self):
        c = _login(self.user)
        resp = c.get(reverse('highschool_admin:student', args=[self.student.id]))
        self.assertEqual(resp.status_code, 200)
        # Page renders without the removed term_data/#term_rec_* machinery:
        self.assertNotContains(resp, 'href="#term_rec_')


class RecommendationTabRecEligibleTests(TestCase):
    """A student with a real rec-eligible registration must actually see the
    collapsed #recommendation pane (not the guarded-out empty case above).

    Student.needs_recommendation() gates `record.needs_recommendation` in
    highschool_admin/templates/highschool_admin/student.html; it requires an
    'applied' StudentRegistration whose class_section.course.registration_eligibility
    contains f'{student.grade_level}*', with class_section.term in
    registration_terms() and no existing StudentRecommendation for that term.
    """

    def setUp(self):
        _provision_groups()
        _provision_menu()

        # StudentRegistration's post_save signal calls Student.add_note(),
        # which falls back to the 'cron' system user when no request user
        # is present.
        User.objects.get_or_create(username='cron', defaults={'email': 'cron@example.com'})

        self.hs = HighSchool.objects.create(name=_u('HS'))

        self.user = User.objects.create(email=f'{_u("admin")}@x.com', username=_u('admin'))
        self.user.groups.add(Group.objects.get_or_create(name='highschool_admin')[0])
        self.admin = HSAdministrator.objects.create(user=self.user)
        position = HSPosition.objects.create(name=_u('Pos'))
        # The recommendation UI and the POST handler are both gated on
        # HSAdministrator.can_manage_student_recommendation(), so this fixture
        # has to grant the permission explicitly to exercise the permitted path.
        HSAdministratorPosition.objects.create(
            hsadmin=self.admin, highschool=self.hs,
            position=position, status='Active',
            meta={'manage_student_recommendation': 'Yes'},
        )

        ay = AcademicYear.objects.create(name=_u('AY'))
        self.term = Term.objects.create(academic_year=ay, code='F25', label=_u('Fall'))

        cohort = Cohort.objects.create(name=_u('Cohort'), designator='CO')
        # Freshman-eligible course: registration_eligibility must contain
        # f'{grade_level}*' for both Student.needs_recommendation() (the tab
        # gate) and StudentRegistration.needs_recommendation() (the per-row
        # select gate).
        self.course = Course.objects.create(
            catalog_number='101', title='Intro', name=_u('COURSE'),
            cohort=cohort, credit_hours=3,
            registration_eligibility=['FR*'],
        )
        self.section = ClassSection.objects.create(
            term=self.term, course=self.course,
            class_number=_u('CN'), section_number='01',
            highschool=self.hs,
        )

        su = User.objects.create(email=f'{_u("stu")}@x.com', username=_u('stu'))
        self.student = Student.objects.create(
            user=su, highschool=self.hs, grade_level='FR',
        )
        self.registration = StudentRegistration.objects.create(
            student=self.student, class_section=self.section,
            status='applied', status_changed_on={},
        )

        # registration_terms() reads this Setting; the term must be listed
        # or Student.has_recommendation()/needs_recommendation() and the
        # view's rec_registrations filter never see this registration.
        from django.conf import settings as dj_settings
        key = f'{dj_settings.CAMPUS_CODE_PREFIX}_cis_registrations'
        Setting.objects.update_or_create(
            key=key, defaults={'value': {'registration_terms': [str(self.term.id)]}},
        )

    def _url(self):
        return reverse('highschool_admin:student', args=[self.student.id])

    def test_fixture_is_actually_rec_eligible(self):
        # Guard against a silently-vacuous fixture: if this is False, the
        # assertions below would pass even with a broken/regressed tab.
        self.assertTrue(self.student.needs_recommendation())
        self.assertTrue(self.registration.needs_recommendation())

    def test_collapsed_recommendation_pane_renders_for_rec_eligible_student(self):
        c = _login(self.user)
        resp = c.get(self._url())
        self.assertEqual(resp.status_code, 200)

        # The collapsed single tab/pane is present...
        self.assertContains(resp, 'href="#recommendation"')
        self.assertContains(resp, 'id="recommendation"')
        # ...and the old per-term tab markup is gone.
        self.assertNotContains(resp, 'href="#term_rec_')
        # The per-course approve/deny select for our applied, rec-eligible
        # registration proves the pane actually rendered its course rows
        # (not just an empty guarded-out shell).
        self.assertContains(
            resp, f'name="registration_{self.registration.id}"')

    def test_post_recommendation_sets_hsadmin_reviewer(self):
        """Submitting the recommendation form must set
        StudentRegistration.reviewer to the logged-in HS admin's
        HSAdministrator record (StudentRegistration.reviewer is a FK to
        cis.HSAdministrator, NOT to CustomUser). Prior to the fix in
        myce_tenant_configs/services/recommendation_form.py, save() did
        `reg.reviewer = request.user` (a CustomUser), which raises
        `ValueError: Cannot assign "<CustomUser>": "StudentRegistration.reviewer"
        must be a "HSAdministrator" instance.` on POST.
        """
        from cis.models.student import StudentRecommendation

        c = _login(self.user)
        data = {
            'student': str(self.student.id),
            'student_grade_level': self.student.grade_level,
            'student_gpa': '3.5',
            'student_prereq': 'Yes',
            'school_assessment': 'Proficient',
            'keystone_exam': 'Proficient',
            'geip': 'No',
            'enrolled_in_honors': 'No',
            f'registration_{self.registration.id}': 'approved',
            'submit_recommendation': 'Submit Recommendation',
        }
        resp = c.post(self._url(), data)
        self.assertEqual(resp.status_code, 302)

        self.assertTrue(
            StudentRecommendation.objects.filter(
                student=self.student, term=self.term).exists())

        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'approved')
        self.assertIsNotNone(self.registration.reviewer_id)
        self.assertEqual(self.registration.reviewer_id, self.admin.id)
