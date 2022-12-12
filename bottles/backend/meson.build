pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
backenddir = join_paths(pkgdatadir, 'bottles/backend')

subdir('wine')
subdir('models')
subdir('utils')
subdir('dlls')
subdir('repos')
subdir('managers')

bottles_sources = [
  '__init__.py',
  'globals.py',
  'runner.py',
  'diff.py',
  'health.py',
  'downloader.py',
  'logger.py',
  'cabextract.py'
]

install_data(bottles_sources, install_dir: backenddir)
