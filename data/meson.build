conf = configuration_data()
conf.set('APP_NAME', APP_NAME)
conf.set('APP_ICON', APP_ICON)

desktop_file = configure_file(
        input:  'com.usebottles.bottles.desktop.in.in',
       output:  'com.usebottles.bottles.desktop.in',
    configuration: conf)

desktop = i18n.merge_file(
  input: desktop_file,
  output: 'com.usebottles.bottles.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils,
    args: [desktop]
  )
endif

appstream_file = i18n.merge_file(
  input: 'com.usebottles.bottles.metainfo.xml.in',
  output: 'com.usebottles.bottles.metainfo.xml',
  po_dir: '../po',
  install: true,
  install_dir: join_paths(get_option('datadir'), 'metainfo')
)

appstream_util = find_program('appstream-util', required: false)
if appstream_util.found()
  test('Validate appstream file', appstream_util,
    args: ['validate', appstream_file]
  )
endif

install_data('com.usebottles.bottles.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0/schemas')
)

compile_schemas = find_program('glib-compile-schemas', required: false)
if compile_schemas.found()
  test('Validate schema file', compile_schemas,
    args: ['--strict', '--dry-run', meson.current_source_dir()]
  )
endif

install_data(
    join_paths('icons/hicolor/scalable/apps', APP_ICON),
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'icons/hicolor/scalable/apps')
)

install_data(
    join_paths('icons/symbolic/scalable/apps/com.usebottles.bottles-symbolic.svg'),
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'icons/hicolor/symbolic/apps')
)

install_data(
    join_paths('icons/hicolor/scalable/apps/com.usebottles.bottles-program.svg'),
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'icons/hicolor/scalable/apps')
)

install_data(
    join_paths('icons/symbolic/scalable/apps/bottle-symbolic.svg'),
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'icons/hicolor/symbolic/apps')
)

install_data(
    join_paths('icons/symbolic/scalable/apps/bottles-steam-symbolic.svg'),
    install_dir: join_paths(get_option('prefix'), get_option('datadir'), 'icons/hicolor/symbolic/apps')
)

mimedir = join_paths(get_option('prefix'), get_option('datadir'), 'mime/packages')
mime_sources = [
    'mime/com.usebottles.bottles.exe.xml',
]

install_data(mime_sources, install_dir: mimedir)