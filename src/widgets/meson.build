pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
widgetsdir = join_paths(pkgdatadir, 'bottles/widgets')

bottles_sources = [
  '__init__.py',
  'dependency.py',
  'dxvk.py',
  'importer.py',
  'installer.py',
  'page.py',
  'program.py',
  'runner.py',
  'state.py',
  'vkd3d.py'
]

install_data(bottles_sources, install_dir: widgetsdir)
