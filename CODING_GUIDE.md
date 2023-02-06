## Build & Run locally
### use flatpak
Build and install
```bash
flatpak-builder --install --user --force-clean ./.flatpak-builder/builddir com.usebottles.bottles.yml
```
Run
```bash
flatpak run com.usebottles.bottles
```
Uninstall devel version
```bash
flatpak uninstall com.usebottles.bottles//master
```

## Run Test
### run all tests
```bash
pytest .
```