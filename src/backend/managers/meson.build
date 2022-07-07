pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
managersdir = join_paths(pkgdatadir, 'bottles/backend/managers')

bottles_sources = [
  '__init__.py',
  'backup.py',
  'component.py',
  'dependency.py',
  'installer.py',
  'library.py',
  'manager.py',
  'versioning.py',
  'data.py',
  'notifications.py',
  'runtime.py',
  'importer.py',
  'conf.py',
  'journal.py',
  'repository.py',
  'template.py',
  'sandbox.py',
  'steam.py',
  'epicgamesstore.py',
  'queue.py',
]

install_data(bottles_sources, install_dir: managersdir)
