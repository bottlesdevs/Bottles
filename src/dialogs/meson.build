pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dialogsdir = join_paths(pkgdatadir, 'bottles/dialogs')

bottles_sources = [
  '__init__.py',
  'crash.py',
  'dlloverrides.py',
  'duplicate.py',
  'envvars.py',
  'generic.py',
  'launchoptions.py',
  'onboard.py',
  'runargs.py',
  'rename.py',
  'drives.py',
  'gamescope.py',
  'generic_cli.py',
  'journal.py',
  'filechooser.py',
  'localresources.py',
  'bottlepicker.py',
  'protonalert.py',
  'sandbox.py'
]

install_data(bottles_sources, install_dir: dialogsdir)
