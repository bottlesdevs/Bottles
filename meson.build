project(
	'bottles',
	version: '2022.8.28-brescia-2',
	meson_version: '>= 0.59.0',
	default_options: [
		'warning_level=2',
	],
  	license: 'GPL-3.0-or-later'
)

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
