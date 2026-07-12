# Changelog

All notable changes to `package-highschool_admin` (the MyCE High School Admin portal).
Releases are git-tag-driven; pin a tag in the host's `webapp/requirements.txt`.

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
