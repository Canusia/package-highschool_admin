# Outer wrapper package for the highschool_admin submodule.
# Do NOT import Django app code or models here — this module is imported before
# the app registry is ready. The real Django app is the inner package
# `highschool_admin.highschool_admin`. Host wiring selects it via
# find_spec('highschool_admin.highschool_admin').
