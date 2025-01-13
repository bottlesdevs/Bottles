pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dialogsdir = join_paths(pkgdatadir, 'bottles/frontend/windows')

bottles_sources = [
  '__init__.py',
  'crash_report_dialog.py',
  'dll_overrides_dialog.py',
  'duplicate_dialog.py',
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
  'journal_dialog.py',
  'bottle_picker_dialog.py',
  'proton_alert_dialog.py',
  'sandbox_dialog.py',
  'installer_dialog.py',
  'dependencies_check_dialog.py',
  'exclusion_patterns_dialog.py',
  'upgrade_versioning_dialog.py',
  'vmtouch.py',
  'window.py',
]

install_data(bottles_sources, install_dir: dialogsdir)
