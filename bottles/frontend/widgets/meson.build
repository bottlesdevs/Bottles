pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
widgetsdir = join_paths(pkgdatadir, 'bottles/frontend/widgets')

bottles_sources = [
  '__init__.py',
  'dependency.py',
  'executable.py',
  'importer.py',
  'installer.py',
  'playtimechart_weekly.py',
  'playtimechart_hourly.py',
  'playtimechart_monthly.py',
  'program.py',
  'state.py',
  'component.py',
  'library.py',
]

install_data(bottles_sources, install_dir: widgetsdir)
