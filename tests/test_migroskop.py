"""Migroskop ayrıştırıcı testleri: python -m unittest discover tests"""
import unittest
from datetime import date

from dustumu.sources.migroskop import ayristir, donem

BUGUN = date(2026, 10, 30)
DONEM = '<img src="https://x/909 22 EKIM-4 KASIM MIGROSKOP HODRI/Ad/a.jpg"><img src="https://x/910 5-18 KASIM MIGROSKOP/Ad/b.jpg">'


def _fiyat(tam, kurus, birim=""):
    return (f'<div class="price-text"><div class="first"><span>₺</span><span>{tam},</span></div>'
            f'<div class="second"><span>{kurus}</span><span>{birim}</span></div></div>')


def _sayfa(icerik, pid="1"):
    return (f'{DONEM}<div class="page"><div class="content"><div class="product" data-pid="{pid}">'
            f'<div class="image"><img src="https://x/1.png"></div><h1 class="title">Ürün<br>500 g</h1>{icerik}'
            '</div></div><span class="pn" data-page-number="8"></span></div>')


class Migroskop(unittest.TestCase):
    def test_money_fiyati_ve_money_siz_fiyat(self):
        k = f'<div class="price-content" name="indirimli-fiyat">{_fiyat("149", "95")}<h6>MONEY\'Lİ FİYAT</h6>{_fiyat("112", "50")}</div>'
        u = ayristir(_sayfa(k), BUGUN)[0]
        self.assertEqual((u.fiyat, u.liste_fiyat), (112.5, 149.95))
        self.assertEqual(u.ad, "Ürün 500 g")
        self.assertEqual((u.bitis, u.gecerlilik), ("2026-11-04", "22 Ekim-4 Kasım"))
        self.assertEqual(u.url, "https://migroskop.migros.com.tr/migroskop#sayfa/8")

    def test_binlik_fiyat(self):
        k = f'<div class="price-content" name="indirimli-fiyat">{_fiyat("1.279", "95")}<h6>MONEY\'Lİ FİYAT</h6>{_fiyat("999", "00")}</div>'
        self.assertEqual(ayristir(_sayfa(k), BUGUN)[0].liste_fiyat, 1279.95)

    def test_raf_fiyatinda_indirim_yok(self):
        k = f'<div class="price-content" name="raf-satis-fiyat">{_fiyat("162", "90", "Adet")}</div>'
        u = ayristir(_sayfa(k), BUGUN)[0]
        self.assertEqual((u.fiyat, u.liste_fiyat), (162.9, None))

    def test_rozetli_urun_atlanir(self):
        k = '<div class="price-content"><div class="badge-content" name="x"><span>1 ALANA</span></div></div>'
        self.assertEqual(ayristir(_sayfa(k), BUGUN), [])

    def test_donem_yoksa_urun_alinmaz(self):
        k = f'<div class="price-content" name="raf-satis-fiyat">{_fiyat("10", "00")}</div>'
        self.assertEqual(ayristir(_sayfa(k).replace(DONEM, ""), BUGUN), [])

    def test_ayni_ay_ve_yil_donumu(self):
        self.assertEqual(donem("909 5-18 KASIM MIGROSKOP", BUGUN), ("5-18 Kasım", "2026-11-18"))
        self.assertEqual(donem("909 25 ARALIK-7 OCAK MIGROSKOP", date(2026, 12, 28))[1], "2027-01-07")


if __name__ == "__main__":
    unittest.main()
