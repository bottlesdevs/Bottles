pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
pagesdir = join_paths(pkgdatadir, 'bottles/pages')

bottles_sources = [
  '__init__.py',
  'add.py',
  'create.py',
  'list.py',
  'details.py',
  'preferences.py',
  'dialog.py',
]

install_data(bottles_sources, install_dir: pagesdir)
