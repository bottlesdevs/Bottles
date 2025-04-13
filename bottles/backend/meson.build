pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
backenddir = join_paths(pkgdatadir, 'bottles/backend')

params_file = configure_file(
    input:  'params.py',
    output:  'params.py',
    configuration: conf
)

subdir('wine')
subdir('models')
subdir('utils')
subdir('dlls')
subdir('repos')
subdir('managers')

bottles_sources = [
  '__init__.py',
  'bottle.py',
  'globals.py',
  'runner.py',
  'diff.py',
  'health.py',
  'downloader.py',
  'cabextract.py',
  'state.py',
  'typing.py',
  params_file
]

install_data(bottles_sources, install_dir: backenddir)
