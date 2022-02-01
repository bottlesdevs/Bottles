pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
backenddir = join_paths(pkgdatadir, 'bottles/backend')

subdir('wine')
subdir('models')
subdir('utils')
subdir('dlls')

bottles_sources = [
  '__init__.py',
  'backup.py',
  'component.py',
  'dependency.py',
  'globals.py',
  'installer.py',
  'manager.py',
  'runner.py',
  'versioning.py',
  'data.py',
  'notifications.py',
  'runtime.py',
  'importer.py',
  'layers.py',
  'diff.py',
  'health.py',
  'conf.py',
  'downloader.py'
]

install_data(bottles_sources, install_dir: backenddir)
