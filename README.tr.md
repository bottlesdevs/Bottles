<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/master/data/icons/hicolor/scalable/apps/com.usebottles.bottles.svg" width="64">
  <h1 align="center">Bottles</h1>
  <p align="center">Ortamları kullanarak kolayca wineprefix'i yönetin.</p>
</div>

<br/>

<div align="center">
  <a href="https://hosted.weblate.org/engage/bottles">
    <img src="https://hosted.weblate.org/widgets/bottles/-/bottles/svg-badge.svg" />
  </a>
  <a href="https://www.codefactor.io/repository/github/bottlesdevs/bottles/overview/master">
    <img src="https://www.codefactor.io/repository/github/bottlesdevs/bottles/badge/master" />
  </a>
  <a href="https://github.com/bottlesdevs/Bottles/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg">
  </a>
  <a href="https://github.com/bottlesdevs/Bottles/actions">
    <img src="https://github.com/bottlesdevs/Bottles/workflows/Build%20release%20packages/badge.svg">
  </a>
  <br>
  <a href="https://stopthemingmy.app" title="Please do not theme this app">
    <img src="https://stopthemingmy.app/badge.svg">
  </a>

  <hr />

  <a href="https://docs.usebottles.com">Doküman</a> ·
  <a href="https://forums.usebottles.com">Forum</a> · 
  <a href="https://t.me/usebottles">Telegram grubu</a> · 
  <a href="https://usebottles.com/funding">Finans</a>
</div>

<br/>

<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/master/screenshot.png">
</div>

