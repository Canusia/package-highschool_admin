# #3 — Make the Classes section-scoping pluggable

> Implemented inline. Written against `feat/issues-3-4-6-7` @ `71d7a65`.

**Goal:** The Classes list (`ClassSectionViewSet.get_queryset`) and the class-section detail
guard (`views/classes.py::class_section`) both ask **one** function which sections an HS admin
may see. A tenant can change the rule without forking either file.

**Architecture:** `services/section_scope.py::visible_sections(request)` resolves the rule in
this order:
1. **Tenant override (general seam):** `get_tenant_override('highschool_admin', 'visible_sections')`,
   the codebase's standard opt-in pattern. The tenant ships
   `<TENANT_SERVICES_APP>/services/highschool_admin.py` with
   `def visible_sections(request, highschools): -> ClassSection queryset`.
2. **Built-in rule by setting:** `MY_CE['highschool_admin']['class_section_scope']`:
   - `'hosted'` (default): `highschool__in=my schools`, which is today's behaviour;
   - `'hosted_or_own_students'`: sections my schools host **or** that my schools' students are
     registered in (NNU consortium). Registrations of any status count, so a counselor can
     still open a class their student dropped.
3. Unknown setting value → `'hosted'`, with a logged warning.

The detail guard is `visible_sections(request).filter(pk=...).exists()`, so a section that is
listed always opens and one that isn't listed always 404s.

## Review Focus
1. `hosted_or_own_students` with a student registered twice in one section → listed once (subquery, not a join).
2. Tenant override present → it wins over the setting.
3. Detail page for a consortium section: 404 under `'hosted'`, 200 under `'hosted_or_own_students'`.
4. The term filter still applies on top of the scope.
5. A tenant module without the attribute → default (opt-in seam).

## Tasks
- [x] `services/section_scope.py` + wire the viewset and detail view.
- [x] Tests: `tests/test_class_section_scope.py`.
- [x] README section, full suite, commit.
