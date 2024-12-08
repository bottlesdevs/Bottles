project(
	'bottles',
	version: '51.15',
	meson_version: '>= 1.5.0',
	default_options: [
		'warning_level=2',
	],
	license: 'GPL-3.0-only'
)


APP_NAME = 'Bottles'
DEVELOPER_ID = 'com.usebottles'
BASE_ID = DEVELOPER_ID + '.' + meson.project_name()
APP_ID = BASE_ID
APP_VERSION = meson.project_version()
PROFILE = get_option('profile')

if PROFILE == 'development'
	APP_VERSION += '-' + run_command(
		'git', 'rev-parse', '--short', 'HEAD',
		check: true
	).stdout().strip()
	APP_NAME += ' (Development)'
	APP_ID += '.' + 'Devel'
endif


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
