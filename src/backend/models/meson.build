pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
modelsdir = join_paths(pkgdatadir, 'bottles/backend/models')

bottles_sources = [
  'result.py',
]

install_data(bottles_sources, install_dir: modelsdir)
