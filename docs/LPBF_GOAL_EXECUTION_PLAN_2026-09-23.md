# LPBF ortak çekirdek ve veri hattı uygulama planı

Durum: 27 Eylül 2026 hedef revizyonu kullanıcı isteğiyle Codex hedefi olarak
oluşturuldu; hedef aktiftir. Başlangıç: `codex/lpbf-buildjob-material-identity`,
`a35499d` (23 Eylül 2026). Ana program çerçevesi
`DIGITAL_TWIN_MASTER_PLAN_2026-09-21.md`; güncel sınırlar
`LPBF_SHARED_CORE_CONTRACT.md`, `LPBF_CORE_BASELINE_2026-09-21.md` ve
`STATUS.md` içindedir. Bu belge tamamlanmış paketleri yeniden açmadan kalan
işlerin yürütme sırasını ve çıkış kapılarını tanımlar.

## Güncel hedef ve kapsam — 2026-09-27

Metalliksa-1'de sürümlü malzeme, girdi ve motor kimliğiyle tekrarlanabilir
LPBF iş akışını tamamla. Ortak fizik motorlarını kaynak, birim, korunum ve
ağ/zaman yakınsaması açısından doğrula; somut kusurları gider. CPU referansı,
PyTorch CUDA ve Warp CUDA uygulamalarını aynı termal sözleşmede karşılaştır;
ölçülmüş veri aktarımı, senkronizasyon ve hesap darboğazlarını sonuçları
koruyarak azalt. GPU koşularını kalıcı kaynak/koşu/sonuç arşivine bağla ve
seç→hesapla→karşılaştır→dışa aktar→geri yükle akışını gerçek arayüzde doğrula.
Dört mevcut alaşımın tek malzeme otoritesini koru. IN625 öncelikli en az bir
yeni alaşımı ancak kaynak, belirsizlik ve model uygunluğu kapısını geçerse tam
modele kabul et. CPU sonuçlarını uygun bağımsız IN718 ölçümleriyle karşılaştır.
Yazılım doğruluğu, sayısal doğrulama ve deneysel geçerlilik için ayrı kanıt sun;
sentetik verileri, tahmini girdileri, model çıktılarını ve deney ölçümlerini
ayrı göster. Kanıt eksikse sonuç `unvalidated` / doğrulanmadı kalır.
EIS/EDS ve ilgisiz modüller kapsam dışıdır.

Bu bölüm güncel öncelik sırasıdır; aşağıdaki tarihli kayıtlar tarihsel kanıttır.
Önceki karttaki LPBF dışı genişleme bu konuşmanın kapsamıyla çelişiyordu.
Kullanıcının açık isteği üzerine, önceki hedef artık mevcut değilken bu kapsamla
yeni hedef oluşturuldu ve araç `active` durumunu doğruladı.

## Öncelikler ve kabul kapıları

| Sıra | Hedef | Kabul ölçütü |
| --- | --- | --- |
| 1 | Kanıt ve koşu devamlılığı (P0–P4, P10) | Önce mevcut koşuların canlı/tamamlanmış/kesilmiş durumu ve çıktı kimlikleri okunur; yinelenen hesap başlatılmaz. Kaynak baytları, malzeme revizyonu, girdiler ve motor parmak izi korunur. Güncel CPU ağ/zaman sonuçları önceden dondurulmuş kapılarla değerlendirilir. |
| 2 | Kısa ürün kabul akışı (P3, P8) | Küçük ve sabit gerçek CPU hesabıyla seçim, hesap, kaynak bağlantısı, karşılaştırma durumu, dosya indirme/yükleme, yalıtılmış restore ve sayfa yenileme tamamlanır; kimlikler ve çıktı hash'leri korunur. API ve tarayıcı kanıtları ayrı kaydedilir. |
| 3 | Aynı fizik için CPU/Torch/Warp tabanı (P6, P11) | Malzeme yasası, ağ, sınırlar, kaynak integrali, zaman adımı ve gözlem operatörü eşleştirilir. Tam sıcaklık alanı, entalpi/enerji, kabul edilen adımlar ve eriyik geometrisi önceden belirlenen toleranslardan geçer. Phase 22 çok-fizik yolu ayrı sözleşme olarak tutulur. |
| 4 | Ölçülmüş hızlandırma (P11) | Önce GPU indirgemeleri ve kalıcı tamponlarla büyük alan kopyaları azaltılır. Kaynak/sınırlayıcı taşıma, kernel birleştirme ve CUDA Graph ancak profil gerekçelendirirse uygulanır. Her değişiklik aynı-girdi doğruluk kapısı ve eşlenmiş toplam süre ölçümünden geçer. |
| 5 | Dayanıklı GPU ürün yolu (P12, P8) | Cihaz başına yönetilen GPU kuyruğu, tekrar kullanılan bellek/derleme önbelleği, ilerleme/iptal/hata ve yenileme sonrası işe bağlanma doğrulanır. GPU sonuçları sürümlü kaynak/koşu paketleriyle dışa aktarılır ve geri yüklenir. |
| 6 | Deney ve alaşım kabulü (P5, P7) | IN718 ölçümünün rejim, geometri, tarama geçmişi, gözlem tanımı ve belirsizliği modele uygundur. Yeni alaşımın gereken özellikleri kaynak ve belirsizlikle kapsanır; desteklenen her yetenek ayrı kabul edilir. Eksik veri tam-model kabulü veya deneysel başarıya dönüştürülmez. |
| 7 | Birleşik teslim (P9) | İlgili yazılım, sayısal ve arayüz kontrolleri; kanıt tablosu; yerel commit ve devam kaydı tamamlanır. Açık bilimsel kapılar açık kalır; kısmi ürün teslimi tüm hedefin tamamlandığı anlamına gelmez. |

