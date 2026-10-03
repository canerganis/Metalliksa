# Native neutral sequence — bağımsız Sol denetimi

**Sonuç: kayıtlı Node lint/unit/build dizisi ve kaynak bütünlüğü PASS.** Bu denetim hiçbir test veya runner çalıştırmadı; mevcut JSON/logları okuyup hashlerini bağımsız hesapladı. Full V1 veya canlı UI kabulü sonucu değildir.

## Exact source / kayıt ayrımı

- Kaynak aday `ec3a5fcbeb1c5aa1b250ed31a4e812796c5d17ce`; gerçek cwd `.runtime/v1-input-claims-native-20261003`. Audit anındaki repo HEAD `dfd181e` bir sonraki belge kaydıdır; frozen code adayının adı değiştirilmedi. Paylaşılan checkout'ın clean olduğu iddia edilmiyor.
- `source-manifest.json`:1579 dosya, SHA-256 `4573e2295d8d9721700c177adf39826f9a956c24cee3b524a9ce3b8eb3a6c1a2`.
- Byte-identical çalıştırılan `flash_resume_reproduction.py` SHA `edbd890bd139fb33269851b82e99798eeeaa49bd640f0557f29b8bd985ae7e69`; önceki statik denetimden farklı modül değil.
- Altı stage guard'ın her birinde statusPASS/count1579/expectedCount1579, ec3 revision ve gerçek snapshot eşit. **Altı hash map'i original manifest mapping'iyle birebir; her mapte0 mismatch/0 missing.**
- Guard kayıtlarına ek olarak snapshot'taki1579 gerçek dosya tekrar hash'lendi: **1579/1579 eşit,0 mismatch**. Test/source/timeout/ignore/numerical acceptance eşikleri değiştirilmemiş; resume helper yalnız ayrı scratch/environment orchestration'ı.

## Komut/log/exit bağı

Her stage'in summary ve exclusive exitJSON command/cwd/exit/duration alanları eşit. Üç gerçek raw log SHA'sı hem summary hem exitJSON ile eşleşiyor. Commands sabit resmi Node.exe + npmCLI üzerinden runlint/run test:unit/runbuild; hepsi exit0.

| Stage | Runner elapsed | Raw log SHA-256 | Pre/post kaynak guard |
|---|---:|---|---|
| lint |21.374501s|`7a9f755a382a4ee111eda93f908328d996638dd4b13e8b1230e68c9a2f4525e2`|1579/1579,0mismatch ×2|
| test:unit |49.255396s|`f79e3ed09c944bbadae9ce2e4b5727aaecf01cd00e7acdc55652bb7416510657`|1579/1579,0mismatch ×2|
| build |128.644926s|`5b9dea5ea5c0ebde1b3061ec9dd69467a7329ec4c4dcb90457f1a08179c69c4c`|1579/1579,0mismatch ×2|

Terminal Node test summary: **372 total /371PASS /0FAIL /1SKIP /0cancelled /0todo**, test-runner duration48.558359s. Tek skip optional CMU ham payload eksikliği: STMeasurements.csv, MTMeasurements.csv, README.txt. Runner wall49.255396s ile test-runner duration farklı ölçümlerdir. Watcher regression artık gerçek PASS, test921.364ms; source hash değişimi/skip/timeout gevşetmesi yok.

Build: Vite üretim build'i ve esbuild server.cjs tamamlanmış; her ikisi logda görülüyor. Büyük chunk uyarısı sürüyor. Unit logunda test-fixture path'i için Vite dep-scan 'server is being restarted or closed / Request is outdated' mesajı var; terminal0FAIL/exit0 ile karıştırılmamalı, paket 'hatasız/uyarısız log' iddiası kurmamalı. Bu inceleme o shutdown mesajını yeni product bug olarak değerlendirmiyor.

## Install/policy/başarısız deneme ayrımı

- Başarılı **önceki native npm ci** ayrı kayıt `native-stage-npm-ci.json`: resmi Node/npmCLI `ci --offline=false --no-audit --no-fund`, exit0,135.031s,850 paket. Raw log hash `e185991a859e14890168bedffd960f876f326b42c5952122bb8f0ae887be85c2` bağımsız eşleşti.
- Resume summary reusedExistingInstalledDependencyTree=true /noNewNpmInstall=true. Bu dizide tekrar npmci yapılmadı; başarılı locked install kanıtı ayrı bağlanır. Ağlı kurulum offline başarı diye sunulmaz.
- Native install logu9 install-script entry için mevcut allowScripts coverage uyarısını koruyor. Helper npm policy/allowScripts/ignore-scripts/proxy/global config değiştirmiyor, yeni install/approval çalıştırmıyor. Build kaydı bu korunan politika altındaki gerçek sonuçtur; bütün install scripts çalıştı veya policy warning yok iddiası çıkarılmaz.
- İlk native unit sonucu370PASS/1FAIL/1SKIP ve buildNOTRUN ayrı başarısız kanıt olarak kalır. Controlled TEMP/TMP A/B ignored-ancestorFAIL/neutralPASS gözlemi de korunur. Yeni PASS bu eski başarısızlıkları silmez; aynı kaynakta yeni guarded sequence'dir.
- Yeni child TEMP/TMP `C:/Users/can02/AppData/Local/Temp/metalliksa-native-neutral-0kiizzyn`; locked Python/no-bytecode koşulları helper tarafından veriliyor. Security environment clearing, ürün/test patch'i ve recursive evidence cleanup yok.

## Kullanılabilecek sonuç

ec3 adayında recorded locked native npm install + fresh neutral lint/fullunit/build + six source guards yazılım kabul kanıtı olarak bağlanabilir. Bütün Python suite, fresh Python venv, fiziksel LPBF yakınsaması, deneysel validity, browser/keyboard/stale/cancel/portable UI kabulü veya **fullV1 accepted** sonucu çıkarılmaz. Önceki browser userdenial geçerli; canlı gate'ler ayrı bekliyor. Yalnız bu scratch rapor yazıldı; başkalarının dosya/STATUS/index/commit değişikliklerine dokunulmadı.
