pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
frontenddir = join_paths(pkgdatadir, 'bottles/frontend')

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

bottles_sources = [
  '__init__.py',
  'main.py',
  'params.py',
  'const.py',
  'operation.py',
]

if get_option('devel')
  bottles_sources += [
    'devel/const.py',
  ]
endif

install_data(bottles_sources, install_dir: frontenddir)
