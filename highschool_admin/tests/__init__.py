"""Test package for highschool_admin.

`PKG` is the app's importable dotted path, resolved at runtime. The package
ships in two layouts — nested as an editable git submodule
(`highschool_admin.highschool_admin`) and flat when pip-installed
(`highschool_admin`) — and `mock.patch` targets are strings, so they cannot
rely on Python's relative-import machinery the way `from ..module import x`
can. Hardcoding either layout breaks the suite on tenants using the other:
see ewu#61.

Import statements in these tests should use relative imports; only patch
targets and other dotted-path *strings* need `PKG`.
"""
import importlib.util

PKG = (
    'highschool_admin.highschool_admin'
    if importlib.util.find_spec('highschool_admin.highschool_admin')
    else 'highschool_admin'
)
