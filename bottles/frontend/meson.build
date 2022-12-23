pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
frontenddir = join_paths(pkgdatadir, 'bottles/frontend')
conf = configuration_data()
conf.set('APP_NAME', APP_NAME)
conf.set('APP_ICON', APP_ICON)
conf.set('APP_VERSION', APP_VERSION)

subdir('ui')
subdir('utils')
subdir('views')
subdir('widgets')
subdir('windows')
subdir('cli')

configure_file(
  input: 'bottles.in',
  output: 'bottles',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

param_file = configure_file(
        input:  'params.py.in',
       output:  'params.py',
    configuration: conf)

bottles_sources = [
  '__init__.py',
  'main.py',
  'const.py',
  'operation.py',
  param_file,
]

if get_option('devel')
  bottles_sources += [
    'devel/const.py',
  ]
endif

install_data(bottles_sources, install_dir: frontenddir)
