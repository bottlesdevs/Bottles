pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
frontenddir = join_paths(pkgdatadir, 'bottles/frontend')

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
  install_dir: get_option('bindir'),
  install_mode: ['rwxr-xr-x']
)

params_file = configure_file(
    input:  'params.py',
    output:  'params.py',
    configuration: conf
)

fs = import('fs')

if not fs.is_file('/' + '.flatpak-info')
  error('file does not exist')
endif

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
