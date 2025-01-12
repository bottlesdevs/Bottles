pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dialogsdir = join_paths(pkgdatadir, 'bottles/frontend/windows')

bottles_sources = [
  '__init__.py',
  'crash_report_dialog.py',
  'dlloverrides.py',
  'duplicate.py',
  'envvars.py',
  'generic.py',
  'launchoptions.py',
  'onboard.py',
  'rename.py',
  'drives.py',
  'gamescope.py',
  'vkbasalt.py',
  'fsr.py',
  'mangohud.py',
  'display.py',
  'generic_cli.py',
  'journal.py',
  'bottle_picker_dialog.py',
  'protonalert.py',
  'sandbox.py',
  'installer.py',
  'dependencies_check_dialog.py',
  'exclusionpatterns.py',
  'upgradeversioning.py',
  'vmtouch.py',
  'window.py',
]

install_data(bottles_sources, install_dir: dialogsdir)
