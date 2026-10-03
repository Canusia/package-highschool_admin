# #4 — Widen the hardcoded-nested-path guard to the whole package

> Implemented inline. Written against `v0.0.19` / `972eb7c`.

**Goal:** `tests/test_no_hardcoded_package_prefix.py` scans every `.py` file in the inner
package, not just `tests/`, because a nested path in runtime code breaks pip-installed tenants.

**Architecture:** Walk `highschool_admin/` with `os.walk`, skipping `__pycache__`, `staticfiles`,
`templates` and `migrations` (generated; Django writes app labels there, not module paths).
Exempt, by path relative to the package: `apps.py` (the dev/prod config resolver names both
layouts on purpose), `tests/__init__.py` (the `PKG` resolver) and the guard itself.

## Tasks
- [x] Rewrite the guard to walk the package, with path-relative exemptions.
- [x] Add a self-check that the walk really reaches non-test modules (`views/`,
  `page_messages.py`), so a broken walk can't pass vacuously.
- [x] Prove it catches runtime code: a temporary nested import in `page_messages.py` fails
  the guard (verified manually, then reverted).
- [x] Full suite, commit.

## Follow-up (not done here)
`class_visit/class_visit/tests/test_no_hardcoded_package_prefix.py` has the same narrow
`tests/`-only scope. Port this version there so the two guards stay identical.
