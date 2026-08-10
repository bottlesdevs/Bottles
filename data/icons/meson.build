scalable_dir = 'hicolor' / 'scalable' / 'apps'
install_data(
  scalable_dir / ('@0@.svg').format(APP_ID),
  scalable_dir / 'soda-runner.svg',
  scalable_dir / 'caffe-runner.svg',
  scalable_dir / 'vaniglia-runner.svg',
  scalable_dir / 'protosoda-runner.svg',
  install_dir: get_option('datadir') / 'icons' / scalable_dir
)

symbolic_dir = 'hicolor' / 'symbolic' / 'apps'
install_data(
  symbolic_dir / ('@0@-symbolic.svg').format(APP_ID),
  install_dir: get_option('datadir') / 'icons' / symbolic_dir
)
