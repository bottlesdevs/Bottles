pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
frontenddir = join_paths(pkgdatadir, 'bottles/frontend')
conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('APP_NAME', APP_NAME)
conf.set('APP_ID', APP_ID)
conf.set('APP_VERSION', APP_VERSION)
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

subdir('ui')
subdir('utils')
subdir('views')
subdir('widgets')
subdir('windows')
subdir('cli')

configure_file(
  input: 'bottles.py',
  output: 'bottles',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

params_file = configure_file(
    input:  'params.py',
    output:  'params.py',
    configuration: conf
)

bottles_sources = [
  '__init__.py',
  'main.py',
  'const.py',
  'operation.py',
  params_file,
]

if get_option('devel')
  bottles_sources += [
    'devel/const.py',
  ]
endif

install_data(bottles_sources, install_dir: frontenddir)
