# STATUS.md arşivleme planı

## Amaç ve yöntem

`STATUS.md` içindeki eski, tamamlanmış devam kayıtlarını `docs/archive/status-YYYY-MM.md` dosyalarına **kopyalayarak** ana durum dosyasını zamanla kısalt. Kaynak bölümleri bu plan kapsamında taşınmayacak veya silinmeyecek; gerçek arşivleme ayrıca kararlaştırılana kadar `STATUS.md` içeriği aynen kalacak. Ay etiketi, kaydın tarihine göre seçilsin; aynı ay için mevcut hedef varsa önce farkı incele ve üzerine yazma.

## Manifest incelemesi

İstenen tarama `rg -l "STATUS.md|PROOF.md" docs --glob "*.json"` ile yapıldı. Sonuçta `docs` altında 27 JSON manifest/snapshot dosyası eşleşti. İçerik incelemesinde source manifestlerinde `"STATUS.md": "<SHA-256>"` ve `"PROOF.md": "<SHA-256>"` biçiminde dosya yolu anahtarı ve hash değeri; bazı diagnostic JSON'larda ise yalnız açıklama metninde `STATUS.md` referansı görüldü. Bu eşleşmelerden arşivlemeyi gerçekleştirmek için hiçbir JSON değiştirilmedi.

Eski bölümlerin kopyasını `docs/archive/status-YYYY-MM.md` olarak eklemek, mevcut `STATUS.md` veya `PROOF.md` yollarını değiştirmediğinden bu manifestlerde kayıtlı tarihsel kaynak hash'lerini ve snapshot'ları geçersiz kılmaz. Bununla birlikte, `STATUS.md` sonradan düzenlendiğinde güncel dosyanın hash'i tarihsel snapshot hash'inden farklı olabilir; bu manifestler yeni canlı durumu değil, kaydedildikleri andaki dosya baytlarını doğrular. Arşiv kopyası da manifestlerde ayrıca listelenmedikçe hash kapsamına dahil değildir. Bu görevde arşivleme yapılmadı.

## Uygulama sırası — ileride

1. Aday eski bölümleri ve her birinin tarihini listele; güncel özet, açık eylemler ve bilimsel durum ifadelerini kaynakta bırak.
2. Her bölümün tam metnini uygun `docs/archive/status-YYYY-MM.md` hedefine kopyala; hedefin mevcut olmadığını veya içerikle uyumlu olduğunu doğrula.
3. Kopya ile kaynak bölümü karakter ve newline düzeyinde karşılaştır; bağlantıların ve başlıkların bağlamını koru.
4. Ayrı bir değişiklikte ancak arşiv kopyaları gözden geçirildikten sonra STATUS'tan çıkarılacak bölümleri belirle. Hash manifestleri varsa yeni canlı STATUS hash'ini ayrıca güncellemek gerekip gerekmediğini manifest amacına göre değerlendir; tarihsel kayıtları geriye dönük değiştirme.
5. Değişiklik kapsamını, kopya/çıkarma farkını ve manifest etkisini gözden geçir; uygun doküman kontrollerini çalıştır.