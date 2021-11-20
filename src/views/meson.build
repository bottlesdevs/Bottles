pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
viewsdir = join_paths(pkgdatadir, 'bottles/views')

bottles_sources = [
  '__init__.py',
  'new.py',
  'list.py',
  'details.py',
  'preferences.py',
  'taskmanager.py',
  'importer.py',

  'bottle_details.py',
  'bottle_installers.py',
  'bottle_dependencies.py',
  'bottle_preferences.py',
  'bottle_programs.py',
  'bottle_versioning.py'
]

install_data(bottles_sources, install_dir: viewsdir)
