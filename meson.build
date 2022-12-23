project(
	'bottles',
	version: '2022.12.14.1',
	meson_version: '>= 0.59.0',
	default_options: [
		'warning_level=2',
	],
	license: 'GPL-3.0-only'
)


APP_NAME = 'Bottles'
APP_ID = 'com.usebottles.bottles'
APP_VERSION = meson.project_version()
devel = get_option('devel')

if devel == true
	APP_VERSION += '-' + run_command(
		'git', 'rev-parse', '--short', 'HEAD'
	).stdout().strip()
	APP_NAME += ' (Development)'
	APP_ID += '.' + 'Devel'
endif

APP_ICON = APP_ID + '.' + 'svg'



gnome = import('gnome')
i18n = import('i18n')
localedir = get_option('localedir')

subdir('po')
subdir('bottles')
subdir('data')

gnome.post_install(
	glib_compile_schemas: true,
	gtk_update_icon_cache: true,
	update_desktop_database: true,
)
