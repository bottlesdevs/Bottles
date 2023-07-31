pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dialogsdir = join_paths(pkgdatadir, 'bottles/frontend/windows')

bottles_sources = [
  '__init__.py',
  'crash.py',
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
  'display.py',
  'generic_cli.py',
  'journal.py',
  'bottlepicker.py',
  'protonalert.py',
  'sandbox.py',
  'installer.py',
  'depscheck.py',
  'exclusionpatterns.py',
  'upgradeversioning.py',
  'vmtouch.py',
  'main_window.py',
  'runfiledialog.py',
]

install_data(bottles_sources, install_dir: dialogsdir)