## 📚 Doküman
Yeni bir sorun bildirimi açmadan önce daha önce ele alıp alınmadığını bizim [doküman](https://docs.usebottles.com)dan kontrol edin.
Lütfen belgelerin bazı sayfalarının hala yazılmakta olduğunu unutmayın.

## 🗣 Bottles'ın sizin dilinizi konuşmasına yardım edin
Nasıl yapılacağini [buradan](https://github.com/bottlesdevs/Bottles/tree/master/po#readme) okuyun. Bottles'ı dilinize çevirebilirsiniz veya mevcut olanlarını geliştirmeye yardımcı olabilirsiniz.
## 🦾 Özellikler
- Ortamlara dayalı şişeler oluşturun(kuralları ve bağımlılıkları ayarlayın)
- Tüm denemeleriniz için özelleştirilebilir bir ortama erişim
- Otomatik Yükleyiciler
- Dosya yöneticinizdeki menüyü kullnarak tüm yürütülebilir dosyaları (.exe/.msi/.bat) çalıştırın 
- Yürütülebilir dosyaların bağımsız değişkenleri için entegre yönetim ve depolama
- Özel ortam değişkenleri desteği
- Basitleştirilmiş DLL geçersiz kılmaları
- Birden fazla wine/proton/dxvk versiyonlarını anında yükeyin ve yönetin
- Daha iyi oyun performansı için çeşitli optimizasyonlar(esync, fsync, dxvk, cache, shader compiler, offload ... ve daha fazlası.)
- Çeşitli ince wine prefix ayarlarını Bottles'dan çıkmadan yapın
- Otomatik dxvk kurulumu
- Şişelerin çalıştırma güncellemelerini kontrol etme ve bozulmaları durumunda onarım
- Topluluğa dayalı uyumluluk kontrolü ile tümleşik bağımlılıklar yükleyicisi [depo](https://github.com/bottlesdevs/dependencies)
- Yüklenen programları tespit etmek
- Wine görevleri için tümleşik görev yöneticisi
- Destek için ProtonDB ve WineHQ'ya kolay erişim
- Bottles sürümleri arasında güncelleme yapılandırması
- Eski sürümden ve diğer yöneticilerden şişeleri yedekle ve içe aktar (Lutris, POL,..)
- Şişe versiyonlama
- ... ve Bottles'ı kullnarak daha fazlasını keşfedebilirsiniz!

### 🚧 Yapım Aşamasında
- Katmanlar (farklı katmanlardaki bağımlılıklar ve programlar) [#510](https://github.com/bottlesdevs/Bottles/issues/510)

## ↗️ Yükle
Bottles resmi olarak [Flatpak](https://flathub.org/apps/details/com.usebottles.bottles) olarak sağlanmaktadır.

Bottles'ı diğer dağıtımlarda nasıl kuracağınızı [burayı](https://docs.usebottles.com/getting-started/installation) okuyarak öğrenebilirsiniz
### Paket yapımcıları için bildirimler
Bottles'ı paketleyeceğiniz görmekten mutluluk duyuyoruz ancak sizden bazı küçük kurallara saygı göstermenizi istiyoruz
- Paket 'bottles' olmalıdır.Diğer dağıtımlarda son ekler kullanılabilir (ör. `bottles-git` git tabanlı paket için Arch Linux'ta) diğerlerinde ise RDNN formatı gereklidir (ör.elementary OS ve Flathub deposunda `com.usebottles.bottles`). Diğer tüm isimlendirmeler önerilmez.
- Dış dosyaları paketlemeyin ve kodları değiştirmeyin, Açıkçası zor bir script yok paketleme için olan dosyalar hariç.
- Paket versiyounları CalVer modelini (yıl.ay.gün) ve projenin yayın döngüsünü takip etmelidir. Bottle her ay 2 kere güncelleme sürümü yayınlar : ayın 14. günü ve 28. günü. Bir düzeltme yayımlandığında, bu sürüm sürüme eklenir (ör. 2022.2.14-1). Bottles'ın da zorunlu olmayan ve şu anda sadece Flatpak tarafından kullanılan bir kod adı var.

## Kısayollar
| Kısayollar |         Eylem          |
|:--------:|:-----------------------:|
| `Ctrl+Q` |      Bottles'ı Kapat|
| `Ctrl+R` | Şişe listesini yeniden yükle|
|   `F1`   | Dokümantasyona git|
|  `Esc`   |         Geri Dön |

## SSS
- [Neden Bottles?](https://docs.usebottles.com/faq/why-bottles)
- [Winetricks Nerede?](https://docs.usebottles.com/faq/where-is-winetricks)
- [Eski sürümler kullanımdan kaldırılacak mı?](https://docs.usebottles.com/faq/updates-and-old-versions#older-versions-will-be-deprecated)
- [Geriye dönük uyumlu mu?](https://docs.usebottles.com/faq/updates-and-old-versions#backward-compatibility)

## Code of Conduct
Bu proje [GNOME Davranış Kuralları](https://wiki.gnome.org/Foundation/CodeOfConduct) 'na uyar.
 Bottles'ı bütün alanlarda takip etmeniz beklenir, Bu deponun, projenin sosyal medyası, mesajlaşma sohbetleri ve forumları gibi. Bağnazlık ve tacize müsamaha gösterilmeyecektir.

## Sponsorlar
<a href="https://www.jetbrains.com/?from=bottles"><img height="55" src="https://unifiedban.solutions/static/images/jetbrains-logos/jetbrains.png" /></a>&nbsp;&nbsp;&nbsp;
<a href="https://www.gitbook.com/?ref=bottles"><img height="55" src="https://www.gitbook.com/cdn-cgi/image/height=55,fit=contain,dpr=1,format=auto/https%3A%2F%2F2775338190-files.gitbook.io%2F~%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252FNkEGS7hzeqa35sMXQZ4X%252Flogo%252FTO5E3RjWKeaJmYYWMGWV%252Fspaces_gitbook_avatar-rectangle.png%3Falt%3Dmedia%26token%3Da34e957e-f044-4bee-abee-23946d2e9cfb" /></a>&nbsp;&nbsp;&nbsp;
<a href="https://www.linode.com/?from=bottles"><img height="48" src="https://usebottles.com/uploads/linode-brand.png" /></a>
