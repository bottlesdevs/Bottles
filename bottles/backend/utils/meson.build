pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
utilsdir = join_paths(pkgdatadir, 'bottles/backend/utils')

bottles_sources = [
  '__init__.py',
  'display.py',
  'gpu.py',
  'manager.py',
  'vulkan.py',
  'terminal.py',
  'file.py',
  'generic.py',
  'wine.py',
  'lnk.py',
  'decorators.py',
  'snake.py',
  'vdf.py',
  'imagemagick.py',
  'proc.py',
  'yaml.py',
  'nvidia.py',
  'threading.py',
  'gsettings_stub.py',
  'json.py',
  'singleton.py'
]

install_data(bottles_sources, install_dir: utilsdir)
