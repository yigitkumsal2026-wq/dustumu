"""Reels stil ve üretim testleri: python -m unittest discover tests"""
import tempfile
import unittest
import wave
from pathlib import Path

from dustumu import reel, ses


class Stil(unittest.TestCase):
    def test_art_arda_her_parca_degisir(self):
        for no in range(200):
            a, b = reel.stil_sec(no), reel.stil_sec(no + 1)
            for parca in ("p", "rozet", "blok", "giris", "ayna"):
                self.assertNotEqual(a[parca], b[parca], (no, parca))

    def test_hareket_ve_desen_cogunlukla_degisir(self):
        for parca in ("rozet_hareket", "desen"):
            ayni = sum(reel.stil_sec(n)[parca] == reel.stil_sec(n + 1)[parca] for n in range(200))
            self.assertLess(ayni, 60, parca)

    def test_kombinasyonlar_gec_tekrarlar(self):
        anahtar = lambda s: (s["p"]["ad"], s["rozet"], s["blok"], s["rozet_hareket"], s["giris"], s["desen"], s["ayna"])
        self.assertGreater(len({anahtar(reel.stil_sec(n)) for n in range(60)}), 50)


class Uretim(unittest.TestCase):
    def test_ses_sessiz_degil_ve_sure_dogru(self):
        with tempfile.TemporaryDirectory() as g:
            yol = ses.uret(Path(g) / "s.wav", 2.0, [("pop", 0.1), ("ding", 0.5), ("ufleme", 1.0)], 3)
            with wave.open(str(yol)) as w:
                self.assertEqual(w.getnframes(), 2 * ses.ORNEK)
                veri = w.readframes(w.getnframes())
        self.assertGreater(max(veri), 0)

    def test_gorselsiz_aktuel_de_video_uretir(self):
        f = {"kod": 1, "ad": "Deneme Ürün", "fiyat": 99.5, "eski_fiyat": 99.5, "indirim": 0, "guven": "aktuel",
             "kaynak": "bim", "gorsel": None, "gecerlilik": "1 Kasım Pazar"}
        with tempfile.TemporaryDirectory() as g:
            h = reel.uret([f], ("BUGÜN", "BİM'DE", "NE DÜŞTÜ?"), Path(g) / "r.mp4", stil_no=2)
            self.assertGreater(h.stat().st_size, 10000)


if __name__ == "__main__":
    unittest.main()
