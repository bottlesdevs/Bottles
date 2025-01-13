pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
widgetsdir = join_paths(pkgdatadir, 'bottles/frontend/widgets')

bottles_sources = [
  '__init__.py',
  'dependency_entry_row.py',
  'executable.py',
  'importer_row.py',
  'installer_row.py',
  'program.py',
  'state.py',
  'component_entry_row.py',
  'library.py',
]

install_data(bottles_sources, install_dir: widgetsdir)
