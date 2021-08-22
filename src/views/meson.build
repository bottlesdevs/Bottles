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
  'dialog.py',
  'onboard.py'
]

install_data(bottles_sources, install_dir: viewsdir)
