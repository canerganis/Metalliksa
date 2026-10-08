# Metalliksa — Project Rules

## 1. Dil ve kapsam

- Kullanıcıyla Türkçe iletişim kur. Uygulamadaki kullanıcı metinleri İngilizce olmalıdır.
- Kod adları ve teknik yorumlarda İngilizce kullan.
- Kullanıcının kabul ettiği kapsamda ilerle; rutin uygulama kararları için tekrar onay isteme.
- Kapsamı önemli ölçüde değiştiren kararları açıkla. Ücretli hesap, dış mesaj ve geri döndürülemez işlemler için gerekli yetkiyi doğrula.

## 2. Kanıt ve doğrulama

- Değişen davranışı riskine uygun, en dar anlamlı seviyede doğrula.
- Fizik değişikliğinde ilgili sayısal kontrolleri ve dondurulmuş benchmark'ları çalıştır.
- UI değişikliğinde etkilenen akışı gerçek tarayıcıda, klavye ve erişilebilirlik açısından kontrol et.
- Doküman değişikliğinde içerik, bağlantı ve diff kontrolü yeterlidir; ilgisiz ürün testleri zorunlu değildir.
- Çalıştırılmayan, atlanan ve başarısız kontrolleri belirt. Tarihsel başarı güncel kanıt değildir.
- Doğrulanmış bilimsel iddiaları PROOF.md içinde kapsam, girdiler, kaynak/benchmark, sonuç ve kabul ölçütüyle kaydet.
- Mock, sentetik, tahmini veya kaynağı doğrulanmamış kullanıcı verisini ölçülmüş gerçeklik olarak sunma.
- Qualification kayıtlarında Build → ProcessParams → Sample → Properties → Source zincirini koru; alan ayrıntıları docs/archive/SCHEMA.md içindedir.
- Bir standart uyumu iddiasında ilgili ASTM/ISO standardını ve kapsamını belirt; atıf tek başına doğrulama değildir.

## 3. Süreklilik ve teslim

- Ürün devam noktası Metalliksa-1/STATUS.md dosyasıdır; workspace ve araç notları ../STATUS.md içindedir.
- Durum notunu yalnız kilometre taşında veya işe devam etmek için gerektiğinde güncelle; her ara işlemi kaydetme.
- Ani kesinti kayıt yazmayı engellerse sonraki başlangıçta repo durumundan devam notunu tamamla.
- sonkayıtlar/LOG.md tarihsel kayıttır; her araç çağrısı veya küçük işlem için ikinci bir uzun kayıt zorunlu değildir.
- Agent Memory'yi yalnızca kalıcı bir kararı hatırlatmaya yardım edecekse kullan.
- Kullanıcıya sonucu, doğrulama kanıtını ve kalan sınırlamaları kısa biçimde bildir.

## 4. Commit ve dış yayın

- Dosya/kod değiştiren tamamlanmış işi uygun doğrulamadan sonra yalnız o işe ait değişikliklerle yerel Git commit'ine al; değişiklik yoksa boş commit üretme.
- Önce ilgili diff ve staged kapsamını incele; yalnız kendi görev değişikliklerini ekle.
- Kullanıcı/diğer ajan değişikliklerini, gizli bilgileri, .env dosyalarını ve üretilmiş çıktıları yanlışlıkla commit etme.
- Açık dosya yollarıyla stage et; ortak çalışma sırasında git add . veya git add -A kullanma.
- Push veya yayın yalnız kullanıcı tarafından yetkilendirilmiş kapsamda yapılır; yerel commit isteği otomatik push talebi değildir.
- Git kimliğini değiştirme, doğrulama hook'larını atlama veya paylaşılan geçmişi yeniden yazma.
- Kullanıcı işi üzerinde reset, checkout, clean veya stash uygulama.
- İç uygulama reposu ve üst workspace reposu ayrı geçmişlerdir; her commit'in hedefini kontrol et.

## 5. Codex, Gemini ve diğer ajanlarla ortak çalışma

- Başkasının erişimini veya otomatik mesaj alacağını varsayma. Bir dosyaya not yazmak karşı tarafa teslim onayı değildir.
- Eşzamanlı işlerde görev, ajan, branch/worktree, sahip olunan yollar, ortak sözleşme ve kabul kontrollerini görünür biçimde kaydet.
- Aynı dosyada eşzamanlı yazma yapma. Shared schema, package lock, ana router ve STATUS.md gibi ortak dosyalar için tek entegrasyon sahibi belirle.
- docs/ACTIVE_WORK.md paralel işleri koordine etmek için isteğe bağlıdır; atomik kilit veya onay değildir.
- Yazmadan ve commit'ten önce değişiklikleri yeniden kontrol et. Beklenmeyen örtüşmede dosyayı ezme; etkilenmeyen işte ilerle ve koordinasyon iste.
- Ayrı worktree gerekiyorsa başlangıç commit'ini ve gerekli mevcut değişiklikleri açıkça belirt; kirli çalışma ağacının otomatik taşındığını varsayma.
- Ortak checkout'ta Git index işlemlerini sırala. Diğer ajanın staged değişikliklerini kendi commit'ine alma.
- Entegrasyon sahibi birleşik sonucu doğrular. Bir ajanın PASS raporu entegrasyon testi yerine geçmez.