P5/P7 kaynak araştırması bağımsız ilerleyebilir. Kısa P8 akışı eksik bilimsel
kapıları doğru gösterebilir; bunun için yeni alaşımın kabulünü beklemek gerekmez.
Tam deneysel karşılaştırma ve yeni alaşım hedefleri bu sırayla kaldırılmaz.

### Performans ölçüm sözleşmesi

- Küçük/orta/büyük iş yükleri ve toleranslar sonuçlar görülmeden sabitlenir;
  her backend yalnız desteklediği aynı fizik/girdi ile karşılaştırılır.
- İlk derleme/başlatma ve ısınmış süre ayrı raporlanır. Isınmadan sonra en az
  beş dönüşümlü eşlenmiş tekrar alınır; medyan, dağılım, donanım, yazılım
  sürümleri, hassasiyet ve bellek kullanımı saklanır. Ölçüm sırasında aynı
  cihazda rakip ağır hesap çalıştırılmaz.
- Kuyruk, başlatma, hesap, CPU–GPU aktarımı, arşiv ve arayüz süreleri ayrılır;
  kernel süresi ile toplam süre karıştırılmaz. GPU ölçümü uygun cihaz
  senkronizasyonu/olaylarıyla tamamlanan işi kapsar. Profil ek yükü ayrı tutulur.
- Hız kazancı ölçüm saçılımından ayırt edilemiyorsa kanıtlanmış sayılmaz.
  Mikrobenchmark kazancı uygulamanın toplam kazancı olarak sunulmaz.
- İlk optimizasyonlarda mevcut float64 korunur. Hassasiyet azaltımı ayrı
  hata bütçesi ve yakınsama değerlendirmesi gerektirir. İndirgeme sırası,
  tepe seçimi ve kabul edilen zaman adımlarındaki değişiklikler denetlenir.
- Otomatik CPU/GPU seçimi ancak ölçülmüş iş yükü aralıklarında uygulanır;
  aksi halde CPU varsayılanı ve açık GPU seçimi korunur. İstenen CUDA cihazı
  kullanılamıyorsa sessiz CPU dönüşü yapılmaz.
- Tek malzeme otoritesi ve sürümlü kaynak sözleşmesi korunur. Önbellek ve
  arşiv kimliği model, girdiler, malzeme revizyonu, uygulama parmak izi ve
  backend/hassasiyet ayarlarını ayırt eder; fiili cihaz ve çalışma ortamı
  kayda eklenir. Windows derleme önbelleği ve eşzamanlı kullanım hataları
  açık raporlanır; süreçler arasında global ayar yarışına izin verilmez.

## Bitiş tanımı

Yerel uygulamada kaynaklı bir IN718 deney/senaryo kaydı seçilir; eksik koşullar
görünür; sürümlü malzeme ve model kimliğiyle CPU termal hesap çalıştırılır;
uygun eşlenmiş ölçümlerle ayrı bir karşılaştırma raporu üretilir; çalıştırma,
kaynak revizyonu ve tüm çıktı baytları dışa aktarılıp bağımsız dizine geri
yüklenir. Aynı sınırlandırılmış termal problem açıkça seçilen GPU cihazında
çalışır ve önceden dondurulmuş CPU/GPU sayısal karşılaştırma kapısından geçer.
Dört mevcut alaşım için model yeterlilik ve veri boşluğu matrisi yayımlanır;
en az bir yeni alaşım (öncelik IN625) kaynaklı özellik ve model veri kapısından
geçerek desteklendiği yeteneklerde kullanılır. Her yeni termal modelin GPU
kabiliyeti ayrıca aynı özellik yasası ve sınır koşullarıyla CPU karşılaştırmasına
tabi tutulur; en az bir yeni alaşım için GPU termal yolu doğrulanır. Başarısız
bilimsel kapı başarılı gibi etiketlenmez.

Sınırlı IN625 bare-plate taraması tam-model alaşım kabulü yerine geçmez.
Uygun bağımsız IN718 karşılaştırması veya yeni alaşım veri kapısı kapanmamışsa
bu bilimsel hedefler tamamlanmış sayılmaz; ürün akışı kendi kapsamıyla teslim
edilebilir. Performans ve GPU işletim/arşiv hedeflerinin bitişi P11/P12 kabul
ölçütlerine bağlıdır.

## Paketler ve bağımlılıklar

