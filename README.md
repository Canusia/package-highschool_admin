# myce-highschool-admin

The **High School Admin portal** for [MyCE](https://github.com/Canusia) (Canusia's Concurrent /
Dual Enrollment platform). High-school administrators manage their schools' students, notes,
transcripts, certificates, bulk enrollment, personnel, and per-term recommendation / review /
pay-type workflows. This package is the `/highschool_admin/` portal app extracted from the MyCE
host so it can be shared across tenants.

The distribution name is `myce-highschool-admin`; the Django **app label is always
`highschool_admin`** (URL namespace `highschool_admin:*`, template dir `highschool_admin/`, and the
`Setting` storage key all depend on it — do not change it).

---

## Requirements

This app is **tightly coupled to a MyCE host deployment** — it is not a standalone reusable Django
app. It imports the host's `cis` app extensively (~150 import sites across models, forms,
serializers, services, settings, menu, utils, storage, and the page-message registry). Do not
install it outside a MyCE tenant.

**Python / Django**

- Python `>= 3.10`
- `Django >= 4.2` (declared `install_requires`; the reference host runs Django 5.2)

**MyCE host apps / frameworks it imports directly**

- `cis` — `CustomUser`, role helpers (`user_has_highschool_admin_role`), `HighSchool`,
  `HSAdministrator`, `Student`, `StudentRegistration` (incl. `get_pending_recommendations` /
  pending-review / pending-pay-type queries), `Term`, `Note`, `cis.models.settings.Setting`,
  importer services, `cis.menu`, `cis.storage_backend.PrivateMediaStorage`, and the
  **page-message registry** `cis.page_messages` (`page_message`, `PageMessage`,
  `get_page_messages`).
- `two_step` — `verification_required` gate on every portal view (each page requires a verified
  two-step session).
- `django_login_history` — login-history model (used in test fixtures).
- The `setting` framework — surfaces the `student_tabs` configurator under CE Settings.

**Optional integrations** (guarded by `importlib.util.find_spec`, safe if absent):

- `future_sections` — the `projection_window_closed` dashboard message + the Course Projections tab.
- `drop_wd` — the `pending_drop_requests` dashboard message.
- `announcement` — dashboard announcements.

---

## Dual-package layout (editable-submodule pattern)

This repo is both an **installable package root** and an **editable in-tree submodule**, mirroring
`student_onboarding`, `instructor_app`, and `support_ticket`. There are two nested package levels:

```
package-highschool_admin/          <- repo root = outer/installable wrapper package
├── setup.cfg, pyproject.toml, MANIFEST.in
├── README.md, CLAUDE.md, LICENSE
├── __init__.py                    <- outer marker only (NO app code)
└── highschool_admin/              <- inner Django app (the real code)
    ├── apps.py                    <- HighschoolAdminConfig + DevHighschoolAdminConfig
    ├── urls.py (app_name='highschool_admin'), page_messages.py
    ├── views/ (+ views/api/), settings/, migrations/ (empty)
    ├── templates/highschool_admin/  and  staticfiles/highschool_admin/
    └── tests/
```

Two `AppConfig` classes live in `highschool_admin/apps.py`, both with `label = 'highschool_admin'`
(so app_label, template dirs, and URL namespace are identical in either mode):

| Config | `name` | When it loads |
|--------|--------|---------------|
| `HighschoolAdminConfig` | `highschool_admin` | **prod** — pip-installed; inner package is top-level `highschool_admin` |
| `DevHighschoolAdminConfig` | `highschool_admin.highschool_admin` | **dev** — in-tree submodule; selected via `find_spec('highschool_admin.highschool_admin')` |

