# Watcher clean-acceptance kararı — ec3a5fc

## Hard karar

**Fixture lifecycle / kabul harness environment düzeltmesi seçildi; üretim ignore sözleşmesi değişmeyecek. En küçük üretim/test code change: sıfır.** Mevcut kanıt gerçek kullanıcı root'unda kaynak izleme kusuru veya yetersiz timeout göstermiyor. Test fixture'ı özel harness TEMP/TMP'si üzerinden bilerek ignore edilen `.tmp-lpbf...` ağacına yerleştirilmiş.

`tests/vite-watch.test.ts:10` root'u `mkdtemp(path.join(tmpdir(), 'metalliksa-vite-watch-'))` ile kuruyor. `vite.config.ts:25-31` ignored listesi absolute path'teki generated dizinleri dışarıda bırakıyor. Native TEMP/TMP bu nedenle fixture/src'i de kapsamış. Testteki5s readiness sınırını artırmak, testi skip etmek veya ignored listesini kaldırmak gerekçesizdir.

## Kontrollü mevcut RED/GREEN kanıtı

Root'un `watch-temp-probe.json` kaydı aynı ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce /1579 dosya/Node+tsx+tek test komutunu karşılaştırıyor; **tek environment farkı TEMP/TMP root'ları**, sourceHashesBeforeAndAfterMatch=true.

| Ortam | Gerçek terminal sonucu |
|---|---|
| `.tmp-lpbf-input-claims-acceptance-20261003/native-temp` ancestor | RED exit1, source watcher readiness assertion test:38, test5425.573ms |
| `C:/Users/can02/AppData/Local/Temp/metalliksa-watch-neutral-vslg9_c9` | GREEN exit0,1/1PASS, test661.968ms |

Loglar `watch-probe-ignored-ancestor.log` / `watch-probe-neutral.log`; SHA kayıtları sırasıyla `1c2c45dae4bbb69d5dc4eeb449312eb9f06f9fbab7f576dcc67c9f9f29bc2abe` / `38cfd6c36a73e997e8cf1c2a0efd12bbc27bd0f8dcb43f6d68e9e826b7e67f7c`.

GREEN yalnız watcher startup değil: aynı test gerçek `src/probe.ts` change event'ini ve beş generated path'ten change event gelmemesini de assert ediyor (`test:40-48`). Generated graft, nested.tmp-lpbf, .lpbf-runs, .warp-cache ve docs/*.partial.json policy'si hâlâ korunuyor. Gözlenen wrapper completion ~6.8s iki case için ortak subprocess ölçümü; watcher latency karşılaştırması değildir.

**Root içindeki generated dizinlerin ignored davranışı doğrulanmalı ve mevcut GREEN bunu yapıyor. Root'un kendisinin generated/ignored ancestor altında olması için yeni ürün garantisi tanımlanmıyor.** Böyle bir supported working-root gereği ayrı bir ürün kararı olur; current V1 clean reproduction bunu gerektirmiyor. Testi source root altında yeni fixture konumuna taşımak da çalışabilir, fakat mevcut regression code'u değiştirmek bu kanıtla gerekli değil.

## En dar uygulama / yeniden kabul

Root'un başarılı native npm ci kurulumu ve1579hash manifesti korunur. Başarısız ilk full unit denemesi de silinmez veya PASS diye relabel edilmez.

İsteğe bağlı scratch resume helper yalnız şu lifecycle'i uygular:

1. Root'un güncel, izinleri doğru native context'inde nötr OS temp base altında **yeni test-owned temp directory** oluştur; adı `.tmp-lpbf*`, `.lpbf-*`, `.warp-cache*` veya graft ancestor taşımamalı. Varsayılan nötr root'un path'i A/B kaydındaki host temp base ile doğrulandı.
2. Child environment mevcut desteklenen environment'ın kopyası olsun; **yalnız TEMP ve TMP** bu yeni absolute path olsun. METALLIX_PYTHON locked3.12, PYTHONDONTWRITEBYTECODE=1 ve mevcut script/network/npm politikası korunur. Global/user/machine environment veya npmrc değişmez; DISABLE_HMR behavior'a dokunulmaz.
3. Aynı `.runtime/v1-input-claims-native-20261003` kaynak snapshot'ında fresh before-guard1579commit eşliği; ardından aynı resmi Node/npmCLI ile lint → fullunit → build, her exit code ayrı. Fullunit fail olursa build'e geçilmez. After-guard her durumda çalışır; her log/exit/runtime/temp path fresh record'a bağlanır.
4. Aynı testin generated-path exclusion asserts'i ve full suite sonucu birlikte değerlendirilir. İlk failed native suite ile nötr temp'teki fresh accepted sequence ayrı tutulur. Başarılı locked install kaydı yeniden kullanılabilir; npm install veya bağımlılık politikası değişikliği gerekmez. Kaynak değişmediği guard ile gösterilmeden test geçişi kabul edilmez.
5. Fixture cleanup mevcut testin guard'larıyla yalnız kendi mkdtemp dizinini kaldırır (`test:49-56`); helper native snapshot/başarısız partial/cache/output root'larını recursively temizlemez. Nötr üst temp directory veya koşu çıktılarının saklanması root lifecycle sahibine aittir.

Gemini Flash rolü bu küçük scratch resume helper'ın bağımsız review/implementation önerisi olabilir; modeli kullanmak için yapay ürün patch'i gerekmiyor. Bu ajan herhangi bir deney/test/process/network/browser çalıştırmadı; yalnız bu scratch tasarımı yazdı. Luna'nın kaynak keşfi tekrarlanmadı; gerekli test/config spanları ve Root'un controlled probe logları okundu.