| Paket | İş | Bağımlılık | Çıkış kanıtı |
| --- | --- | --- | --- |
| P0 | Güncel kaynak ve kanıt çizgisi | Yok | UI→API→worker→solver→malzeme→test haritası; mevcut/eksik kabul kanıtları ve interpreter/backend kaydı |
| P1 | Build-job özellik snapshot kimliği | P0 | Gerçekte kullanılan termal/slicer özellikleri, birimler, model/sürüm ve kanonik alaşım bir sürümlü içerik kimliğine bağlanır; alias ve cache davranışı doğrulanır |
| P2 | Malzeme otoritesi ve adaptör sınırları | P1 sözleşmesi | Dört alaşımın kaynak, özellik yasası, sıcaklık/birim ve model uygunluğu tek otorite üzerinden açıklanır; taşınan dönüşümler sayısal olarak eşleşir |
| P3 | Kaynak/run kalıcılığı ve uygulama API'si | P0, P1 | Tam snapshot, exact kaynak revizyonu, manifest ve bayt doğrulaması; çakışma/bozuk veri/legacy durumu; mevcut iş kuyruğu korunur |
| P4 | CPU termal sayısal kapısı | P2 | Analitik korunum ve sınır testleri; en az üç ağ ve üç zaman seviyesi; sonuç öncesi sabitlenmiş toleranslarla yakınsama raporu; OpenFOAM kapsamı açık |
| P5 | IN718 deney/ölçüm karşılaştırması | P3, P4 | Kaynak ve ölçüm operatörü, gerçek proses/geometri, tekrar grubu, belirsizlik ve kalibrasyon/holdout ayrımı bağlıdır; sonuç/eksik veri dürüstçe raporlanır |
| P6 | GPU termal eşleşmesi ve alaşım adaptörleri | Mevcut alaşımlar: P2, P4; yeni alaşım: ayrıca P7 | Açık cihaz seçimi; her GPU'ya açılan alaşımda aynı fizik/girdi/boundary; CPU karşılaştırması, bağımsız analitik kontrol, enerji/alan metrikleri ve bellek/süre profili; en az bir yeni alaşım GPU yolu |
| P7 | Alaşım genişlemesi | P2, P4 | Dört alaşım yeterlilik matrisi; en az bir yeni alaşımın kaynaklı özellik revizyonu, sıcaklık kapsamı, CPU model kabiliyeti, GPU adaptör kararı ve ayrı sayısal kontrolleri |
| P8 | Bütünleşik ürün akışı | Kısa kabul: P3; tam kapsam: P5, P6, P7, P12 | Seç→hesapla→karşılaştır→dışa aktar→geri yükle; eski sonuç ve başarısız/eksik durumları görünür; gerçek tarayıcı/klavye kontrolü |
| P9 | Son entegrasyon kapısı | P0–P8, P10–P12 | İlgili Python/TypeScript/sayısal/tarayıcı kontrolleri; değişiklik kapsamı, kanıt ve sınırlamalar; STATUS/PROOF ve bitiş kararı |
| P10 | Çekirdek fizik kusurlarının giderilmesi | P0, ilgili motorun kanıt sınırı | Somut başarısız örnekten hareketle entalpi, enerji, sınır akısı, birim ve zaman adımı kusurlarını motor bazında düzelt; ilgili analitik/sayısal testleri ve değişen benchmark'ları çalıştır; çözülemeyen fizik ve deney sınırlarını çıktıda açık tut |
| P11 | CPU/CUDA/Warp performansı | P0, P2; aday kabulü: P4, P6 | Tekrarlanabilir eşlenmiş profil ve ölçüm; azaltılmış aktarım/senkronizasyon; tam-alan, enerji, adım ve geometri kapıları; toplam süre ve bellek kanıtı; ölçüm saçılımını aşmayan kazanç için iddia yok |
| P12 | GPU çalışma ve arşiv güvenilirliği | P3, seçilen sözleşmenin P6 kanıtı | Açık cihaz/gerçek backend, yönetilen kuyruk ve önbellek, iptal/hata/kurtarma; GPU kaynak/koşu/sonuç kimlikleriyle API ve gerçek arayüzde paket çevrimi |

P10, P4–P9 ile birlikte yürür: doğrulanmış bir motor kusuru diğer paketlerin
sonucunu etkiliyorsa önce onarılır, önceki raporlar geriye dönük olarak PASS
sayılmaz. İlk paket Phase 21'in ayrı 2B geçici entalpi motorundaki entalpi
tersi, sınır akısı ve zaman adımı kusurlarını düzeltti (`69fae9a`). Bu motorun
hareketsiz 2B kaynak geometrisi gerçek LPBF eriyik havuzu için yeterli olmadığı
için sonuç tarama olarak etiketlenir. 3B referans P4 kapısı bağımsızdır.

Kullanıcı P10'u çekirdek motorlara genişletmeyi ayrıca yetkilendirdi. Phase 22
Warp solver'ında metal-hava yanal yüz akısı metal hücre maskesiyle kapatıldı;
zaman entegrasyonu son aralığı kırpar ve sıfır süreli iz için adım çalıştırmaz.
Yüz hızlarının altı çapraz bileşeni MAC koordinatlarında dört-yüzlü bilinear
ortalama ile örneklenir; entalpi taşınımı ortak yüzlerde aynı upwind akısını
kullanır ve iç akıların global entalpi toplamında iptal olduğu CPU Warp testiyle
denetlenir. Basınç projeksiyonunda ayrık yüz diverjansı, gradyanı ve Poisson
operatörü aynı sıvı/serbest-yüzey/katı/alan-sınırı sınıflamasını kullanır;
checkerboard, üretilmiş çözüm, ayrık bileşenler ve Neumann uyumluluk testleri
vardır. Önceki sabit 10 Jacobi turu düzgün hız alanında yakınsamıyordu: göreli
L2 diverjans artığı 9^3 ve 17^3 ağlarda 0,420619 ve 0,793338; 300 turda 17^3
artığı 0,0378842 idi (hedef 1e-3). Bunun yerine aynı stencil üzerinde cihaz
indirgemeli matris-olmayan preconditioned conjugate gradient (PCG) çözücüsü
eklendi. CPU Warp testleri 9^3'te 15 iterasyonda 7,606e-4, 17^3'te 35
iterasyonda 8,074e-4 ölçülen post-projection diverjans oranına ulaştı; iki
ölçüm de 1e-3 hedefini karşılıyor. Uyumsuz Neumann bileşenleri
`numerical_failure`, uyumlu ayrık bileşenler yakınsıyor; iterasyon tükenmesi ve
sayısal bozulma da ayrıca raporlanıyor. Runtime çözüm durumu ölçülen residual'a
bağlıdır. CUDA donanımında çalıştırma ve performans bu Windows hostta
doğrulanmadı; GPU-device doğrulaması iddia edilmez. CPU transient motorunun
yüzey kesmesi de tam hücre yaklaşımını kullanır; cut-cell kütle/iletim
düzeltmesi ayrı kapsamdır.

