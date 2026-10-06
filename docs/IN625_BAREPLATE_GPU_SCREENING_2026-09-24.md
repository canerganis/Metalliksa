# IN625 bare-plate CPU/CUDA thermal screening — 2026-09-24

## Karar ve kapsam

IN625 için ayrı, model-specific bir bare-substrate termal alan yolu eklendi.
Bu yol CPU ve açık CUDA cihazında aynı sınırlı entalpi/iletim yasasını uygular.
Durum `unvalidated-literature-model-screening` olarak kalır. Bu sonuç powder-bed,
tam transient LPBF, melt-pool doğruluğu veya bilimsel/deneysel yeterlilik değildir.

NIST AMB2018-02 çıplak IN625 metal yüzeyinde tekil lazer izlerini ve melt-pool
uzunluğu/soğuma ölçümlerini tanımlar; bu nedenle geometri seçimiyle uyumludur.
Bu rapordaki dondurulmuş küçük sayısal vaka NIST koşusu değildir ve ölçümle
karşılaştırma yapmaz. NIST kaynağı: [AMB2018-02](https://www.nist.gov/ambench/amb2018-02-description).

## Model sözleşmesi

- Malzeme otoritesi `in625_thermal_material` snapshot'ıdır; revizyon SHA-256'sı
  `f47b07e4c8288b8c7177001f069a254be3410bace43ad5ea2f73168ac4466f07`.
- Cp(T), k(T), faz aralığı ve gizli ısı aynı sınırlı yasa üzerinden hesaplanır;
  H→T ters dönüşümü yalnızca 273.15–1623.15 K içinde bracket edilir. Sınırı aşan
  enerji adımı reddedilir; sıcaklık kırpma veya superheat ekstrapolasyonu yoktur.
- Hücre merkezli 3B sonlu-hacim iletiminde yüz k değeri harmonik ortalamadır;
  tüm dış yüzler sıfır akılıdır. Hacim başına enerji değişimi komşu yüz iletim
  güçleri ve üst yüzeydeki kaynak gücünden gelir.
- Kaynak, kullanıcı tarafından açıkça verilen `absorbed_power_W` değerli hareketli
  normalize Gauss yüzey dağılımıdır. Optik absorptivite veya lazer coupling
  değeri türetilmez. Sınırda kesilen kiriş için devam eden kaynak yolu ortak
  `MINIMUM_SOURCE_CAPTURE_FRACTION = 1/1.01` kapısını uygular; düşük yakalamayı tam
  güce yeniden ölçekleyip yapay yoğunlaştırmaz.
- Yoğunluk 8440 kg/m³ olarak sabit tedarikçi-bülteni varsayımıdır; lot eşleşmesi
  veya sıcaklığa bağlı yoğunluk değildir. Kaynak [Special Metals Alloy 625
  bulletin, Table 2](https://www.specialmetals.com/documents/technical-bulletins/inconel/inconel-alloy-625.pdf).
- Akış, Marangoni, recoil, buharlaşma, ışınım/konveksiyon, toz yatağı ve evrilen
  serbest yüzey yoktur. IN625 build-job/slicer ve genel full-transient desteği
  kapalı kalır.

## Dondurulmuş sayısal kontrol

Vaka: 12×12×4 hücre; 0.25 mm eşit hücre boyu; 298.15 K başlangıç; 30 W açıkça
absorbe edilen yüzey girdisi; σ=0.30 mm; 1.25 m/s x-yönlü kaynak; 10 µs adım,
4 adım. Bu sentetik, küçük doğrulama vakasıdır; AMB ölçüm koşulu veya yeterlilik
deneyi değildir.

| Ölçüt | CPU NumPy | RTX 4060 `cuda:0` | Fark |
| --- | ---: | ---: | ---: |
| Son alan en yüksek sıcaklığı | 300.24236740455194 K | 300.24236740455194 K | 0 K |
| Son sıcaklık alanı | 576 hücre | 576 hücre | maksimum mutlak fark 0 K; RMS 0 K |
| Son özgül entalpi alanı | aynı referans | aynı referans | maksimum mutlak fark 0 J/kg |
| Enerji bilançosu maksimum artığı | 1.11e-16 J | 1.11e-16 J | aynı |
| En düşük alan kaynak yakalama oranı | 0.9999987338861048 | aynı geometri | eşik 0.990099... üstü |

Tek koşuda CUDA duvar süresi 1.325 s ve tepe ayrılmış cihaz belleği 100,864 bayt
ölçüldü. Bu çok küçük testin profilidir; hızlanma veya ölçeklenme iddiası değildir.

Bağımsız 64 noktalı Gauss–Legendre Cp integrali H(T) ve ters dönüşümü denetler.
CPU ve CUDA testleri ayrıca açık cihaz politikasını, tam alan paritesini, enerji
kapanışını, alan dışı entalpi reddini ve sıvılaşma sınırının aşılmamasını kapsar.
Bu testler yazılım/nümerik uygulama kanıtıdır; malzeme yasasının fiziksel
geçerliliğini kanıtlamaz.

## Kaynak ve bilimsel sınırlar

Sabau ve ark. katı faz Cp/k denklemlerini JMatPro hesaplaması olarak, sıvı Cp/k
değerlerini ise sabit varsayımlar olarak verir ([Appendix B](https://link.springer.com/article/10.1007/s11663-020-01808-w)).
Bu yayında bu uygulama için eşleşmiş lot belgesi, model belirsizliği veya tam
`sourceValidityRange_K` yoktur; registry bu aralığı `unknown` bırakır. Supplier
density girdisi ayrı bir kaynaktır ve NIST AMB2018-02 build lotuyla eşleştirilmiş
değildir. Sabit yoğunluk ve mushy aralık enterpolasyonları model varsayımlarıdır.

Bu nedenle P7 yalnızca **bare-plate numerical screening route** olarak açılır.
IN625 genel malzeme kabulü, powder-bed yeterliliği, bağımsız deneysel geçerlilik
veya üretim kullanımına açılmaz. NIST AMB2018-02 ile gerçek, source-revision-bound
geometri/soğuma kıyası; CPU ağ-zaman yakınsaması; uygulama API/UI akışı; ve tam
ölçek CUDA profil/alan sınamaları açık işlerdir.
