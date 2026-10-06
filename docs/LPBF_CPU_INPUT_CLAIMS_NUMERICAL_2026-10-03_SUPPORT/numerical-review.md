# Bağımsız CPU input-claims kanıt incelemesi — 2026-10-03

Salt okunur kontrol; yeni test, solver, browser veya kaynak değişikliği yapılmadı. Graft ilk sorguda ilgili manufactured test ve timestep tanılama düğümlerini buldu, fakat güncel scratch logları/manifesti kapsamadı. Bu üretilmiş kanıtlar indekslenmediğinden exact `.runtime/v1-input-claims-20261003` snapshot kaynaklarına ve belirtilen scratch kayıtlarına geçtim.

## Kimlik ve kaynak koruması

- `source-manifest.json`: aday revizyon `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce`, 1.579 dosya, manifest SHA-256 `4573e2295d8d9721700c177adf39826f9a956c24cee3b524a9ce3b8eb3a6c1a2`.
- Kilitli Python ile salt okunur bağımsız yeniden hesaplama: **1.579/1.579 dosya eşleşti; eksik, ekstra veya hash uyuşmazlığı yok**. Ayrıca commit arşivinden (`git archive` ile aynı revizyon blob'ları) **1.579/1.579 SHA-256 eşleşti**. Manifest revizyonu snapshot commit HEAD ile aynı.
- CPU öncesi, CPU sonrası ve diagnostics sonrası kayıtlarının her biri 1.579 dosyada sıfır mismatch gösteriyor. Üretim implementation fingerprint öncesi/sonrası aynı: `4cf24334a711ecf6fd41597cb087726580c0ed85b52ece72e0f15b89f6802e35`.
- CPU/numerical log hashleri `cpu-commands.json` kayıtlarıyla eşleşti; diagnostics JSON hash'i logdaki SHA ile eşleşti.
- `run_cpu_acceptance.py`, önceki harness'ten sadece üç tekil path/revision değiştirme kuralı uyguluyor. Eski harness ile türetilen `numerical_diagnostics.py` üzerinde byte karşılaştırması tam eşleşti: eski snapshot path'i, revision string'i ve manifest path'i; her biri kaynakta bir kez. Diff toplam altı satır: 3 çıkarma + 3 ekleme.

## Test kapsamı ve sayım

- `cpu-suite.log`: **27 test, PASS, 0 failure/error/skip, 22.988 s**. İlk dört satırdaki manufactured test, aynı 27 testin alt kümesidir; benzersiz toplam **27**'dir, 31 değildir.
- `numerical-diagnostics.log` ve JSON: yalnızca o mevcut dört manufactured testi tekrar çalıştırıyor; **4/4 PASS, 13.047 s**. Bu, 27'ye ek ayrı benzersiz vaka sayımı değildir. Test fonksiyonlarının kendisi değiştirilmeden, `sys.settrace` yalnızca dört test-method frame'ini gözlüyor; üretim operatör frame'leri izlenmiyor. Diagnostics modu açıkça `diagnosticOnly=true`, `experimentalValidation=false`, solver `unvalidated`, fiziksel LPBF yakınsaması `inconclusive`.

Dört kaynak testin gerçek kabul sınırları:

1. Nonuniform enthalpy ramp: pasif iletim operatörü bağımsız yüz-akı oraklıyla her gerçekleşmiş adımda `rtol=2e-12`, `atol=1e-7 W/m³`; final zaman 14 basamak, tepe/merkez sıcaklık mutlak hatası `≤1e-7 K`; enerji-bilanço bağıl hatası `≤1e-10`. Gerçek adım sayıları 23/38/75.
2. Piecewise enthalpy ramp: analitik `H(T)`/faz kesri örneklerinde inceltmeyle hata oranı `coarse/4`'ten küçük; eşik entalpisi mutlak toleransı `1e-6 J/kg`, eşik sıçraması toleransı `1e-3 J/kg`; enerji bağıl hatası `≤1e-10`. Gerçek adımlar 34/42/75. Bu, belirlenmiş analitik entalpi yasasının inversion kontrolüdür.
3. Uniform enthalpy ramp: final zaman 14 basamak, tepe/merkez sıcaklık hatası `≤1e-7 K`, enerji bağıl hatası `≤1e-10`; üç seviyede adım sayıları farklı olmalı. Gerçek adımlar 23/38/75.
4. Mixed-boundary diffusion: kaynak testi sabit 160 µm derinlikli, x/y'de sabit manufactured alanı üretim CPU transient döngüsünden geçiriyor; `dx` ile `dt_max` beraber (`dt_max ∝ dx²`) inceltiliyor. Z seviyeleri 8/16/32 için **gerçekleşmiş adımlar 47/187/747**; alan RMS hata değerleri **5.65596e-4, 1.42081e-4, 3.55630e-5 K** ve gözlenen toplam mertebe **1.99306, 1.99827**. Testin kaynak eşiği yalnızca hataların pozitif ve monoton azalması ve iki gözlenen mertebenin `>1` olmasıdır; oran yaklaşık 2 olduğundan rapor bunu yaklaşık ikinci mertebe davranış olarak gösterebilir.

Bu diffusion sonucu eşzamanlı uzay-zaman inceltmesinde sentetik sınır koşullu/manufactured transient hata davranışıdır. Ayrı bir fiziksel LPBF mesh yakınsama testi, zaman hatasından bağımsızlaştırılmış saf uzaysal mertebe kanıtı veya deneysel doğrulama değildir. Report edilen accepted step/distribution değerleri sonuç nesnelerindeki fiilen gerçekleşen adımlardan alınır; istenen `maxDt` değerleriyle karıştırılmamalıdır.

## Kalan kabul sınırları

`clean-run-summary.json` offline `npm ci` denemesinin `ENOTCACHED` nedeniyle başarısız olduğunu; lint, frontend unit ve build'in bu clean-candidate aşamasında çalışmadığını kaydediyor. Bu CPU bilimsel-input kanıtı başarılı ve hash-guarded olsa da genel V1/release kabulünü tamamlamaz. Gerçek tarayıcı/klavye kabulü bu incelemede yapılmadı.

İnceleme sırasında hiçbir test tekrar koşturulmadı; yalnızca manifest/hash doğrulaması, commit blob karşılaştırması, log/JSON hash karşılaştırması ve mevcut kaynak/raporların okunması yapıldı.