## IN718 geometri karşılaştırmasının ön protokolü

P5 için aday gözlem, NIST AMB2022-03'ün çıplak IN718 levhada yedi tek iz
koşuluna ait optik kesit W/D ortalamalarıdır. Resmî sonuç belgesi Table 4 her
koşulda altı ölçümün ortalamasını ve standart sapmasını verir. Kaynak ölçüm
tanımı, belirtilen kesitte başlangıç levha yüzeyinden en büyük derinliği
ve kesitteki en büyük genişliği kullanır; model çıktısındaki başka bir genişlik
tanımı bunun yerine geçmez. Birincil pilotta bu yedi koşula sonuçlara bakarak
kalibrasyon yapılmayacak; hata ve ölçüm yayılımı koşul bazında raporlanacaktır.
Sonradan kalibrasyon yapılırsa koşul grupları ve holdout ayrımı önceden ayrı
bir protokol revizyonunda dondurulacaktır.

NIST yazarlarının sonraki [ölçüm yayını, s. 369 Tablo 4](https://link.springer.com/content/pdf/10.1007/s40192-024-00355-5.pdf)
bu altı ölçümü koşul başına üç tekrar iz × iz başına iki kesit olarak açıklar.
Challenge yöntemindeki P1–P4 kesilmiş levha parçası konumları, Tablo 4'ün
koşul başına dört ölçümü olduğu şeklinde yorumlanmamalıdır. Yerel agregat
transkripsiyon bireysel kesitleri veya görüntüleri içermez. Resmî NIST
[ölçüm çalışma kitabı](https://data.nist.gov/od/ds/ark:/88434/mds2-2718/AMB2022-718-SH1-MeltPool_Cross-Section_Measurement_Results.xlsx)
ayrı bayt kaynağı olarak arşivlendi (SHA-256
`2cfaac96aaca3dabb77b7029f842cdcc7e75c5a2cf3577d0734823246364a931`).
BP1 levhasındaki yedi koşulun her birinde üç iz × iki kesit vardır; ölçüm
konumları iz başlangıcından 4,9 ve 6,0 mm'dir. Bu 42 BP1 satırının örnek
ortalaması ve standart sapması, yedi koşulun yerel Tablo 4 transkripsiyonunu
0,1 µm yuvarlamada yeniden üretir; model/deney kıyası ayrı kapıda kalır.

Kıyas başlamadan modelin çıplak levha koşulunu, 4,9 ve 6,0 mm'deki ölçüm
kesitlerini ve kaynağın `D4σ` ışın tanımını karşılayabildiği gösterilmelidir.
[NIST'in 2025 metroloji raporu](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958616) 67 µm nominal tek-iz koşulu için ölçülmüş
Gaussian `Dg` çapını ve %5,2 birleşik standart belirsizliği verir; dairesellik
sapması 1 µm olarak raporlanır. Rapor ayrıca normalize edilmiş ölçülmüş sinyal
yoğunluğunu ve merkez x/y kesitlerini Fig. 7'de, ölçülmüş beam-caustic noktaları
ile `Dg(z)` uyumunu Fig. 8'de yayımlar. Fig. 5 ise sentetik/simüle edilmiş
profil örneğidir. İncelenen açık kaynaklarda ham sayısal 2B kamera dizisi veya
NIST ölçüm baytlarına bağlı tarama-özel profil kaydı bulunmadı; yayımlanmış
grafiğin sayısallaştırılması ham ölçümün yerini tutmaz ve ayrıca
sayısallaştırma belirsizliği taşır. Uygulamanın 1/e² çapı ideal Gaussian'da
`Dg` ile aynıdır; gerçek ışın için bu eşitlik ve nominal D4σ eşleşmesi açık bir
yaklaşım olarak kaydedilmelidir. Kaynak-baytına bağlı ölçüm kaydı ve çap eşleme
belirsizliği arşivlenene kadar sıkı P5 profil kapısı kapalı kalır. Mevcut katalogda
yer alan 40 µm katman/110 µm hatch değerleri tek iz çıplak levha ölçümü değildir;
bu değerler eşleştirme için kullanılamaz. Uygun operatör yoksa kıyas durumu
`unavailable` olur. Ham termografi sıcaklığı bu W/D kaynağından türetilmez.

### 10 mm çıplak levha modeli için mevcut uygulama sınırı

2026-09-24 kaynak/hesaplanabilirlik denetiminde NIST termografi Table 1 ve 2
Case 0 girdileri 285 W, 960 mm/s, 67 µm spot, tek +X yönlü 10 mm çıplak levha
izi ve 23,5 °C altlık sıcaklığı olarak alındı ([resmî yöntem belgesi](https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101)).
67 µm, NIST'in [2025 raporundaki](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958616) ölçülmüş nominal Gaussian `Dg` çapıyla
desteklenir; rapor %5,2 birleşik standart çap belirsizliği verir, normalize
ölçülmüş profil grafiğini ve merkez kesitlerini de yayımlar. Solver bunu
ideal-Gaussian 1/e² girdisi olarak kullanabilir; `Dg`–D4σ eşleşmesi ise yalnız
ideal/çok yakın Gaussian yaklaşımıdır. Ham sayısal 2B ışınım dizisi ve
source-byte bağlı, tarama-özel ölçüm kaydı incelenen açık kaynaklarda bulunmadı;
ölçülmüş çap tam profil SHA'sı sayılmaz ve tek başına P5 kapısını açmaz.

Mevcut `python/lpbf_simulation.py` giriş sınırı `trackLength_um <= 3000`;
10.000 µm Case 0 girdisi çözüm başlamadan reddedilir. Alan hesabında sınırı
yalnız bellekte geçici olarak genişletmek, hiçbir termal çözüm çalıştırmadan,
mevcut kare X/Y alanının 10,201 mm yayılım için 20/10/5 µm'de sırasıyla
4.177.936 / 32.315.671 / 258.272.222 hücre istediğini gösterdi. İnce ağda tek
float64 alan bile yaklaşık 2,07 GB'dir; bu uygulama şekli 3+3 çalışma için
uygun değildir. Tam iz süresini korumakla birlikte dar enine alan kullanan bir
hareketli çerçeve/dar-bant model veya yeterli bellekli ayrı bir backend
gereklidir. Alan hesabı geometri tahminidir, solver çalışması değildir.

Mevcut `midtrack_bare_plate_section` tek bir x=0 kesitinde ever-liquidus
hücrelerini raporlar. NIST optik tanımı derinliği başlangıç yüzeyinden en büyük
dikey uzaklık, genişliği kesitteki en büyük yatay uzaklık olarak alır; Tablo 4
koşul başına üç izde 4,9 ve 6,0 mm konumlarından altı ayrı kesit içerir
([NIST geometri tanımı, s. 3 ve Tablo 4](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957295)).
Yeni model bu iki fiziksel kesiti ve üç tekrar gözlemini ayrı korumalı; mevcut
x=0 termal vekili bunların ortalaması gibi sunulmamalıdır. Sonraki P5 işi bu
dar-bant/konumlu kesit modelini ve ona bağlı ağ-zaman kapısını tasarlamaktır.
Nominal Gaussian sonuçları ayrı, açıkça unvalidated tarama olarak kalır;
ölçülmüş profil, altı kesit gözlemi ve geçen bağımsız 3+3 kapı olmadan NIST
residual üretilmez.

2026-09-24 physics follow-up adds a hard model-validity stop: the 10 mm CPU
Case 0 attempt reaches the fixed-material boiling boundary after 133 source
steps, at only 0.1024% of the scan. Do not remove the guard, rerun the same
solver, or infer a complete melt pool. `enthalpy-fv-6` currently has no
evaporation, surface-mass recession, recoil, or melt-flow equations; Phase 22's
height-graph terms are heuristic and the available OpenFOAM defaults are not
IN718-qualified. P5 stays unavailable until a new, source-bounded material/beam
model revision passes independent manufactured conservation and force/energy
checks, then receives a new prospective 3-mesh × 3-timestep protocol. This
prerequisite does not change any existing P4/P5 threshold.

## Değişmez sözleşmeler

- `four_alloy_materials.py` mevcut dört alaşımın ortak malzeme otoritesidir.
  Modelin kullandığı özellik sıcaklığı, optik varsayımı ve birim dönüşümü
  sonucunda görünür kalır. Başka alaşımdan sessiz sabit aktarılmaz.
- Build-job `rosenthal-screening-v1`, transient referans ve termal OpenFOAM
  kimlikleri birbirinin bilimsel kanıtı sayılmaz. Özellik içerik hash'i bayt/
  içerik kimliğidir; deneysel doğrulama, kaynak güvenilirliği veya imza değildir.
- NIST IN718 ham kamera sinyali, doğrulanmış sıcaklık değildir. `D4σ` spot etiketi
  `1/e²` ışın çapına kanıtsız çevrilmez. Birincil dönüşüm/ölçüm tanımı eksikse
  o metrik için karşılaştırma unavailable kalır; uygun başka bağımsız ölçüm
  ancak kendi kaynak ve koşul eşleşmesiyle kullanılabilir.
- IN718 için ayrı geometri adayı, NIST AMB2022-03 optik mikroskopi tek iz W/D
  sonuçlarıdır ([resmî ölçüm tanımı](https://www.nist.gov/document/amb2022-03-measurement-and-challenge-descriptions-version-101),
  [resmî sonuçlar](https://www.nist.gov/document/am-bench-amb2022-03-measurement-and-result-descriptions-v10),
  veri DOI `10.18434/mds2-2718`). Bunlar çıplak levhada ölçülmüştür;
  mevcut `meltPoolLiteratureCases.ts` kaydındaki 40 µm katman ve 110 µm hatch
  değerleri deneyin ölçülmüş koşulu olarak kullanılamaz. Karşılaştırma operatörü
  yüzey referansı, en büyük kesit W/D, tekrar grubu ve ışın çapı tanımıyla
  önceden dondurulmalıdır.
- GPU işi eski Warp prototipini otomatik eşdeğer backend ilan etmez. İlk hedef,
  sınırlandırılmış aynı termal operatörün açık cihazlı uygulamasıdır. Eşdeğerlik
  toleransları sonuçlara bakılmadan kaydedilir; başarısız karşılaştırma saklanır.
- Yeni alaşım için kimlik/bileşim, kaynak ve proses durumu, gerekli sıcaklığa bağlı
  özellikler, geçerlilik aralığı, birimler ve desteklenen model ayrı kaydedilir.
  IN625 önceliklidir; kaynak/veri kapısı geçilmeden kullanıcıya hesap desteği
  açılmaz. İlk kabul termal modele özgü olabilir; build-job kararı, slicer,
  yorulma ve qualification kendi eksik özellik/veri kapıları geçilene kadar
  unavailable kalır. Mevcut IN718 varsayılanı yeni alaşıma uygulanmaz.
  [NIST AMB2018-02](https://www.nist.gov/ambench/amb2018-02-description) IN625
  çıplak levha deney kapsamını; [NIST kaynaklı bir model tablosu](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=932570)
  bazı termofizik değerleri sağlar. Bu parçalı kaynaklar tek başına tam model
  uygunluğu veya deneysel doğrulama sayılmaz.
- Yazılım doğruluğu, sayısal doğrulama ve bağımsız deneysel geçerlilik ayrı
  raporlanır. Sentetik/solver verisi holdout ölçümü olarak kullanılamaz.

## Çok ajanlı yürütme

Ana ajan ortak sözleşmelerin, `STATUS.md` ve bu planın entegrasyon sahibidir.
En fazla üç alt ajan aynı anda çalışır. Başlamadan önce her paketin dosya
sahipliği ve dar kabul kontrolü `ACTIVE_WORK.md` içine yazılır. P1/P2 Python
malzeme hattı, P3 Node kayıt/API hattı ve P4 sayısal doğrulama ayrı dosyalarda
paralel ilerleyebilir; aynı ortak şema veya dosyada eşzamanlı yazma yapılmaz.
P5 kaynak/ölçüm işi P4 sonuçlarına göre, P6 GPU işi termal sözleşme sabitlenince,
P8 UI işi backend sözleşmesi hazır olunca açılır. Her paketin diff'i ve ilgili
kontrolü gözden geçirilir; yerel commit sonrası entegrasyon kapısı tekrar çalışır.
Kullanıcıya ara karar gerektirmeyen işlerde durulmaz. Bağlam değişiminde bu plan,
`STATUS.md`, Git durumu ve en son commit yeni görevin devam noktasıdır.

EIS/EDS ve diğer yan araştırma modülleri kapsam dışıdır. Push, yayın veya
canlı veri göçü bu planın bitiş koşulu değildir.

## 2026-09-24 — P6/P8 ve çekirdek fizik devamı

P6'nın bağımsız analitik ısı alt-kapısı artık Phase 22 üretim entalpi kernel'ine
uygulanan 3B Fourier modu ve tam-alan enerji oracle'ıyla sınanıyor; rapor
`docs/PHASE22_MANUFACTURED_THERMAL_2026-09-24.md`. Bu sabit-özellikli iletim
kontrolü, önceki enerji defteri/CPU paritesi kontrollerinden ayrıdır ve tam
P6'yı veya P4/P5'i kapatmaz. CPU/GPU taramasında yeni, yüksek güvenli başka bir
kusur bulunmadı; OpenFOAM IN718 ve yüksek-sıcaklık akış/arayüz sınırlamaları
ayrıca kalır.

P8 için en güncel kayıtlı canlı UI kanıtı `PROOF.md` içindeki 2026-09-24
“Core physics + IN625 UI/archive integration” bölümüdür: yerel türetilmiş IN625
screening kaynak revizyonu 2 önizlendi/içe alındı/bayt doğrulandı; aynı
konfigürasyon CPU ve açık RTX 4060 `cuda:0` üzerinde hesaplandı ve arayüzde
karşılaştırıldı; CUDA koşusu tam kaynak revizyonuyla arşivlendi; bundle
doğrulandı ve ayrı kopyaya geri yüklendi, canlı arşiv değişmedi. Bu, temel
seç→hesapla→CPU/CUDA karşılaştır→dışa aktar→geri yükle yazılım akışını destekler.
Arşivlenmiş IN625 koşusunun core contract'ı `legacy-unbound`, modeli
`unvalidated-literature-model-screening`; NIST kıyası `unavailable` kaldı.
Önceki IN718 analitik-screening P8 kaydı geçmiş kanıttır, en güncel kabul kanıtı
değildir. P8 yazılım akışı için kayıtlı kabul sürer; bilimsel kıyas ve P5 model
geçerliliği açık kalır.

## 2026-09-24 — P1 kimliği, P7 IN625 oracle'ı, P10 buharlaşma kapanışı

P1 bileşik `buildJobIdentity` artık kanonik alaşımı, model kimliğini, solver
revizyonunu, özellik snapshot şema/revizyonunu ve ayrı özellik SHA-256'sını
bağlıyor. Başarılı sonuçta üretiliyor, cache anahtarına katılıyor ve cache hit
sırasında doğrulanıyor. TypeScript oturumu eksik/tutarsız kimlikli başarılı
sonucu reddediyor. Alias eşitliği ile model/revizyon/şema değişimleri odaklı
testlerle kapsanıyor.

P7 IN625 sınırlı füzyon-entalpi uygulaması için H(T), gizli ısı katkısı,
süreklilik, monotonluk ve dH/dT değerlerini bağımsız Gauss-Legendre Cp
integrasyonuyla denetleyen oracle eklendi. Bu yalnız sayısal uygulama tutarlılığı
kanıtıdır; JMatPro/literatür modeli deneysel olarak doğrulanmamıştır, kaynak
geçerlilik aralığı bilinmiyor ve build-job/tam transient kabulü kapalıdır.

P10 incelemesi, OpenFOAM'ın VOF/süreklilik kütle aktarımı olmadan buharlaşma
enerji kaybı ve geri tepme/plume kuvveti uyguladığını buldu. Üretilen çok-fizikli
vakalar ve örtük C++ model varsayılanı artık bu terimleri kapatıyor; açık recoil
formül fikstürü yalnızca formül kanıtı olarak açık kalıyor. Tanı çıktısı
buharlaşma kütle aktarımı kapanışının olmadığını ve modelin nitelenmediğini
belirtiyor. Bu güvenli bir yetenek sınırıdır; tam evaporatif VOF düzeltmesi
değildir. OpenFOAM derleme/yürütme doğrulanmadı.

Kullanıcı P6/P7'yi en az bir yeni alaşım için GPU termal yolu ve her alaşımda
aynı yasa ile CPU/GPU yeterliliği gerektirecek şekilde genişletti. IN625 GPU
adaptörünün uygulanabilirliği denetleniyor. P4/P5/P6 açık; bu yazılım ve sayısal
kontrollerden bilimsel kabul sonucu çıkarılmıyor.

## 2026-09-24 — IN625 sınırlı bare-plate CPU/CUDA yolu

P7 için IN625'in kaynaklı JMatPro-tabanlı sınırlı Cp/k/H yasasıyla ayrı bir
bare-substrate 3D iletim taraması eklendi. CPU NumPy ve açık RTX 4060 `cuda:0`
alanları küçük sabit 576 hücre/4 adımlı vakada aynı çıktı; bağımsız Cp integrali,
enerji defteri, entalpi üst sınırı ve ortak kaynak-yakalama kapısı denetlendi.
Model revizyonu `f47b07e4...4466f07`; durum `unvalidated-literature-model-screening`.
Bu yalnızca model-specific numerical screening kapısını açar. NIST AMB2018-02
çıplak IN625 plaka geometrisini destekler fakat bu test AMB verisiyle
karşılaştırılmadı; powder-bed, genel transient ve deneysel kabul açık kalır.

P6 bu yolla kısmi ilerledi, tamamlanmadı: kaynak alanı ve CPU/CUDA eşleşmesi
yalnız küçük sentetik vakada var; ölçek/bellek-hız çalışması, bağımsız NIST
ölçüm karşılaştırması ve uygulama UI/kalıcı kayıt akışı açık.

## 2026-09-24 — IN625 mushy-range GPU witness

The bounded IN625 CPU/CUDA field route was extended with one synthetic
phase-range case at an artificial 1500 K initial state. In 8×8×2 cells and 33
steps, both CPU and explicit RTX 4060 `cuda:0` reached 1565.4608746 K and four
mushy cells; maximum temperature and enthalpy differences were 4.55e-13 K and
2.33e-10 J/kg. A 64-point independent Cp integral and whole-domain energy
balance passed; the maximum ledger residual was 5.33e-15 J. The focused suite
passes 11/11. A 16×16×4 refinement keeps the same 2×2×0.5 mm domain, 3.3 ms
duration, 0.099 J source and boundary conditions; both backends reach 1577.34 K
with 32 mushy cells. CPU/CUDA differences remain below 9.10e-13 K and
3.50e-10 J/kg, with ledger residual `5.33e-15 J`. Single-run CUDA/CPU times
are 9.196/0.289 s at 128 cells and 23.254/1.316 s at 1,024 cells; CUDA is
slower at both sizes. This closes only field-level exercise of the current
screening constitutive law; it does not change IN625's `unvalidated` status or
source gate. P6/P7 remain partial; frozen P4 stays `failed`, P5 stays
`unavailable`. Details: `docs/IN625_MUSHY_CPU_CUDA_SCREENING_2026-09-24.md`.

Independent acceptance audit: frozen P4 remains failed under its frozen
actual-spacing criteria; the separate 75 W continuous-contour assessment is
inconclusive. P5 remains unavailable because Case 0 exits at the model's
boiling-validity guard before a usable field/section result. The same
enthalpy-FV model must not be rerun or have its guard removed; a new
source-bounded model needs consistent free-surface mass transfer, latent-energy
loss and force/energy controls first. P6 now covers the IN625 mushy-range field
on CPU/CUDA for one synthetic test vector, but that alloy remains unqualified
and CUDA is slower on the 128-cell profile. P7 source review found no complete
alternate source package; Hastelloy X is a candidate for further data capture,
not an admitted alloy. Preserve these statuses until new evidence is produced.

## 2026-09-24 — Phase 22 molten-surface evaporation gate

The enthalpy kernel and energy ledger could apply evaporation above the
1500 K saturation cutoff even when the surface-kinematics kernel kept the
surface fixed below `T_solidus`. An 1850 K regression against the default
1878 K solidus reproduced the unpaired enthalpy sink. One shared
liquid-surface flux helper now gates enthalpy loss, ledger loss, and surface
recession at the solidus; existing above-solidus area and mass matching still
passes. The Phase 22 Python suite passes 30/30 on CPU Warp. This repair closes
only an internal model-contract inconsistency, not the missing experimental
validation or P4/P5/P6/P7 gates.

## 2026-09-24 — Phase 22 explicit momentum timestep bound

The selected time step previously satisfied a thermal diffusion limit only,
although momentum advection and viscous diffusion are explicit updates. It now
also satisfies a conservative joint momentum rate bound based on the 5 m/s
per-component clamp and `nu=mu/rho`, while preserving the thermal limit and
exact requested end time. The new synthetic low-alpha test makes the momentum
bound active. The full Phase 22 suite passes 31/31 on CPU Warp. This repair
covers explicit-update stability under configured limits; physical
qualification remains open.

## 2026-09-24 — Hastelloy X alternate-alloy gate

The evaluated sources do not pass the full melting-range data gate. Scheel et
al. provides useful as-deposited LPBF Cp/enthalpy, but its liquid conductivity
is modeled with a 15× factor, density is a fixed room-temperature measurement,
and the complete uncertainty-bounded property set is absent. NASA AM records
and NIMS liquid-density metadata do not close or match the missing properties.
No runtime alloy admission follows. Keep any bounded pilot source-labelled,
with unmeasured liquid inputs explicit as assumptions. See
docs/HASTELLOY_X_P7_SOURCE_HUNT_2026-09-24.md.

P4 remains failed, P5 unavailable, and P6 partial. Next work remains physically
closed model development and larger same-physics GPU performance/crossover
analysis; CPU/CUDA agreement does not establish process validity.

## 2026-09-24 — Projected CFL and height-graph floor validity guards

Phase 22 now checks the actual post-projection velocity field against the
explicit momentum and enthalpy-transport stability bound before applying
thermal fluxes. A violation stops with a validity error. If molten-surface
evaporation would drive the interface into the height graph's lower domain
floor, the solver likewise stops before updating enthalpy or the energy
ledger. The synthetic regressions and full Phase 22 CPU Warp suite pass 33/33;
no GPU run was part of this package. This closes two numerical/model-boundary
gaps without qualifying the free-surface model or changing P5's unavailable
status.

NIMS experiment 264 is a separate molten-density lead. Public metadata lacks
the sample-specific chemistry, numerical values/uncertainty, and surface-
tension/viscosity fits needed to combine it with Scheel data. Detailed source
limits: docs/HASTELLOY_X_P7_SOURCE_HUNT_2026-09-24.md.

## 2026-09-24 — IN625 repeated CPU/CUDA timing

After the bounded CUDA inversion-check reduction, one warm-up and five
alternating repeats produced median CUDA/CPU ratios of 24.6× slower at 128
cells and 14.1× slower at 1,024 cells. Temperature-field differences remained
below 9.1e-13 K, and the focused field suite passed 12/12. Direct solver timings
exclude UI/API transport and are not a paired before/after campaign, so no
speedup or crossover is claimed. Full ranges and method:
docs/IN625_CUDA_BENCHMARK_2026-09-24.md.

P6/P7 remain partial. Next step is to profile a larger same-physics workload
before considering fused GPU kernels; this screening alloy remains unqualified.

## 2026-09-24 — Larger IN625 same-domain GPU screen

A z-refined, 2,048-cell case kept the same domain, process source, integrated
energy and simulated duration. The warm three-repeat medians were 4.013 s CPU
and 43.617 s CUDA, so the GPU remained 10.87× slower. Both backend outputs
passed the independent enthalpy and energy oracles, with matching 44 mushy
cells and maximum temperature/enthalpy differences below 9.10e-13 K and
4.66e-10 J/kg. This is larger same-law numerical evidence, not spatial
convergence, process validation, alloy qualification, or a CUDA crossover.
Full timings are in docs/IN625_CUDA_BENCHMARK_2026-09-24.md.

Next: profile backend launch and arithmetic costs before deciding on fused
kernels; maintain P6/P7 as partial.

## 2026-09-24 — Frozen 80 W peak-selection forensic replay

The archived P4 report does not retain the historical full thermal history or
field series. Six isolated runs at diagnostic commit `5dae4c9` used the exact
frozen input hashes and reproduced every saved aggregate (actual mesh/time,
step count, W/D, peak temperature and energy error) with zero delta. All six
`implementationHash` values differ, including when fingerprinted at the
report's `ec6b0a5` commit; a Git-blob scan across 69 commits from the P4 harness
through the new capture gate found no matching tree. The exact run likely used
a dirty/uncommitted or unrecorded Python tree. This is a matched-input forensic
replay, not exact-code reproduction.

The replay shows broad equal-maximum plateaus on coarse mesh levels (439 and
300 accepted endpoints, versus 25 at the fine mesh). Timestep levels select
the same W/D and sample an approximately 2.2 µs plateau with 6/12/25 tied
endpoints. This is a possible discrete peak-selection sensitivity, not a proven
cause of the non-monotonic depth sequence. See
`docs/LPBF_P4_PEAK_DIAGNOSTIC_REPLAY_2026-09-24.md`. Frozen P4 remains `failed`;
the current 99% source-capture validity guard and all acceptance limits remain
unchanged. The diagnostic supports a same-operator peak-selection sensitivity
review but cannot revise acceptance. Preserve the missing source-tree identity
as a provenance limitation; any new numerical study must freeze its vector,
model/operator and existing acceptance rules before the next run.

## 2026-09-24 — Phase 22 guard CUDA execution

The lower-domain evaporation stop and projected post-pressure CFL tests execute
on CPU and explicit RTX 4060 Laptop GPU. The focused two-test run passed with
four CPU/CUDA subtests. This confirms compilation/execution of the new guard
path on the selected device, not experimental validity of the Phase 22 model.
