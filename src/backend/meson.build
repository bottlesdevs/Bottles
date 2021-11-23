pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
backenddir = join_paths(pkgdatadir, 'bottles/backend')

bottles_sources = [
  '__init__.py',
  'backup.py',
  'component.py',
  'dependency.py',
  'globals.py',
  'installer.py',
  'manager.py',
  'manager_utils.py',
  'runner.py',
  'versioning.py',
  'data.py',
  'notifications.py',
  'result.py'
]

install_data(bottles_sources, install_dir: backenddir)
