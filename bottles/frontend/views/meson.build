pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
viewsdir = join_paths(pkgdatadir, 'bottles/frontend/views')

bottles_sources = [
  '__init__.py',
  'new_bottle_dialog.py',
  'list.py',
  'library.py',
  'bottle_details_view.py',
  'preferences.py',
  'importer.py',
  'loading.py',

  'bottle_details_page.py',
  'bottle_installers.py',
  'bottle_dependencies.py',
  'details_preferences_page.py',
  'bottle_versioning.py',
  'details_task_manager_view.py'
]

install_data(bottles_sources, install_dir: viewsdir)
