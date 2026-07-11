# CLAUDE.md — package-highschool_admin

MyCE **High School Admin** portal, extracted as a pip-installable submodule.

## Layout
- Outer wrapper = repo root (`setup.cfg`, `pyproject.toml`, `MANIFEST.in`, `__init__.py` marker only).
- Inner Django app = `highschool_admin/` (app **label `highschool_admin`**; namespace `highschool_admin:*`).
- Two configs in `highschool_admin/apps.py`: `HighschoolAdminConfig` (prod, `name='highschool_admin'`)
  and `DevHighschoolAdminConfig` (dev, `name='highschool_admin.highschool_admin'`). Only `name` (+ the
  `CONFIGURATORS` `app` key) differs.

## Rules
- **No models, no migrations.** The only persisted state is the `student_tabs` `Setting` row
  (key literal `highschool_admin.settings.student_tabs` — never `str(__name__)`).
- Self-imports inside the inner package are **relative** (`from ..settings.student_tabs import …`).
  External imports (`cis`, `two_step`, optional `future_sections`/`drop_wd`) stay absolute.
- `page_messages.py` providers register via `cis.apps.ready()`'s `autodiscover_modules('page_messages')`;
  the registry lives in `cis.page_messages`. See README → "Porting page_messages".
- Run tests from a host that checks this out as an in-tree submodule (dev/nested layout):
  `docker exec -w /app/webapp django_web_ewu python manage.py test highschool_admin`.
