pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
utilsdir = join_paths(pkgdatadir, 'bottles/frontend/utils')

bottles_sources = [
  '__init__.py',
  'autostart.py',
  'gtk.py',
  'localization.py',
  'common.py',
  'filters.py',
  'flatpak.py',
  'playtime.py',
  'sh.py',
  'sandbox_guard.py',
  'umu.py',
]

install_data(bottles_sources, install_dir: utilsdir)
