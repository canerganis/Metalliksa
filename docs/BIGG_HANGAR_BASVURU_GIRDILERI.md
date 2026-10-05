# BIGG HANGAR Başvuru Ön Çalışması — Metalliksa

> **Durum:** İç çalışma taslağı; başvuruya hazır değildir. Ürün anlatımı 2026-09-27 itibarıyla uygulama belgeleriyle hizalanmıştır. Problem, müşteri, pazar, ödeme isteği ve program koşulları doğrulanmalıdır.  
> **Ürün kapsamı için kaynak:** [Metalliksa Ürün Özeti](PRODUCT_OVERVIEW.md).

## 1. İş fikrinin kısa adı

**Metalliksa — LPBF araştırma ve proses geliştirme için izlenebilir mühendislik platformu**

## 2. Tek cümlelik tanım

Metalliksa, metal eklemeli imalat araştırmacıları ve mühendislerinin LPBF analizlerini, malzeme bilgisini ve kaynaklı kanıt kayıtlarını tek bir çalışma ortamında ilişkilendirerek teknik incelemelerini daha izlenebilir yürütmesine yardımcı olan bir araştırma mühendisliği platformudur.

## 3. Çözülmesi hedeflenen problem

**Problem hipotezi:** LPBF proses geliştirme sırasında proses girdileri, model çıktıları, literatür bulguları ve deney kayıtları farklı araçlarda tutulabiliyor. Bir sonucun hangi girdi, kaynak, varsayım ve doğrulama durumuna dayandığını yeniden kurmak bu nedenle zorlaşabilir.

Bu henüz müşteri görüşmeleriyle doğrulanmış bir bulgu değildir. Başvuruya sayısal zaman, maliyet, hurda veya deney azalması iddiaları eklenmeden önce kullanıcı ve pilot verisi gereklidir.

## 4. Mevcut çözüm

Metalliksa, bugün çalışan araştırma mühendisliği prototipi içinde üç bağlantılı çalışma alanı sunar:

- **LPBF Engineering:** malzeme/proses girdileriyle kullanılabilir termal ve analitik tarama iş akışları;
- **Materials & Characterization:** malzeme verisi ve malzeme araştırma araçları;
- **Evidence & Records:** araştırma kaynakları, incelenmiş bulgular, ölçüm kayıtları ve mühendislik sonuçları için izlenebilir inceleme akışı.

Research Hub kaynak ve bulguları modüllerle ilişkilendirebilir; bu kayıtlar çözücü girdilerini kendiliğinden değiştirmez. Amaç, analizi ve dayanaklarını birlikte inceleyebilmektir.

## 5. Farklılaşma hipotezi

Sınanacak ürün varsayımı, hesaplamalı analiz ile kaynak/kanıt izini aynı iş akışında tutmanın araştırma ekiplerine değer sağlayacağıdır. Metalliksa ölçülmüş bulguları, literatür tahminlerini, model sonuçlarını ve yazılım doğrulamalarını ayrı tutmayı hedefler.

Bu aşamada rakiplere göre üstünlük, pazarda benzersizlik veya doğrulanmış maliyet tasarrufu iddiası kurulmamıştır. Rakip ve alternatif iş akışı araştırması başvuru öncesi tamamlanmalıdır.

## 6. Hedef kullanıcı ve müşteri varsayımları

### Kullanıcı hipotezleri

- LPBF proses geliştiren malzeme ve üretim mühendisleri;
- eklemeli imalat araştırmacıları ve üniversite/kurum Ar-Ge ekipleri;
- simülasyon, literatür ve deney kayıtlarını birlikte değerlendiren teknik ekipler.

### Olası alıcılar — doğrulanacak

Kurumsal Ar-Ge ekipleri, LPBF hizmet sağlayıcıları, makine üreticileri ve malzeme tedarikçileri olası segmentlerdir. İlk müşteri ve ödeme yapan rol henüz seçilmiş/doğrulanmış değildir.

