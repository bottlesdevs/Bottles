pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'bottles')

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('BASE_ID', BASE_ID)
conf.set('APP_ID', APP_ID)
conf.set('APP_NAME', APP_NAME)
conf.set('APP_VERSION', APP_VERSION)
conf.set('PROFILE', PROFILE)
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

subdir('backend')
subdir('frontend')

bottles_sources = [
  '__init__.py',
]

install_data(bottles_sources, install_dir: moduledir)
