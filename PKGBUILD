# Maintainers: Mirko Brombin <send@mirko.pm>, Gabriele Musco <emaildigabry@gmail.com>
# Upstream URL: https://github.com/mirkobrombin/Bottles/

pkgname=bottles-git
pkgver=0.0.8.r10.g4d4b2f7-1
pkgrel=1
pkgdesc='A wineprefix manager designed for elementary OS'
arch=('any')
url='https://github.com/mirkobrombin/Bottles'
license=('GPL3')
depends=('wine' 'gtk3>=3.14' 'python' 'granite' 'xterm')
makedepends=('git')
provides=('bottles')
conflicts=('bottles')
source=("bottles::git+https://github.com/mirkobrombin/Bottles")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/bottles"
  git describe --long --tags | sed 's/\([^-]*-g\)/r\1/;s/-/./g'
}

package() {
  cd "$srcdir/bottles"
  mkdir -p $pkgdir/usr
  python setup.py install --prefix $pkgdir/usr
}
