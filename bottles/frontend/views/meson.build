pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
viewsdir = join_paths(pkgdatadir, 'bottles/frontend/views')

bottles_sources = [
  '__init__.py',
  'new_bottle_dialog.py',
  'list.py',
  'library.py',
  'bottle_details_view.py',
  'preferences.py',
  'importer_view.py',
  'loading.py',

  'bottle_details_page.py',
  'details_installers_view.py',
  'details_dependencies_view.py',
  'details_preferences_page.py',
  'details_versioning_page.py',
  'details_task_manager_view.py'
]

install_data(bottles_sources, install_dir: viewsdir)
