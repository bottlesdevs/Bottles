pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'bottles')

python = import('python')

dependency('libhandy-1', version: '>= 1.5')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'bottles.in',
  output: 'bottles',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

configure_file(
  input: 'cli.in',
  output: 'bottles-cli',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

subdir('backend')
subdir('utils')
subdir('dialogs')
subdir('ui')
subdir('views')
subdir('widgets')

bottles_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'params.py',
  'operation.py',
  'operation_cli.py',
]

install_data(bottles_sources, install_dir: moduledir)
