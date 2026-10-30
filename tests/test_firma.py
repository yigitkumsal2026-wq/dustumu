"""Tek firma kuralı testleri: python -m unittest discover tests"""
import unittest

from dustumu.planner import _firma_sec, _yer_eki


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


class YerEki(unittest.TestCase):
    def test_ekler(self):
        beklenen = {"BİM": "BİM'de", "Migros": "Migros'ta", "Gratis": "Gratis'te", "ŞOK": "ŞOK'ta", "n11": "n11'de",
                    "Trendyol": "Trendyol'da", "Rossmann": "Rossmann'da", "A101": "A101'de"}
        for ad, ek in beklenen.items():
            self.assertEqual(_yer_eki(ad), ek)


if __name__ == "__main__":
    unittest.main()
