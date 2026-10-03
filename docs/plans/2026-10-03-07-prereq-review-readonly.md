# #7 — Surface the college's prerequisite review, read-only, to HS admins

> Implemented inline. Written against `feat/issues-3-4-6-7` @ `3175e2a`. Spec: rvcc
> `docs/superpowers/specs/2026-09-11-hs-admin-uploads-design.md`, Phase D. The tenant side
> is `rvcc/webapp/myce_tenant_configs/services/prereq_tracking.py`.

**Goal:** Counselors see whether the college received a student's transcript, whether each
class's prerequisite is met, and which test score is still needed. They see it on the student
page and across the cohort in a table, and can never change it.

**Architecture:** `services/prereq_review.py` resolves the tenant's `prereq_tracking` service
through `get_tenant_service`. A tenant without the module gets `None` and the portal shows
nothing; an `ImportError` raised *inside* an existing module is a real breakage and propagates.
It reads only through the service's public accessors (`get_review`,
`get_registration_review`, `test_score_display`), never through `Student.meta` directly, and it
**whitelists three keys**. The CE-internal `note` and the audit stamps never leave it.

## Decisions
| Topic | Decision |
|---|---|
| Data shape drift | Since the issue was filed, RVCC moved `prereq_met` (and `note`) to **per registration**; `transcript_received` / `test_score_needed` stay per term. The helper reads per-class `prereq_met` and falls back to a term-level value (older layout). |
| "Student table" | The flags go on **Registrations by Term**: one row per student per class, which is the workbook's own grain and the only place a per-class `prereq_met` fits. Three columns, not orderable or searchable (the values live in JSON, not ORM columns). |
| Student page | A new read-only **College Review** tab: per term, the transcript and test-score values, then a class/prereq-met table. |
| Read-only | No write path in the package. The test service's `set_review`/`set_flag` raise if called, and a stray POST changes nothing. |

## Review Focus
1. `note` (CE-internal) must not appear in the API JSON or the page HTML.
2. A tenant without the service → no tab, no columns, `prereq_review: null`.
3. A breakage inside the service module is not swallowed.
4. N+1: the registration API select_related adds `class_section__term`; `student.meta` comes with `student`.
5. A test score stored with the legacy code `Either` → shown as "ACT or Accuplacer".

## Tasks
- [x] Service, serializer field, viewset select_related, table columns (template + JS), student tab.
- [x] `tests/test_prereq_review_readonly.py`.
- [x] README, full suite, commit.
