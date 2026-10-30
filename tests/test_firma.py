"""Tek firma kuralı testleri: python -m unittest discover tests"""
import unittest

from dustumu.planner import _cesitli_sec, _firma_sec, _tazelik, _urun_tipi, _yer_eki


def _adaylar(adet=3, bitis=None, puan=10):
    return [{"bitis": bitis, "puan": puan}] * adet


class FirmaSec(unittest.TestCase):
    def test_bitisi_yakin_firma_once(self):
        g = {"migroskop": _adaylar(bitis="2026-11-04"), "bim_indirim": _adaylar(bitis="2026-11-02"), "sok": _adaylar()}
        self.assertEqual(_firma_sec(g, None), "bim_indirim")

    def test_ayni_firma_ust_uste_gelmez(self):
        g = {"migroskop": _adaylar(bitis="2026-11-04"), "bim_indirim": _adaylar(bitis="2026-11-02")}
        self.assertEqual(_firma_sec(g, "bim_indirim"), "migroskop")

    def test_tek_firma_varsa_tekrar_edebilir(self):
        self.assertEqual(_firma_sec({"sok": _adaylar()}, "sok"), "sok")

    def test_uc_adaydan_azsa_secilmez(self):
        self.assertIsNone(_firma_sec({"sok": _adaylar(2)}, None))


class FirmaDonusu(unittest.TestCase):
    def test_en_uzun_suredir_paylasilmayan_once(self):
        g = {"migroskop": _adaylar(bitis="2026-11-04"), "migros": _adaylar(), "sok": _adaylar()}
        son = {"migroskop": "2026-10-31T09:00", "migros": "2026-10-30T09:00", "sok": "2026-10-29T09:00"}
        self.assertEqual(_firma_sec(g, None, son, "2026-11-01"), "sok")

    def test_bitmek_uzere_olan_one_gecer(self):
        g = {"bim_indirim": _adaylar(bitis="2026-11-02"), "sok": _adaylar()}
        son = {"bim_indirim": "2026-11-01T09:00", "sok": "2026-10-29T09:00"}
        self.assertEqual(_firma_sec(g, None, son, "2026-11-02"), "bim_indirim")


def _urunler(*adlar):
    return [{"ad": a, "kaynak": "sok"} for a in adlar]


class Cesit(unittest.TestCase):
    def test_ayni_marka_en_fazla_iki(self):
        s = _cesitli_sec(_urunler("Nivea Men Sprey", "Nivea Fresh Sprey", "Nivea Kadın Sprey", "Milka Çilekli 300 g"), 9, kaynak_siniri=9)
        self.assertEqual([u["ad"] for u in s], ["Nivea Men Sprey", "Nivea Fresh Sprey", "Milka Çilekli 300 g"])

    def test_ayni_tip_en_fazla_iki(self):
        s = _cesitli_sec(_urunler("Omo Toz Deterjan", "Persil Sıvı Deterjan", "Bingo Matik Deterjanı", "Eti Burçak"), 9, kaynak_siniri=9)
        self.assertEqual([u["ad"] for u in s], ["Omo Toz Deterjan", "Persil Sıvı Deterjan", "Eti Burçak"])

    def test_elle_secilende_sinir_yok(self):
        s = _cesitli_sec(_urunler("KIKO Ruj 1", "KIKO Allık 2", "KIKO Far 3"), 9, kaynak_siniri=9, aile_kontrol=False)
        self.assertEqual(len(s), 3)

    def test_yakinda_paylasilan_aile_geriye_duser(self):
        son = ["Signal White Now Gold Diş Macunu 75 Ml"]
        adlar = ["Signal White Now Original 75 Ml", "Colgate Optic Diş Macunu 75 Ml", "Eti Burçak 200 g"]
        self.assertEqual(sorted(adlar, key=lambda a: _tazelik(a, son)), [adlar[2], adlar[1], adlar[0]])

    def test_tip_buyuk_harfte_de_bulunur(self):
        self.assertEqual(_urun_tipi("DİŞ MACUNU 75 ML"), "diş macunu")
        self.assertIsNone(_urun_tipi("Eti Burçak"))


class YerEki(unittest.TestCase):
    def test_ekler(self):
        beklenen = {"BİM": "BİM'de", "Migros": "Migros'ta", "Gratis": "Gratis'te", "ŞOK": "ŞOK'ta", "n11": "n11'de",
                    "Trendyol": "Trendyol'da", "Rossmann": "Rossmann'da", "A101": "A101'de"}
        for ad, ek in beklenen.items():
            self.assertEqual(_yer_eki(ad), ek)


if __name__ == "__main__":
    unittest.main()
