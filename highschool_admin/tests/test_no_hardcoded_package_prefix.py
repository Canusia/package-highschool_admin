"""No module in this package may hardcode the nested `highschool_admin.highschool_admin` path.

The package runs in two deployment shapes: the in-tree editable submodule,
where it imports as `highschool_admin.highschool_admin`, and a pip-only
tenant, where it is flat. A module that spells either prefix out fails to
import in the other layout. In a test that costs the regression signal
(11 tests errored on every pip-installed tenant, ewu#61); in runtime code it
breaks the feature itself, so the whole package is scanned, not just tests/ (#4).

Use a relative import, or `PKG` from this package's `tests/__init__` where a
string is required.
"""
import os

from django.test import SimpleTestCase

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NESTED_PREFIX = 'highschool_admin' + '.highschool_admin'

# Paths relative to the package. These name both layouts on purpose.
EXEMPT = {
    'apps.py',                     # the dev / prod AppConfig pair
    os.path.join('tests', '__init__.py'),  # the PKG resolver
    os.path.join('tests', os.path.basename(__file__)),  # this guard
}
# Not Python source we own: caches, static assets, templates, generated migrations.
SKIP_DIRS = {'__pycache__', 'staticfiles', 'static', 'templates', 'migrations'}


def package_modules():
    for root, dirs, files in os.walk(PACKAGE_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
        for name in sorted(files):
            if name.endswith('.py'):
                path = os.path.join(root, name)
                yield os.path.relpath(path, PACKAGE_DIR), path


class NoHardcodedPackagePrefixTests(SimpleTestCase):

    def test_no_module_spells_out_the_nested_prefix(self):
        offenders = []
        for rel, path in package_modules():
            if rel in EXEMPT:
                continue
            with open(path, encoding='utf-8') as fh:
                for lineno, line in enumerate(fh, 1):
                    if NESTED_PREFIX in line:
                        offenders.append(f'{rel}:{lineno}: {line.strip()}')
        self.assertEqual(offenders, [], '\n'.join(offenders))

    def test_walk_covers_runtime_code(self):
        # Guard against a walk that silently scans nothing outside tests/.
        scanned = {rel for rel, _ in package_modules()}
        self.assertIn('page_messages.py', scanned)
        self.assertTrue(any(rel.startswith('views' + os.sep) for rel in scanned))
        self.assertNotIn(os.path.join('migrations', '__init__.py'), scanned)
