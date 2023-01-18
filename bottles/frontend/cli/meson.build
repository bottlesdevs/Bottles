pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
clidir = join_paths(pkgdatadir, 'bottles/frontend/cli')

bottles_sources = [
  '__init__.py',
  'operation_cli.py',
]

install_data(bottles_sources, install_dir: clidir)

configure_file(
  input: 'cli.py',
  output: 'bottles-cli',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)