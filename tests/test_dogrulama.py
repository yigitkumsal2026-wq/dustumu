"""İndirim doğrulama motoru testleri: python -m unittest discover tests"""
import unittest
from datetime import date

from dustumu.calendar_tr import ozel_gunler
from dustumu.sources import affiliate_link, tl, tr_baslik
from dustumu.sources.bim import etiket_tarihi
from dustumu.verify import degerlendir


class Dogrulama(unittest.TestCase):
    def test_gercek_indirim_gecmisle_dogrulanir(self):
        s = degerlendir([1000, 1000, 990, 1000], 800, 1200, "eticaret")
        self.assertEqual(s["karar"], "firsat")
        self.assertEqual(s["guven"], "dogrulandi")
        self.assertEqual(s["eski"], 990)  # üstü çizili fiyat değil, 30 günün en düşüğü
        self.assertAlmostEqual(s["indirim"], 19.19, places=1)

    def test_once_zam_sonra_indirim_sahte(self):
        # Ürün hep 800 TL; satıcı "1600'den 800'e %50 indirim" diyor.
        s = degerlendir([800, 810, 800, 805], 800, 1600, "eticaret")
        self.assertEqual(s["karar"], "red")

    def test_zam_yapilip_indirimli_gosterilen_sahte(self):
        # Fiyat 800'dü, 1000'e çıkarıldı, şimdi "1600'den 820" — 30 günün en düşüğü 800 > yine sahte.
        s = degerlendir([800, 800, 800, 1000, 1000], 820, 1600, "eticaret")
        self.assertEqual(s["karar"], "red")
        self.assertEqual(s["neden"], "sahte")

    def test_suren_kampanya_sahte_sayilmaz(self):
        # 1000 TL'lik ürün 5 gündür 700'de: kampanya öncesi fiyata göre hâlâ gerçek indirim.
        s = degerlendir([1000, 1000, 1000, 700, 700, 700, 700, 700], 700, 1000, "eticaret")
        self.assertEqual(s["karar"], "firsat")
        self.assertEqual(s["guven"], "dogrulandi")
        self.assertEqual(s["eski"], 1000)

    def test_gecmis_yokken_beyan_esigi(self):
        self.assertEqual(degerlendir([], 700, 1000, "eticaret")["guven"], "beyan")  # %30
        self.assertEqual(degerlendir([], 800, 1000, "eticaret")["karar"], "red")    # %20 < 30
        self.assertEqual(degerlendir([], 800, 1000, "market")["karar"], "firsat")   # market eşiği 20

    def test_inanilmaz_indirim_reddedilir(self):
        # Geçmiş yokken e-ticarette %74 "indirim" -> şişirilmiş liste fiyatı şüphesi.
        self.assertEqual(degerlendir([], 3265, 12500, "eticaret")["karar"], "red")

    def test_sisirilmis_liste_fiyati_duzeltilir(self):
        # 2 gün 1000 TL görüldü; satıcı liste fiyatını 2000 yazıyor -> eski fiyat 1000 alınır.
        s = degerlendir([1000, 1000], 650, 2000, "eticaret")
        self.assertEqual(s["karar"], "firsat")
        self.assertEqual(s["eski"], 1000)

    def test_cok_ucuz_urun_elenir(self):
        self.assertEqual(degerlendir([], 9, 20, "market")["karar"], "red")


class Yardimcilar(unittest.TestCase):
    def test_tl(self):
        self.assertEqual(tl("4.990,00 ₺"), 4990.0)
        self.assertEqual(tl("12599"), 12599.0)
        self.assertEqual(tl("6369.02"), 6369.02)
        self.assertEqual(tl("1.299"), 1299.0)

    def test_tr_baslik(self):
        self.assertEqual(tr_baslik("KUMTEL 11 DİLİM YAĞLI RADYATÖR ISITICI"), "Kumtel 11 Dilim Yağlı Radyatör Isıtıcı")

    def test_bim_etiket(self):
        self.assertEqual(etiket_tarihi("30 Ekim Cuma", date(2026, 10, 28)), (date(2026, 10, 30), None))
        self.assertEqual(etiket_tarihi("24-30 Ekim", date(2026, 10, 28)), (date(2026, 10, 24), date(2026, 10, 30)))
        self.assertEqual(etiket_tarihi("02 Ocak Cuma", date(2026, 12, 28))[0], date(2027, 1, 2))

    def test_black_friday(self):
        bf = next(o for o in ozel_gunler(2026) if o["ad"].startswith("Black Friday"))
        self.assertEqual(bf["tarih"], date(2026, 11, 27))

    def test_affiliate_link_soru_isareti(self):
        from dustumu import config
        config.ayarlar()["affiliate"]["amazon"] = "{url}?tag=deneme-21"
        self.assertEqual(affiliate_link("amazon", "https://a.com/x?y=1"), "https://a.com/x?y=1&tag=deneme-21")
        self.assertEqual(affiliate_link("amazon", "https://a.com/x"), "https://a.com/x?tag=deneme-21")
        config.ayarlar()["affiliate"]["amazon"] = ""


if __name__ == "__main__":
    unittest.main()
