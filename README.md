# DÜŞTÜ MÜ? ⬇ — Gerçek İndirim Otomasyonu

Instagram: [@dustu.mu](https://www.instagram.com/dustu.mu/)

E-ticaret ve market indirimlerini otomatik toplar, **sahte indirimleri ayıklar**, dikkat çekici
görseller üretir ve Instagram'a hesabın bot sanılmayacağı bir tempoda paylaşır. Tamamen ücretsizdir:
GitHub Actions (çalıştırma) + GitHub Pages (link sayfası) + Instagram resmi API.

---

## 1. Ne yapıyor?

| # | Özellik | Nasıl |
|---|---|---|
| 1 | **E-ticaret indirimleri** | n11 otomatik; Trendyol / Hepsiburada / Amazon panelden (affiliate linkinle) |
| 1 | **"Doğru indirim" doğrulama** | Her ürünün günlük fiyatı kaydedilir. İndirim, satıcının üstü çizili fiyatına göre değil, **son 30 günün en düşük fiyatına** göre hesaplanır (Ticaret Bakanlığı yönetmeliği ile aynı mantık). "Önce zam sonra indirim" yapanlar elenir. |
| 2 | **Market indirimleri + günleri** | Migros, ŞOK (Haftanın Fırsatları), BİM Aktüel (katalog tarihleriyle). A101 manuel. Her pazartesi "Bu hafta indirim takvimi" gönderisi. Black Friday, 11.11, Anneler Günü vb. yıl bazında otomatik hesaplanır. |
| 3 | **Otomatik Instagram paylaşımı** | Resmi Instagram Graph API: tekli gönderi, market carousel'i (kaydırmalı), hikâye |
| 4 | **Bot sanılmama** | Isınma planı (yeni hesap 2/gün → 30. günden sonra 6/gün), gönderiler arası 2 saat ± rastgele sapma, sadece 08–23 arası, altın saatlere öncelik, aynı ürünü 14 gün tekrar etmeme, her gönderide farklı açıklama |
| 5 | **İndirimli ürüne link** | Instagram açıklamadaki linkleri tıklatmaz. Çözüm: bio'daki **link sayfası** (kodla arama) + her fırsatın kısa linki `.../k/123` + isteğe bağlı **"LİNK" yazana DM ile otomatik link** |
| 6 | **Dikkat çekici görseller** | 4:5 akış formatı, dönen renk temaları, dev indirim etiketi, "Gerçek indirim ✓" rozeti, "X TL tasarruf" şeridi |
| 7 | **Ekstralar** (aşağıda) | |

### Senin aklına gelmeyen ama eklediklerim (madde 7)
- **Sahte indirim avcısı:** Yakalanan sahte indirimler link sayfasında listelenir → güven inşa eder, içerik fikri olur.
- **Fiyat geçmişi** ve panelde mini grafik.
- **Link sayfası** (bio linki): kod arama, filtreler, haftalık market takvimi, yaklaşan büyük indirim günleri geri sayımı.
- **Yorum → DM:** "LİNK" yazanlara linki özel mesajla gönderir (etkileşimi ve erişimi artırır).
- **Telegram kanalı** (isteğe bağlı): aynı fırsatlar **tıklanabilir** linkle; hatalar sana bildirim olarak gelir.
- **Affiliate (gelir ortaklığı)** desteği + Reklam Kurulu kuralı gereği otomatik `#işbirliği` etiketi.
- **Token otomatik yenileme** (Instagram token'ı 60 gün geçerli; bot haftada bir yeniler, şifreli saklar).
- **Kara liste:** alkol/tütün vb. kelimeler + panelden "Gizle" ile ürün engelleme.
- **Siteye nazik davranma:** robots.txt'e uyar, istekler arası bekler, bot korumasını aşmaya çalışmaz, tam tarama 3 saatte bir.
- **Yasal alt bilgi:** "Fiyatlar paylaşım anındaki fiyatlardır" + tarih/saat.

---

## 2. Önce bilgisayarında incele (yerel deneme)

Python 3.11+ gerekli (sende 3.12 kurulu).

1. Klasördeki **`PANEL_AC.bat`** dosyasına çift tıkla. (Ya da terminalde: `pip install -r requirements.txt` → `python main.py panel`)
2. Tarayıcıda `http://localhost:5000` açılır.
3. Sırasıyla:
   - **"1. Fiyatları topla + doğrula"** (2-3 dk sürer, ~1.200 ürün tarar)
   - **"Gönderi planla (hemen, zorla)"** → **Gönderiler** sekmesinde görselleri ve açıklamaları gör
   - **"Link sayfasını önizle"** → bio'ya koyacağın sayfa
   - **Fırsatlar** sekmesi: tüm fırsatlar, güven seviyesi, fiyat grafiği. Beğendiğine "Gönderi yap", istemediğine "Gizle"
   - **Manuel fırsat ekle:** Trendyol/Hepsiburada fırsatlarını buradan ekle

> Panel **deneme modundadır**: Instagram'a hiçbir şey gitmez. `config.yaml`'da `instagram_aktif: false`.

**Önemli:** İlk gün fiyat geçmişi olmadığı için fırsatlar "beyan" (satıcı indirimi) olarak görünür.
Sistem 3 gün fiyat biriktirdikten sonra gerçek indirimleri **"Gerçek indirim ✓"** ile işaretlemeye başlar.
E-ticaret ürünleri Instagram'a sadece doğrulandıktan sonra gider (`eticaret_sadece_dogrulanmis: true`).
Bu yüzden botu **Instagram'ı açmadan önce 3-4 gün deneme modunda bulutta çalıştırman** önerilir.

---

## 3. Buluta kur (bilgisayarın kapalıyken de çalışsın) — ücretsiz

### 3.1 GitHub deposu
1. [github.com](https://github.com) hesabı aç (yoksa).
2. Sağ üst **+ → New repository** → ad: `dustumu` → **Public** seç (ücretsiz Actions dakikası ve Pages için gerekli; şifreler depoda değil "Secrets"ta durur) → *Create repository*.
3. Bu klasörde terminal aç ve (KULLANICI_ADIN yerine kendi adını yaz):
   ```
   git remote add origin https://github.com/KULLANICI_ADIN/dustumu.git
   git push -u origin main
   ```
   (Klasör zaten git deposu olarak hazırlandı ve ilk commit yapıldı.)

### 3.2 GitHub Pages (link sayfası)
Depoda **Settings → Pages → Build and deployment → Source: "GitHub Actions"** seç.
Link sayfan şu adreste olacak: `https://KULLANICI_ADIN.github.io/dustumu/`
→ Bunu Instagram **bio'na** link olarak ekle. (`config.yaml` > `site_url`'i de bununla güncelle; bulutta otomatik algılanır ama yerelde açıklamalarda görünür.)

### 3.3 İlk çalıştırma (deneme modu)
Depoda **Actions** sekmesi → "I understand… enable" → **Düştü Mü botu → Run workflow**.
Bot bundan sonra her gün 08:00–24:00 arası 30 dakikada bir kendiliğinden uyanır.
Çoğu turda "henüz zamanı değil" deyip kapanır; bu normaldir (insan gibi aralıklı paylaşım).

---

## 4. Instagram bağlantısı (resmi API — şifre vermezsin)

1. **Hesabı profesyonele çevir:** Instagram uygulaması → Profil → ☰ → *Hesap türü ve araçlar* → **Profesyonel hesaba geç** → *İçerik Üretici* veya *İşletme* (kategori: "Alışveriş ve Perakende").
2. [developers.facebook.com](https://developers.facebook.com) → giriş yap → **My Apps → Create App** → kullanım alanı: **"Manage messaging & content on Instagram"** → oluştur.
3. Uygulama panelinde **Instagram → API setup with Instagram login**:
   - **"Add account"** → `dustu.mu` ile giriş yap, izinleri onayla.
   - Hesabın yanında **"Generate token"** → çıkan **token**'ı kopyala (bu `IG_ACCESS_TOKEN`).
   - Aynı yerde görünen hesap kimliği (Instagram user ID, rakamlar) → `IG_USER_ID`.
   - İzinler: `instagram_business_basic`, `instagram_business_content_publish` (DM için ayrıca `instagram_business_manage_comments`, `instagram_business_manage_messages`).
   - Uygulama "Development" modunda kalabilir: kendi hesabın uygulamanın rolüne eklendiği için yayın yapabilir, App Review gerekmez.
4. GitHub deposu → **Settings → Secrets and variables → Actions**:
   - **Secrets** sekmesi → *New repository secret*:
     - `IG_USER_ID` = hesap kimliği
     - `IG_ACCESS_TOKEN` = token
     - `DURUM_ANAHTARI` = rastgele uzun bir parola (ör. 40 karakter; yenilenen token'ı şifrelemek için. **Mutlaka koy**, yoksa 60 günde bir token'ı elle yenilemen gerekir.)
   - **Variables** sekmesi → *New repository variable*:
     - `INSTAGRAM_AKTIF` = `true`  ← canlıya geçiş anahtarı (kapatmak için `false`)
     - (isteğe bağlı) `YORUM_DM_AKTIF` = `true`
5. Bağlantıyı yerelde test etmek için `.env.example`'ı `.env` olarak kopyalayıp doldur → `python main.py ig-test`.

**Yorum → DM için ek ayar:** Instagram uygulaması → Ayarlar → *Mesajlar ve hikâye yanıtları* → *Mesaj kontrolleri* → *Bağlı araçlar* → **"Mesajlara erişime izin ver"** açık olmalı.

---

## 5. Paylaşım limitleri — neden bu sayılar?

- Instagram resmi API sınırı: **24 saatte 100 gönderi** (carousel tek gönderi sayılır). Bot bunu her yayından önce kontrol eder.
- Ama asıl risk API sınırı değil, **yeni hesabın ani hacimle "spam" algılanmasıdır.** Instagram kesin bir eşik açıklamaz; güvenli pratik, düşük başlayıp kademeli artırmaktır:

| Hesap yaşı | Günlük feed gönderisi | Hikâye |
|---|---|---|
| 0–6 gün | 2 | ≤8 |
| 7–13 gün | 3 | ≤8 |
| 14–29 gün | 4 | ≤8 |
| 30+ gün | 6 | ≤8 |

- Gönderiler arası en az **120 dk ± 25 dk rastgele**, sadece **08:00–23:00**, öncelik **08-09, 12-14, 19-22**.
- Gönderi başına **5 hashtag** (Instagram 3-5 öneriyor; 30'a kadar izin verse de fazlası erişimi düşürebilir).
- Hepsi `config.yaml` > `yayin` bölümünden değiştirilebilir.

Bir de şunlara dikkat et: ilk hafta profil fotoğrafı, bio ve 3-4 elle gönderiyle hesabı "insan" göster; aynı gün başka bir otomasyon aracı (takip/beğeni botu) kullanma.

---

## 6. Gelir: affiliate linkleri

- **Trendyol, Hepsiburada, Amazon** ortaklık programlarına başvur. Onaylanınca ürün için aldığın linki panelden "Manuel fırsat ekle"ye yapıştır, "affiliate" kutusunu işaretle.
- URL parametresiyle çalışan programlar için `config.yaml` > `affiliate` bölümüne şablon gir: ör. `amazon: "{url}?tag=SENIN-ETIKETIN-21"`.
- Affiliate olan gönderilere otomatik `#işbirliği` eklenir (Reklam Kurulu sosyal medya etkileyicileri kılavuzu).

Bulutta manuel fırsat eklemek için GitHub'da `data/manuel_firsatlar.yaml` dosyasını tarayıcıdan düzenleyebilirsin (dosyada örnek var), ya da yerel panelden ekleyip `git push` yaparsın.

---

## 7. Hangi siteler neden otomatik / manuel?

| Kaynak | Durum | Neden |
|---|---|---|
| n11 | ✅ otomatik | Herkese açık yapılandırılmış veri (schema.org), robots.txt izinli |
| Migros | ✅ otomatik | Herkese açık ürün listesi, indirim oranıyla |
| ŞOK | ✅ otomatik | Haftanın Fırsatları sayfası |
| BİM | ✅ otomatik | Aktüel katalogları + tarihleri |
| Trendyol, Hepsiburada, Amazon, A101, Teknosa… | ✋ manuel | Bot koruması var. Korumayı aşmak kullanım koşullarına aykırıdır ve IP/hesap engeline yol açar; bot bunu bilerek **yapmaz**. Bu siteler için affiliate linkiyle manuel ekleme hem güvenli hem gelir getirir. |

Bir site yapısını değiştirirse o kaynak o tur atlanır, diğerleri çalışmaya devam eder (Telegram hata bildirimi açıksa haber verir). Kaynak kodları `dustumu/sources/` altında, her biri tek dosya.

---

## 8. Komutlar

```
python main.py panel            # yerel panel
python main.py topla            # fiyatları topla + doğrula
python main.py planla --zorla   # hemen gönderi üret
python main.py site             # link sayfasını üret (durum/site/index.html)
python main.py durum            # özet
python main.py ig-test          # Instagram bağlantı testi
python -m unittest discover tests   # doğrulama motoru testleri
```

## 9. Klasör yapısı

```
config.yaml              ← TÜM ayarlar (limitler, kaynaklar, saatler, hashtag sayısı…)
data/manuel_firsatlar.yaml  ← elle eklenen fırsatlar
data/kara_liste.yaml     ← paneldeki "Gizle" ile engellenenler
dustumu/sources/         ← her mağaza için bir dosya
dustumu/verify.py        ← doğru indirim motoru
dustumu/render.py        ← görsel üretici
dustumu/planner.py       ← ne zaman ne paylaşılacak
dustumu/instagram.py     ← Instagram API
dustumu/site.py + site_sablon.html ← link sayfası
.github/workflows/bot.yml ← bulut zamanlayıcı
durum/                   ← veritabanı + üretilen site (bulutta "veri" dalında saklanır)
```

## 10. Sorun giderme

- **"Medya işlenemedi"**: Pages henüz yayında değil ya da Pages kaynağı "GitHub Actions" seçilmemiş (3.2).
- **"Invalid OAuth access token"**: token süresi dolmuş/yanlış → 4.3'teki gibi yeniden üret, secret'ı güncelle.
- **Hiç paylaşım yok**: Actions loglarında "Bu turda paylaşım yok: …" nedenini yazar (saat dışı, limit, bekleme). Hemen denemek için *Run workflow → zorla* işaretle.
- **GitHub zamanlanmış görevi durdurdu**: Herkese açık depolarda 60 gün commit olmazsa GitHub zamanlayıcıyı kapatır; Actions sekmesinden tekrar etkinleştir.
