pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
viewsdir = join_paths(pkgdatadir, 'bottles/frontend/views')

bottles_sources = [
  '__init__.py',
  'new_bottle_dialog.py',
  'list.py',
  'library.py',
  'details.py',
  'preferences.py',
  'importer.py',
  'loading.py',

  'bottle_details.py',
  'bottle_installers.py',
  'bottle_dependencies.py',
  'bottle_preferences.py',
  'bottle_versioning.py',
  'bottle_taskmanager.py'
]

install_data(bottles_sources, install_dir: viewsdir)
