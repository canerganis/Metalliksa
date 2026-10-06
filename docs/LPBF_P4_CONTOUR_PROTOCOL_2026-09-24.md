# P4 sürekli liquidus konturu için önceden sabitlenmiş sayısal protokol

Durum: 75 W koşusu çalıştırılmadan önce sabitlendi. 80 W IN718 ayrık W/D
kapısının başarısız sonucu korunur. 80 W, 5 µm keşif çalışmasında sürekli
liquidus konturunun 20/10/5 µm boyunca iyileştiği görüldü; bu nedenle 80 W
sonucu yeni kapı için bağımsız kabul kanıtı sayılmayacaktır.

## Bağımsız süreç vektörü ve eksenler

`docs/LPBF_P4_CONTOUR_SCENARIO_75W_2026-09-24.json` içindeki IN718 tek iz,
tek katman, toz katmanlı 75 W / 1200 mm/s / 80 µm ışın / 80 µm katman / 200 µm
iz kullanılır. Model `stationary-enthalpy-conduction-v1`, solver
`enthalpy-fv-6`, backend `numpy-reference` ve malzeme revizyonu altı koşuda
aynı olmalıdır. Bu süreç vektöründe önceden sonuç alınmadı.

- Ağ ekseni: istenen 20, 10, 5 µm; tümünde azami zaman adımı `5e-8` s.
- Zaman ekseni: istenen `1e-7`, `5e-8`, `2.5e-8` s; tümünde istenen ağ 10 µm.
- Her eksen için üç bağımsız solver çağrısı; gerçek ağ ve ortalama zaman adımı
  kullanılır. Eksik/başarısız çağrı veya çözünürlük sıralaması eksik kanıttır.

## Operatör ve kabul

Birincil yeni operatör `peak-liquidus-cell-edge-linear-contour-v1`;
`accepted-step-molten-volume-v1` zaman seçimiyle aynı tepe alanında komşu
aktif hücre merkezleri arasındaki lineer liquidus geçişlerinden küresel W/D
elde edilir. Yüzeye ekstrapolasyon yapılmaz. Bu termal sayısal vekildir;
NIST'in dağlanmış optik kesit operatörü değildir.

Her koşulun kaynak/enerji/alan kimliği ve pozitif sonlu W/D değeri zorunludur.
Dondurulmuş eşikler korunur: enerji bağıl kapanış hatası en fazla %1; son iki
seviye W ve D değişimi ayrı ayrı en fazla %5; son üç gerçek çözünürlükte
`lpbf_verification.convergence` sonucu her iki metrik ve eksen için
`numerically-converging` olmalıdır. Başarısız veya belirsiz metrik PASS'a
çevrilmez. Eski ayrık hücre W/D değerlendirmesi aynı raporda ayrıca kalır.

75 W çalışması bu ayrı protokolü geçse bile sonuç yalnız sayısal termal vekil
yakınsamasıdır. NIST'in 2025 beam report'u ölçülmüş nominal 67 µm Gaussian
`Dg` çapını %5,2 birleşik standart belirsizlikle, dairesellik sapmasını da
1 µm olarak verir; indirilebilir ham 2B ışınım artefaktı sağlamaz. Solver'ın
1/e² çapı ideal Gaussian'da `Dg` ile aynıdır; NIST Table 4'ün nominal D4σ
değeriyle eşleme açık bir yaklaşım ve belirsizlikle kaydedilmelidir. P5 için
source-byte bağlı beam kaydı, 4,9/6,0 mm'deki üç tekrar iz ve optik sınır
operatörü ayrıca gereklidir.
