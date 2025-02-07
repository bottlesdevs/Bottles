pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
frontenddir = join_paths(pkgdatadir, 'bottles/frontend')

fs = import('fs')

if not fs.is_file('/' + '.flatpak-info')
  error('file does not exist')
endif

gnome = import('gnome')
blueprints = custom_target('blueprints',
  input: files(
    'component-entry-row.blp',
    'check-row.blp',
    'dependency-entry-row.blp',
    'bottle-details-page.blp',
    'details-dependencies-view.blp',
    'details-task-manager-view.blp',
    'bottle-details-view.blp',
    'bottle-picker-dialog.blp',
    'crash-report-dialog.blp',
    'dependencies-check-dialog.blp',
    'dll-overrides-dialog.blp',
    'drives-dialog.blp',
    'environment-variables-dialog.blp',
    'gamescope-dialog.blp',
    'launch-options-dialog.blp',
    'proton-alert-dialog.blp',
    'rename-program-dialog.blp',
    'sandbox-dialog.blp',
    'vkbasalt-dialog.blp',
    'display-dialog.blp',
    'vmtouch-dialog.blp',
    'fsr-dialog.blp',
    'mangohud-dialog.blp',
    'dll-override-entry.blp',
    'drive-entry.blp',
    'env-var-entry.blp',
    'bottle-row.blp',
    'bottles-list-view.blp',
    'local-resource-row.blp',
    'new-bottle-dialog.blp',
    'onboard-dialog.blp',
    'preferences.blp',
    'program-row.blp',
    'task-row.blp',
    'window.blp',
    'details-preferences-page.blp',
    'help-overlay.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],)

gnome.compile_resources('bottles',
  'bottles.gresource.xml',
  gresource_bundle: true,
  dependencies: blueprints,
  install: true,
  install_dir: pkgdatadir,
)

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

bottles_sources = [
  '__init__.py',
  'main.py',
  'operation.py',
  'gtk.py',
  'common.py',
  'filters.py',
  'sh.py',
  'new_bottle_dialog.py',
  'bottles_list_view.py',
  'bottle_details_view.py',
  'preferences.py',
  'bottle_details_page.py',
  'details_dependencies_view.py',
  'details_preferences_page.py',
  'details_task_manager_view.py',
  'dependency_entry_row.py',
  'executable.py',
  'program_row.py',
  'component_entry_row.py',
  'crash_report_dialog.py',
  'dll_overrides_dialog.py',
  'environment_variables_dialog.py',
  'generic.py',
  'launch_options_dialog.py',
  'onboard_dialog.py',
  'rename_program_dialog.py',
  'drives_dialog.py',
  'gamescope_dialog.py',
  'vkbasalt_dialog.py',
  'fsr_dialog.py',
  'mangohud_dialog.py',
  'display_dialog.py',
  'generic_cli.py',
  'bottle_picker_dialog.py',
  'proton_alert_dialog.py',
  'sandbox_dialog.py',
  'dependencies_check_dialog.py',
  'vmtouch_dialog.py',
  'window.py',
  params_file,
]

install_data(bottles_sources, install_dir: frontenddir)
