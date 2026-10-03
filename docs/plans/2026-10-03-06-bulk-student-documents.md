# #6 — Term-scoped bulk student-document upload for HS admins

> Implemented inline. Written against `feat/issues-3-4-6-7` @ `5fc90d1`. Spec: rvcc
> `docs/superpowers/specs/2026-09-11-hs-admin-uploads-design.md`, Phase C.

**Goal:** One page where an HS admin picks a term and a document type, then attaches a file to
each of their students. This replaces navigating 80 (or 600) student pages.

**Architecture:** A new entry point only. It uses cis's `StudentSupportingDocumentForm` and
the `StudentSupportingDocument` model, the same path as the student page's Supporting Documents
tab. There is no new model and no `cis` change.
- `views/student_documents.py::student_documents` (GET): term (default: active term) and the
  document-type vocabulary (`StudentSupportingDocumentForm._document_type_labels(term)`, the
  same source as the per-student tab). It lists the admin's students registered that term, or
  all of their students with `?all=1`, and the documents each already has for that term.
- `upload_student_document` (POST, JSON): **one file per request**. The JS uploads the chosen
  rows one after another and shows each row's result inline, so a large batch never becomes one
  giant request and a bad file doesn't sink the rest. The student is looked up with
  `highschool__in=get_user_highschools(request)` and the posted student id is never trusted.
  The type must be in the vocabulary. `status` stays CE-only (the form excludes it). A note is
  added to the student, as on the single-student path.

## Decisions
| Question in the issue | Decision |
|---|---|
| Two features called "transcripts" | **Relabel, don't retire.** Since #6 was filed, `/transcripts/` has gained uploads (#15) for school-level files, a legitimate separate use. Both pages now say which is which and link to each other; the Students page gets an "Upload Student Documents" button. The sidebar label is tenant menu data (`cis.settings.menu`), so renaming it is a per-tenant CE choice. |
| "Transcript" in the vocabulary | Tenant data (`support_docs` / `DocumentType`). Nothing to ship here; confirm the type exists per tenant before announcing. |
| Combined multi-student PDF splitting | Out of scope (per the issue). |

## Review Focus
1. A posted student at another school → 404, nothing stored.
2. A type outside the vocabulary → 400.
3. A missing file → 400 (form validation).
4. A malformed student id → 404, not 500.
5. The page never lists another school's student, even one registered in a section the admin's school hosts.

## Tasks
- [x] View + URL + template + JS; cross-links on the Transcripts and Students pages.
- [x] `tests/test_student_documents_bulk.py`.
- [x] README, full suite, commit.
