project(
	'bottles',
	version: '2022.7.14-brescia-2',
	meson_version: '>= 0.50.0',
	default_options: [
		'warning_level=2',
	],
  	license: 'GPL-3.0-or-later'
)

i18n = import('i18n')
localedir = get_option('localedir')

subdir('po')
subdir('src')
subdir('data')

meson.add_install_script('build-aux/meson/postinstall.py')
