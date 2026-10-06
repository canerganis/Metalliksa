# Phase 22 enerji defteri ve CUDA ölçek denetimi

## Bulgular ve değişiklik

`enthalpy_3d_nonlinear_step_kernel` yüzeydeki enerji girdilerini/losslarını `dz` ile hacimsel entalpi artışına çeviriyor. Lazer Gauss akısı projeksiyon düzlemine göre tanımlı; çevre kayıpları ve buharlaşma ise gerçek serbest yüzey alanını kullanmalı. Kod buharlaşma akısını `surface_metric` ile önceden çarpıp sonra ortak kayıp ifadesinde aynı metrikle tekrar çarpıyordu. Bu, eğimli yüzeyde gizli ısı kaybını `1 + hx² + hy²` oranında büyütüyordu. Buharlaşma akısı birim gerçek-alan akısı olarak bırakıldı; konveksiyon, radyasyon ve buharlaşma kayıpları ortak ifadede metrikle tam bir kez ölçekleniyor.

İsteğe bağlı enerji defteri her fizik adımında üretim operatörlerini ayrı ledger kernelinde bütün etkin hücreler üzerinde bütünleştiriyor: soğurulan lazer girdisi, net iletim, net ortak-yüzey adveksiyonu, konveksiyon, radyasyon, buharlaşma ve hareketli yüzey maskesinin ortam entalpisine sıfırladığı enerji. Rapor ayrıca toplam entalpi değişimini, duyulur/gizli ısı ayrımını, trapez integralli nominal soğurulan lazer enerjisini ve kapanış artığını döndürüyor. Bağımsız kontrol, bu terim toplamını üretim çözümünün son tam-alan entalpi değişimiyle kıyaslıyor. Sabit dış kabukla iletim net iletimde yer alır; iç adveksiyon akısı ortak yüzeylerde karşılıklı iptal olmalıdır. Akışkan basınç/viskoz iş terimleri bu termal entalpi denklemine bağlı değildir ve kapsam dışında belirtilir.

Tam alan tanılaması 100.000 hücrede kalır. Enerji defterinin ayrı 1.000.000 hücre sınırı vardır; 64³ denetiminde yedi float64 dizisi yaklaşık 14,7 MiB ek bellek tuttu. Sınırın üzerindeki çok daha büyük defter koşuları için sonraki ölçek adımı hücre dizileri yerine GPU üzerinde blok indirgemeli toplam kullanmaktır.

## Doğrulama

| Koşu | Cihaz ve ayar | Sonuç |
|---|---|---|
| Odaklı CPU testleri | Warp CPU; tam `test_lpbf_transient_3d_gpu.py` ve yeni Phase 22 ledger testi | 28 test geçti |
| CUDA ledger doğrulaması | RTX 4060 Laptop, 7³ hücre, 1 adım, 80 W, 0,2 µs | Kapanış bağıl artığı `1,9709e-6`; bağımsız tam alan entalpi toplamı testi geçti |
| CUDA ölçek ve ledger | RTX 4060 Laptop, `cuda:0`, 64³ = 262.144 hücre, 10 µm ağ, 60 µs, 43 adım, 25 W, 1700 K ön ısıtma | Kapanış bağıl artığı `9,7241e-5` (`< 1e-3` kabul sınırı); artığın işaretiyle `ΔH − model = −8,05e-8 J` |

Ölçek koşusundaki enerji terimleri: lazer `+6,00000e-4 J`; iletim `+2,06163e-8 J`; adveksiyon `+2,41e-12 J`; konveksiyon `−1,19205e-9 J`; radyasyon `−7,82623e-8 J`; buharlaşma `−1,29369e-6 J`; yüzey maskesi sıfırlaması `−2,26921e-4 J`. Toplam entalpi değişimi `3,71646e-4 J`, modelin öngördüğü `3,71726e-4 J` oldu. Nominal lazer integrali `6,0e-4 J`; diskret alan yakalaması `1,00000003` (float yuvarlaması düzeyinde 1'in üzerinde).

GPU: Warp 1.17.0, CUDA Toolkit 12.9, sürücü 13.4, 8 GiB NVIDIA RTX 4060 Laptop (`sm_89`). Defterli soğuk çalıştırma duvar süresi 10,633 s (solver bildirimi 10,553 s; ilk CUDA modül yükleme/derleme yaklaşık 8,797 s). Aynı süreçte derleme sonrası tekrar 1,644 s duvar, 1,623 s solver süresi aldı. Warp bellek havuzu tepe kullanımı 33.587.288 bayt; ledger öncesi aynı 64³ koşuda 18.907.224 bayt idi. GPU boş belleği 7.451.181.056'dan 7.449.083.904 bayta düştü; Warp havuzunun rezervasyon yuvarlaması nedeniyle bu değer gerçek canlı tensör toplamı olarak yorumlanmamalı.

Ledger kabul eşiği `1e-3`, tekil 64³ GPU ölçümündeki `9,72e-5` kapanış hatasının yaklaşık on katı payını bırakır; küçük CPU/CUDA çapraz kontrolleri yaklaşık `2e-6` verdi. Bu, bu test edilen ayrık model ve float32 entalpi saklaması için seçilmiş sayısal kabul sınırıdır; doğruluk belirsizliği veya deneysel doğrulama iddiası değildir.

Ölçek koşusunda en yüksek son sıcaklık 3529,96 K, eriyik hacmi 61.000 µm³, hesaplanan keyhole derinliği 21,744 µm oldu. Basınç izdüşümü yakınsadı; doğrusal bağıl artık `8,9697e-4`, son adım bağıl diverjansı `8,9697e-4` ve ikisi de `1e-3` toleransının altında. Tepe sıcaklığı 3533 K buharlaşma referansına yakın olduğundan bu tek koşu kaynama rejimini doğrulamaz; amaç ölçek ve muhasebe kapanışıdır.

## Tekrarlama

Önce Warp derleme önbelleğini yazılabilir bir klasöre yönlendirip PCH'yi kapatın; sonra `TransientEnthalpy3DGPU(64, 64, 64, 10e-6, 10e-6, 10e-6)` kurucusunda `device = "cuda:0"` seçerek aşağıdaki araç yolunu `solve_toolpath`'a verin:

```python
{
    "t": [0.0, 60e-6],
    "x": [300e-6, 340e-6],
    "y": [320e-6, 320e-6],
    "p": [25.0, 25.0],
}
```

`T_preheat_K=1700.0, include_energy_ledger=True` ile çağırın. Gerçek süre için çağrıdan önce/sonra `time.perf_counter()` ve `wp.synchronize()` kullanın; tepe bellek için `wp.get_mempool_used_mem_high("cuda:0")` okuyun. Bir sonraki daha büyük denetim 128³ için blok indirgeme ledger'ı ekleyip aynı enerji terimleri/kapanış karşılaştırmasını GPU üzerinde yinelemelidir; mevcut 1 milyon-hücre sınırı bu koşuyu bilerek engeller.

## Kod bağlamı

Graft'ta solver operatörleri ve doğrudan kaynak eşleştirmesi için üç odaklı sorgu kullanıldı. Bu sorguların raporlanan toplam tasarrufu yaklaşık **155 token** oldu.