## 7. Mevcut teknik durum ve kanıt sınırı

Metalliksa bir araştırma prototipidir. LPBF geçici termal çözücüsü araştırma kapsamındadır; serbest yüzeyli, buharlaşma/recoil ve eriyik akışı fiziklerini çözen yüksek doğruluklu CFD yeteneği mevcut değildir. Uygun bağımsız deney karşılaştırması ve yakınsama kanıtı olmayan model çıktıları doğrulanmış tahmin olarak sunulamaz.

Yazılım testleri, CPU/GPU sayısal paritesi veya arşivlenmiş çalıştırma kayıtları yazılım/nümerik kanıttır; tek başlarına fiziksel doğrulama, üretim yeterliliği ya da standart sertifikası sağlamaz. Modüllerin olgunluk ve kanıt durumları farklıdır; [LPBF kapsamı](LPBF_ENGINEERING.md), [güncel durum](../STATUS.md) ve [kanıt kayıtları](../PROOF.md) başvuru metniyle birlikte kontrol edilmelidir.

Bu yüzden aşağıdaki iddialar mevcut ürün başarısı gibi yazılmamalıdır: kusuru güvenilir biçimde önceden tahmin etme, proses penceresini kalifiye etme, hurdayı azaltma, fiziksel deneme sayısını düşürme veya üretim serbest bırakma kararı verme. Bunlar ancak tanımlı bir müşteri senaryosunda ölçülüp doğrulanırsa sonuç olarak raporlanabilir.

## 8. İlk pilot/PoC hipotezi

Bir pilot ortağıyla tek bir alaşım, makine/proses ailesi ve ölçülebilir gözlem seçilmesi önerilir. Pilot başlamadan önce girdiler, veri sahipliği, ölçüm yöntemi, belirsizlik, karşılaştırma metriği ve kabul eşiği üzerinde anlaşılmalıdır.

Olası değerlendirme ölçütleri — müşteriyle belirlenecek:

- aynı girdilerle çalıştırma ve sonuç kimliğinin yeniden üretilebilirliği;
- her sonucun girdi, kaynak ve kanıt durumunun izlenebilmesi;
- model/analiz çıktısının bağımsız ölçümle önceden belirlenmiş metrikte karşılaştırılması;
- kullanıcıların iş akışını tamamlayıp raporu teknik incelemede kullanabilmesi.

Ölçüm verisi ve kabul kriterleri sağlanmadan pilot başarısı veya doğruluk oranı varsayılmamalıdır.

## 9. Ticarileştirme varsayımları

İlk olarak ücretli pilot/PoC, sonrasında kurumsal yazılım lisansı araştırılabilir. Bu iş modeli ve fiyatlandırma doğrulanmamıştır. Ücretlendirme biçimi, kurulum/yerel çalışma gereksinimi, veri güvenliği ve kurum içi satın alma süreci müşteri görüşmeleriyle netleştirilmelidir.

## 10. BIGG HANGAR programından beklenen katkı

- İlk kullanıcı ve müşteri segmentine erişim, problem görüşmelerinin yürütülmesi;
- veri ve ölçüm erişimi olan bir pilot/PoC ortağı bulma;
- teknik başarı kriterleri ve bağımsız doğrulama tasarımına mentorluk;
- fikrî haklar, rakip araştırması, kurumsal satın alma ve pazara giriş konularında destek.

Program adı, güncel çağrı şartları, uygun gider kalemleri ve başvuru takvimi resmî çağrı dokümanından ayrıca doğrulanmalıdır.

## 11. İlk 13 haftada hedeflenecek işler

