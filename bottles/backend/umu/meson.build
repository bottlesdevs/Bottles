pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
umudir = join_paths(pkgdatadir, 'bottles/backend/umu')

bottles_sources = [
  '__init__.py',
  'database.py',
  'dependencies.py',
  'executor.py',
  'models.py',
  'processes.py',
  'provider.py',
  'proton.py',
  'repository.py',
]

install_data(bottles_sources, install_dir: umudir)
