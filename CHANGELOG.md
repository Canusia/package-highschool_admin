# Changelog

All notable changes to `package-highschool_admin` (the MyCE High School Admin portal).
Releases are git-tag-driven; pin a tag in the host's `webapp/requirements.txt`.

## v0.0.9 — 2026-08-18

### Fixed
- **Version metadata now tracks the tag.** `setup.cfg` / `pyproject.toml` sat at `0.0.7` while
  tags moved past it, and pip keys upgrades off that string — an existing install read as
  already satisfied, so `pip install -r requirements.txt` kept the old code even after a
  tenant bumped its pin, with no error and no warning. v0.0.8 shipped with this defect;
  install it (or anything earlier) with `--force-reinstall`.

## v0.0.8 — 2026-08-18

### Fixed
- **The packaged tests run on pip-installed tenants again.** Test modules addressed the app
  through the nested `highschool_admin.highschool_admin.*` path, which only resolves in a
  repo that checks this out as an in-tree editable submodule, so 11 tests errored on every
  tenant installing from a pin — leaving the portal with no regression signal downstream.
  Imports are relative and patch targets build from `PKG`, resolved once via `find_spec`.
  A guard test fails if the nested prefix reappears. (ewu#61)

## v0.0.6 — 2026-08-06

### Fixed
- **Courses that need no recommendation now say so.** The Recommendation column rendered an empty
  cell whenever `needs_recommendation` was false, while the course still showed its name, instructor
  and status — so counselors read the blank as a broken control ("only one dropdown for two
  classes") rather than a course that is not rec-eligible. Applied registrations that need no
  recommendation now show a muted "Recommendation not required". Presentation only;
  `needs_recommendation` itself is unchanged. (ewu#51)

## v0.0.5 — 2026-08-06

### Fixed
- **Reopening a submitted recommendation no longer loses the tenant's fields.** `views/students.py`
  rebuilt `initial` from a fixed list of nine field names, five of them Pennsylvania-specific
  (Keystone Exam, PSSA, GEIP), which belong to a tenant's
  `myce_tenant_configs/services/recommendation_form.py` rather than to this package. A tenant whose
  rec form declared different fields saw them render blank on reopen, and submitting again silently
  overwrote the stored value — the blank control still validates, so nothing errored. Prefill now
  follows `StudentRecommendationForm.base_fields`, resolved through
  `get_tenant_service('recommendation_form')`, so this view needs no knowledge of any tenant's
  vocabulary. `student`, `student_state_id` and `upload_label` stay view-owned and still win over
  the stored blob. (ewu#46)
- **The Pre-Upload Blurb renders on a counselor's first visit.** `initial['upload_label']` was set
  only inside the `if existing:` branch, so the configured message was blank until a recommendation
  already existed. (ewu#46)

### Added
- **"Duplicate Section" in the per-course recommendation dropdown.** A counselor closing out a
  registration a student entered twice had only Approved and Not Approved; recording a duplicate as
  a denial misreports the school's approval rate. Matches the flow HVCC has offered for some time.
  (ewu#47)
- **The disabled pay-type column documents its POST-name contract in place.** Every per-registration
  control is named `registration_<field>_<id>`, matching the `registration_<id>` status field the
  same table posts. A tenant's `clean()` was reading two different names, neither of which anything
  posted, so both guards were dead code. (ewu#48)

### New host requirements
- **package-cis v0.0.9 or later.** "Duplicate Section" writes `duplicate` straight through to
  `StudentRegistration.status`; the value must be in `STATUS_OPTIONS` or the save fails.

## v0.0.4 — 2026-08-03

### Added
- **"Enter Grades" link on the class section page**, pointing at the grade-entry view owned by the
  optional `grades` package. Uses the `{% url … as %}` form so the link degrades to nothing when
  `grades` is not installed; no hard dependency is introduced. Requires package-grades v0.0.3 or
  later to have a route to point at.

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