1. En az üç potansiyel kullanıcıyla problem görüşmesi yapmak ve görüşme notlarını kanıt olarak saklamak.
2. En acil kullanıcı problemi, kullanıcı rolü ve olası ödeme yapan kurumu ayırmak.
3. Paylaşılabilir deney verisi, veri kullanım hakkı ve teknik pilot ortağını netleştirmek.
4. Tek alaşım/proses/ölçüm kapsamlı PoC protokolünü ve kabul ölçütlerini yazmak.
5. Rakip ve mevcut alternatif iş akışlarını kaynaklı biçimde karşılaştırmak.
6. Müşteri görüşmelerine göre MVP kapsamını ve iş modeli/fiyatlandırma varsayımını güncellemek.

Bunlar program için hedeflerdir; tamamlanmış faaliyetler olarak sunulmamalıdır.

## 12. Bütçe ve kaynak ihtiyacı

Yatırım tutarı, ekip maliyetleri ve uygun harcamalar mevcut başvuru çağrısı ile gerçek tekliflere göre belirlenecektir. Doğrulanmamış sabit tutar, personel, gelir veya GPU performans rakamı eklenmemelidir.

| İhtiyaç | Kullanım amacı | Tutar/durum |
|---|---|---|
| Bağımsız ölçüm ve pilot | Numune, ölçüm, veri hazırlığı | Teklif ve pilot kapsamı beklenecek |
| Ürünleştirme | Kullanılabilir akış, raporlama ve veri güvenliği | Kapsam/maliyet çıkarılacak |
| Hesaplama altyapısı | Tanımlı pilot iş yükleri | Ölçüm ve teknik gereksinim sonrası |
| Fikrî haklar ve danışmanlık | Patent/özgür kullanım araştırması ve hukuki destek | Güncel teklif beklenecek |

## 13. 90 saniyelik sunum taslağı

LPBF proses geliştirmede bir mühendis yalnızca bir simülasyon sonucuna değil; o sonucun hangi malzeme ve proses girdileriyle üretildiğine, hangi kaynağa dayandığına ve ölçümle ne ölçüde karşılaştırıldığına da ihtiyaç duyar. Metalliksa, LPBF analizlerini, malzeme bilgisini ve kaynaklı kanıt kayıtlarını tek bir araştırma mühendisliği çalışma ortamında bir araya getiren bir prototiptir. Bugünkü hedefimiz üretim için doğrulanmış kusur tahmini vermek değil; araştırma ve proses geliştirme çalışmalarının girdilerini, sonuçlarını ve kanıt durumunu izlenebilir kılmaktır. İlk olarak bu ihtiyacın gerçek kullanıcılar için ne kadar önemli olduğunu görüşmelerle doğrulayacağız. Ardından bir pilot ortağıyla tek bir proses ve ölçüm kapsamı seçecek, bağımsız karşılaştırma yöntemini ve başarı ölçütlerini önceden belirleyeceğiz. BIGG HANGAR’den kullanıcı ve pilot erişimi, ölçüm/PoC tasarımı ve ticarileştirme mentörlüğü bekliyoruz.

## 14. Başvuru öncesi tamamlanacaklar

- Kurucu ve ekip bilgileri, görev dağılımı ve CV'ler;
- problem görüşmeleri, kullanıcı alıntıları ve izinli kayıtlar;
- ilk kullanıcı, satın alma rolü ve doğrulanmış pilot ortağı;
- pilot girdileri, ölçüm verisi, veri sahipliği/izinleri ve kabul kriterleri;
- rakip/alternatif araştırması ve kaynaklar;
- ürünün güncel demo akışı ile hangi parçaların Research/Preview olduğunu gösteren kanıt;
- fikrî haklar ve üçüncü taraf yazılım/veri lisansları;
- güncel başvuru çağrısı, bütçe şartları, yatırım tutarı ve iletişim bilgileri.

## Başvuru metnini güncelleme kuralı

Ürün kapsamı değiştiğinde önce [Metalliksa Ürün Özeti](PRODUCT_OVERVIEW.md) ve `STATUS.md` kontrol edilir. Başvuru taslağına yalnızca bu kaynaklarda desteklenen mevcut yetenekler yazılır; müşteri, pazar ve etki iddiaları ayrı kanıtla doğrulanır.
