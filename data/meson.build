conf = configuration_data()
conf.set('APP_ID', APP_ID)
conf.set('BASE_ID', BASE_ID)
conf.set('APP_NAME', APP_NAME)
conf.set('DEVELOPER_ID', DEVELOPER_ID)

desktop = i18n.merge_file(
  input: configure_file(
    input:  BASE_ID + '.desktop.in.in',
    output:  BASE_ID + '.desktop.in',
    configuration: conf
  ),
  output: APP_ID + '.desktop',
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
  input: configure_file(
    input: BASE_ID + '.' + 'metainfo.xml.in.in',
    output: BASE_ID + '.' + 'metainfo.xml.in',
    configuration: conf
  ),
  output: APP_ID + '.' + 'metainfo.xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

gnome.compile_resources('data',
  'data.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir
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

subdir('icons')