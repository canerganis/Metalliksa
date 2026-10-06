# Metalliksa — Bilimsel Araştırma Vizyonu

**Durum:** Araştırma yönü önerisi; onaylanmış ürün yol haritası veya doğrulanmış bilimsel sonuç değildir.  
**Bağlam:** Metalliksa'nın LPBF fiziği, deney izlenebilirliği ve kanıt sınırlarını koruma hedefleri üzerine beyin fırtınası.

## Ana fikir

Metalliksa'yı, yalnızca proses sonucu hesaplayan bir araç olarak değil, fiziksel modellerin nerede ve neden yanıldığını araştıran ve bu açıklamaları ayırt etmek için hangi ölçümün en değerli olacağını öneren bir araştırma ortamı olarak geliştirmek.

“Çığır açıcı” veya “ilk” olma iddiası burada peşinen kurulmaz. Bu fikirler literatür taraması, uygulanabilir veri kapsamı ve bağımsız deney karşılaştırmasıyla sınanması gereken aday araştırma yönleridir.

## Araştırma yönleri

### 1. Rakip fizik hipotezlerini ayıran deney tasarımı

Eriyik havuzu tahminindeki farkı absorptivite, ısı taşınımı, ışın profili veya ölçüm belirsizliği gibi rakip açıklamalara bağla. Mevcut kanıtın hangi açıklamaları ayırt edemediğini göster; ayrımı en çok iyileştirecek proses koşulunu ve ölçümü öner.

**Araştırma sorusu:** Aynı verilere uyan fizik modellerini hangi ilave gözlem en az deney maliyetiyle birbirinden ayırır?

### 2. Hata örüntülerinden eksik fizik keşfi

Tahmin-deney farklarını proses rejimi ve gözlem türüne göre grupla. Boyutsuz değişkenler, sembolik regresyon ve belirsizlik hesabı ile açıklanabilir düzeltme bağıntıları üret. Önerileri yeni fizik yasası olarak sunma; geçerlilik aralığını ve bağımsız verideki başarısını raporla.

**Araştırma sorusu:** Farklı deneylerde tekrarlayan sistematik hata hangi eksik mekanizmaya veya girdiye işaret ediyor?

### 3. Mikroyapı hedefinden proses yoluna ters tasarım

Parça bölgelerine ait mikroyapı veya özellik hedeflerinden tarama yolu ve proses penceresi adaylarına geriye doğru ilerle. Ulaşılamayan hedefleri ve bunlara neden olan fiziksel ya da makine sınırlarını da açıkla. İlk kapsam tek alaşım ve tek ölçülebilir mikroyapı hedefi olmalı.

### 4. Makine ve toz partileri arasında bilgi aktarımı

Bir makine veya toz partisinde öğrenilen ilişkinin yeni koşullara ne ölçüde taşınabildiğini belirle. Yeni koşulda yeniden ölçülmesi gereken nicelikleri ve bunlar için en küçük kalibrasyon setini öner. Başarıyı dışarıda tutulmuş makine, laboratuvar veya parti verisinde ölç.

### 5. Literatür uyuşmazlığından ölçüm önerisi

Yayımlanmış sonuçlar arasındaki farkları ölçüm tanımı, koşul ve raporlama eksikleri açısından karşılaştır. Metadata'nın açıklayamadığı uyuşmazlıklar için olası açıklamaları ve bunları sınayacak eksik ölçümleri üret. Korelasyonu nedensel açıklama olarak sunma.

## Önerilen ilk çalışma

İlk prototip için 1 ve 2 numaralı yönleri birleştir:

> **IN718'de eriyik havuzu genişliği, derinliği ve soğuma verisini birlikte kullanmak, absorptivite belirsizliği ile model biçimi hatasını ayırmayı ne ölçüde iyileştirir?**

Önce sentetik ve kontrollü vakalarda ayırt edilebilirliği ölç; sonra kamuya açık deney verisinde sınayıp yayın veya deney serisi bazında kalibrasyon ve değerlendirme verilerini ayır. Sonuçları tahmin hatası, belirsizlik aralıklarının ölçüm kapsamı ve aynı doğruluğa ulaşmak için gereken ölçüm sayısıyla değerlendir. Verinin hangi fiziksel nicelikleri gerçekten gözlemlediğini ayrıca kaydet.

Bu kapsam, araştırma planında belirtilen fiziksel makineye erişim olmadan açık veriyle başlayabilir. Sentetik vaka yazılımın ve yönteminin sınamasıdır; deneysel doğrulama değildir.

## Ön literatür dayanakları

- Belirsizlik azaltma ve deney verisiyle kalibrasyon: [Uncertainty quantification and reduction in metal additive manufacturing, *npj Computational Materials* (2020)](https://www.nature.com/articles/s41524-020-00444-x).
- Belirsizlik odaklı PBF-LB parametre uzayı deney tasarımı: [Autonomous exploration of the PBF-LB parameter space (2025)](https://doi.org/10.1016/j.addma.2025.104677).
- Sembolik ve fizik bilgili makine öğrenmesi kıyaslaması: [ESAFORM Benchmark 2025, *International Journal of Material Forming* (2026)](https://link.springer.com/article/10.1007/s12289-026-01995-y).
- Mikroyapı kontrolü için tarama yolu tasarımı: [Reduced-order phase-field ve reinforcement learning yaklaşımı (2025 ön baskı)](https://arxiv.org/abs/2506.21815).
- Kontrollü ve yayımlanmış metal AM ölçümleri: [NIST AM-Bench ölçüm ve problem kataloğu](https://www.nist.gov/ambench/am-bench-data-and-challenge-problems-0).

Bu kaynaklar araştırma motivasyonu sağlar; önerilerin özgünlüğünü veya Metalliksa sonuçlarının bilimsel geçerliliğini tek başlarına kanıtlamaz. Yeni çalışma başlamadan önce yenilik ve benzer iş taraması yenilenmelidir.
