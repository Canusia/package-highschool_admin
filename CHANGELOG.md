# Changelog

All notable changes to `package-highschool_admin` (the MyCE High School Admin portal).
Releases are git-tag-driven; pin a tag in the host's `webapp/requirements.txt`.

## v0.0.3 — 2026-08-02

### Fixed
- **`manage_student_recommendation` is now enforced.** The permission previously had no effect
  anywhere in the portal: the only check was commented out, and it lived in `views/home.py`'s
  `student()` — a dead copy, since `views/__init__.py` exports `student` from `views/students.py`.
  Any hsadmin could post a recommendation and approve/deny registrations for any student at any of
  their high schools.
  - `views/students.py` (the live view) computes `can_recommend` from the **student's** high school
    and refuses the whole POST before any write. A per-registration gate would still let
    `recommendation_form.save()` write the `StudentRecommendation` record itself.
  - The permission follows the student's school, not the section's host school. Those differ when a
    student takes a section hosted elsewhere.
  - `student.html` gates the approve/deny select, the crispy form and `#btn_submit_recommendation`
    on `can_recommend`, showing a warning alert otherwise.
  - `views/home.py`'s dead `student()` gets the same gate rather than being left as a
    live-looking hole.
- **Pending-recommendation lists are scoped to permitted schools.** New
  `get_user_recommendation_highschools()` in `views/utils.py`; the pending datatable
  (`PendingRecommendationViewSet`), the JSON endpoint and the dashboard page-message use it, so
  admins are no longer shown work they hold no permission to act on.

### New host requirements
A host running this version **must** provide, in `cis.models.highschool_administrator`:
- `HSAdministrator.get_recommendation_highschools()` — queryset counterpart to
  `can_manage_student_recommendation()`, keyed off the same active position plus the
  `manage_student_recommendation` meta flag.

and in `cis.models.section`:
- `StudentRegistration.get_pending_recommendations()` scoping its `highschool_ids` branch by
  `student__highschool__id__in` rather than `class_section__highschool__id__in`.

### Upgrade note
This is a behaviour change, not just a hardening. Admins whose `HSAdministratorPosition.meta` does
not carry `manage_student_recommendation: Yes` lose the recommendation UI. **Audit the data before
deploying** — on a tenant where the flag was never set, recommendations stop portal-wide.

## v0.0.2 — 2026-07-12

### Added
- **Student Class(es) tab — CE column parity.** The student-detail `#classes` tab now renders
  through the shared `myce_tenant_configs` registrations-table pattern (columns: Term, Applied On,
  Status, Course, Grade), matching the CE student page. Rows load from a new HS-scoped DataTables
  endpoint `GET /highschool_admin/api/student-registrations/` that reuses
  `cis.serializers.registration.StudentRegistrationSerializer`, scoped to the admin's high schools
  and UUID-guarding the `student` param. The pre-existing `/highschool_admin/api/registration/`
  (students-list page) is unchanged.
- **Single "Recommendation" tab.** The per-registration-term recommendation tabs are consolidated
  into one tab that lists all rec-eligible courses across terms; on submit, one
  `StudentRecommendation` is upserted per distinct term.

### Changed
- The recommendation **form, save logic, and read-back render** were relocated into the host's
  `myce_tenant_configs` app so each tenant can customize them. The HS view now resolves the form via
  `cis.services.tenant_services.get_tenant_service('recommendation_form')` and calls its `save()`.

### New host requirements
A host running this version **must** provide, in its `myce_tenant_configs` app:
- `services/registrations_table.py` with an **`hs_student_detail`** profile variant (see README →
  Requirements).
- `services/recommendation_form.py` exposing `StudentRecommendationForm` (with `save()`) and
  `as_html()`, with `cis.forms.student` shimming `StudentRecommendationForm` and
  `cis.models.student.StudentRecommendation.asHTML` delegating to the tenant render.

### Fixed
- Recommendation `save()` sets `StudentRegistration.reviewer` to the acting `HSAdministrator`
  (not the `CustomUser`), fixing a submission crash (`ValueError` on the FK assignment).

## v0.0.1 — 2026-07-11

### Added
- Initial extraction of the MyCE **High School Admin** portal into a pip-installable submodule,
  using the editable-submodule / `find_spec` pattern (app label `highschool_admin` unchanged; no
  models or migrations). Includes the `student_tabs` visibility setting and the dashboard
  `page_messages` providers. See README → "Porting page_messages".
