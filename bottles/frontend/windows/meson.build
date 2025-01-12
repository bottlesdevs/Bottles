pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dialogsdir = join_paths(pkgdatadir, 'bottles/frontend/windows')

bottles_sources = [
  '__init__.py',
  'crash_report_dialog.py',
  'dll_overrides_dialog.py',
  'duplicate_dialog.py',
  'envvars.py',
  'generic.py',
  'launchoptions.py',
  'onboard.py',
  'rename.py',
  'drives_dialog.py',
  'gamescope_dialog.py',
  'vkbasalt.py',
  'fsr_dialog.py',
  'mangohud.py',
  'display_dialog.py',
  'generic_cli.py',
  'journal.py',
  'bottle_picker_dialog.py',
  'protonalert.py',
  'sandbox.py',
  'installer.py',
  'dependencies_check_dialog.py',
  'exclusion_patterns_dialog.py',
  'upgradeversioning.py',
  'vmtouch.py',
  'window.py',
]

install_data(bottles_sources, install_dir: dialogsdir)
