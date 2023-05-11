pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
dllsdir = join_paths(pkgdatadir, 'bottles/backend/dlls')

bottles_sources = [
  '__init__.py',
  'dll.py',
  'dxvk.py',
  'd8vk.py',
  'vkd3d.py',
  'nvapi.py',
  'latencyflex.py',
]

install_data(bottles_sources, install_dir: dllsdir)