Self-referential imports inside the inner package are **relative** (`from ..settings.student_tabs
import student_tabs`), so both layouts resolve without outer proxy shims. This app has **no models
and no migrations** (its only persisted state, the `student_tabs` visibility flags, lives in the
host's `cis.models.settings.Setting` table under key `highschool_admin.settings.student_tabs`).

---

## Installation

### a. Pip-installed (production / other tenants)

```bash
pip install git+https://github.com/Canusia/package-highschool_admin.git@v0.0.1
```

Pin it in the host's `webapp/requirements.txt`:

```
git+https://github.com/Canusia/package-highschool_admin.git@v0.0.1
```

In this mode `find_spec('highschool_admin.highschool_admin')` is **false**, so the host wiring falls
through to the top-level `highschool_admin.*` branches and loads `HighschoolAdminConfig`.

### b. Editable submodule (development / in-tree, e.g. EWU)

```bash
git submodule add https://github.com/Canusia/package-highschool_admin.git webapp/highschool_admin
```

Now the inner package `highschool_admin.highschool_admin` is importable, so
`find_spec('highschool_admin.highschool_admin')` is **true** and the host selects the inner-path
branches and `DevHighschoolAdminConfig`.

---

## Wiring into a MyCE host

The host selects dev vs. prod with `importlib.util.find_spec(...)`. Add these blocks **exactly**.

### 1. `INSTALLED_APPS` (`myce/settings.py`)

```python
'highschool_admin.highschool_admin.apps.DevHighschoolAdminConfig'
if importlib.util.find_spec('highschool_admin.highschool_admin')
else 'highschool_admin.apps.HighschoolAdminConfig',
```

### 2. `STATICFILES_DIRS` (`myce/settings.py`)

```python
os.path.join(get_package_path("highschool_admin.highschool_admin"), 'staticfiles')
if importlib.util.find_spec('highschool_admin.highschool_admin')
else os.path.join(get_package_path("highschool_admin"), 'staticfiles')
if get_package_path("highschool_admin") else None,
```

(`get_package_path` is the host helper: `os.path.dirname(find_spec(name).origin)`.)

### 3. URL include (`myce/urls.py`)

```python
_ha = 'highschool_admin.highschool_admin' if importlib.util.find_spec('highschool_admin.highschool_admin') else 'highschool_admin'
...
path('highschool_admin/', include(f'{_ha}.urls')),
```

Leave any other `/highschool_admin/…`-prefixed includes (reports, future_sections, drop_wd,
instructor_apps, support_requests) as-is — those are *other* packages mounting under the same URL
prefix, not this app.

---

## Post-install commands

Run inside the host container (for EWU: `docker exec -w /app/webapp django_web_ewu python manage.py ...`):

```bash
python manage.py check               # app loads under the selected config
python manage.py register_settings   # surfaces "Student Page Tabs" under CE Settings (category 1)
python manage.py collectstatic       # ships staticfiles/highschool_admin/js/*
```

There is no `migrate` step — the app owns no models.

---

## Configuration — the `student_tabs` setting

CE admins toggle three tabs at **CE `/ce/settings/` → "Student Page Tabs"** (registered via the
`CONFIGURATORS` / category `1` entry in `apps.py`). Stored as one `cis.models.settings.Setting` row
keyed `highschool_admin.settings.student_tabs`:

```json
{"show_recommendation": true, "show_review": true, "show_pay_type": true}
```

Always read through the `student_tabs` classmethods (`tabs()`, `show_recommendation()`,
`show_review()`, `show_pay_type()`) — never the `Setting` model directly. **Absent keys default to
`True`** (backward compatible: tabs stay visible until an admin unchecks them). These flags gate the
Recommendation / Review / Pay Type tabs on the students-list and student-detail pages **and** the
dashboard "pending recommendation" page-message.

---

## Porting `page_messages` to a MyCE tenant

`highschool_admin/page_messages.py` ships four dashboard/future-sections message **providers**:

| Provider | Scope `(app, page)` | Shows when |
|----------|--------------------|------------|
| `pending_recommendations` | `('highschool_admin', 'dashboard')` | `student_tabs.show_recommendation()` **and** the admin's schools have registrations awaiting recommendation |
| `pending_pay_type` | `('highschool_admin', 'dashboard')` | registrations awaiting a pay-type decision |
| `pending_drop_requests` | `('highschool_admin', 'dashboard')` | (optional `drop_wd`) open drop/WD requests exist |
| `projection_window_closed` | `('highschool_admin', 'future_sections')` | (optional `future_sections`) the projection window has closed |

### How registration works (read this first)

Providers register by **import side-effect**: applying the `@page_message(app, page)` decorator
appends the function to a process-global registry `cis.page_messages._REGISTRY[(app, page)]`. The
registry, the `PageMessage` dataclass, and `get_page_messages(app, page, request)` all live in the
host's **`cis.page_messages`** module — this package imports them, it does not define them.

Discovery is driven by the host: `cis.apps.CisConfig.ready()` ends with

```python
from django.utils.module_loading import autodiscover_modules
autodiscover_modules('page_messages')
```

which imports `<each installed app>.page_messages`. For this package that is
`highschool_admin.highschool_admin.page_messages` (dev) or `highschool_admin.page_messages` (prod) —
both resolve automatically because the app is in `INSTALLED_APPS`. **This app has no `ready()` of its
own; it free-rides on `cis`'s autodiscover.**

### Checklist to activate the providers on a tenant

1. **The registry exists.** Confirm the tenant has `cis/page_messages.py` exporting
   `page_message`, `PageMessage`, `get_page_messages`, and a module-global `_REGISTRY`. If a tenant
   predates the page-message framework, port `cis/page_messages.py` first (it is a
   dependency-free ~70-line module).
2. **Autodiscover runs.** Confirm `cis.apps.CisConfig.ready()` calls
   `autodiscover_modules('page_messages')`. If not, add those two lines to the end of `ready()`.
3. **The app is installed.** `highschool_admin[.highschool_admin]` must be in `INSTALLED_APPS`
   (see *Wiring* above), otherwise its `page_messages` module is never imported and none of its
   providers register.
4. **The dashboard renders messages.** The HS-admin dashboard view/template must call
   `get_page_messages('highschool_admin', 'dashboard', request)` and render each `PageMessage`
   (`text`, `level`, `icon`, `tile_id`, `url`). If the tenant's dashboard doesn't yet consume the
   registry, port that call + the tile-rendering partial.
5. **Provider data dependencies exist.** Providers call
   `StudentRegistration.get_pending_recommendations(...)` and sibling pending-* queries, plus the
   package-internal helper `get_user_highschools(request)` (ships in `views/utils.py`). Ensure the
   tenant's `cis.models.section.StudentRegistration` exposes those classmethods.
6. **Optional integrations degrade gracefully.** `pending_drop_requests` and
   `projection_window_closed` resolve `drop_wd` / `future_sections` behind
   `importlib.util.find_spec(...)` (trying the editable `<pkg>.<pkg>` path, then the flat `<pkg>`
   path). If those packages aren't installed on the tenant, the providers no-op — no action needed.

### Verify after porting

```bash
python manage.py shell -c "from cis.page_messages import _REGISTRY; \
print(sorted(k for k in _REGISTRY if k[0]=='highschool_admin'))"
# -> [('highschool_admin', 'dashboard'), ('highschool_admin', 'future_sections')]
```

Then load `/highschool_admin/dashboard/` as an HS admin whose schools have a pending recommendation
and confirm the danger tile appears (and disappears when "Show Recommendation tab" is unchecked in
the `student_tabs` setting).

---

## Versioning & release

Releases are **tag-driven**; the `setup.cfg`/`pyproject.toml` version stays nominal (`0.0.1`).

1. Make changes in the **inner** package. Run the `submod-package-manifest` skill if you added
   `templates/`, `staticfiles/`, `settings/`, or new top-level modules, so `MANIFEST.in` ships them.
2. Tag and push: `git tag v0.0.2 && git push --tags`.
3. In each consuming tenant, bump the `webapp/requirements.txt` pin (`…@v0.0.2`) and — for the
   submodule tenant — advance the submodule pointer, in one change.

---

## License

MIT © Canusia. See [`LICENSE`](LICENSE).
