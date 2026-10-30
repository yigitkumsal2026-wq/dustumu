"""Rossmann ve Gratis ayrıştırıcı testleri: python -m unittest discover tests"""
import json
import unittest

from dustumu.sources import gratis, rossmann


def _gratis_sayfa(urun: dict) -> str:
    parca = json.dumps(json.dumps({"products": [urun]}, separators=(",", ":")))
    return f"<script>self.__next_f.push([1,{parca}])</script>"


def _gratis_urun(**degisen) -> dict:
    u = {"id": "1", "isActive": True, "stockStatus": "MEDIUM", "shareLink": "https://www.gratis.com/x-p-1",
         "imageUrls": [{"fileUrl": "https://g/1.jpg"}], "attributes": {"displayName": "Ruj", "brand": "Flormar"},
         "prices": {"discountedPrice": 45900, "normalPrice": 45900, "promotionPrice": 22950}}
    return u | degisen


def _rossmann_sayfa(**degisen) -> str:
    u = {"name": "Ruj", "url_key": "ruj-p-sr1", "price": 99, "special_price": 99, "crm_price": "65.000000",
         "is_in_stock": 1, "image": "/a/b.jpeg", "brand": "Isana"} | degisen
    return '{"hits":[{"_id":"1","_source":' + json.dumps(u) + "}]}"


class Gratis(unittest.TestCase):
    def test_kart_fiyati_kullanilmaz(self):
        u = gratis.ayristir(_gratis_sayfa(_gratis_urun()))[0]
        self.assertEqual(u.fiyat, 459.0)
        self.assertIsNone(u.liste_fiyat)
        self.assertEqual(u.id, "gratis:1")

    def test_kartsiz_indirim_liste_fiyati_olur(self):
        fiyat = {"discountedPrice": 30000, "normalPrice": 45900, "promotionPrice": 20000}
        u = gratis.ayristir(_gratis_sayfa(_gratis_urun(prices=fiyat)))[0]
        self.assertEqual((u.fiyat, u.liste_fiyat), (300.0, 459.0))

    def test_stokta_olmayan_atlanir(self):
        self.assertEqual(gratis.ayristir(_gratis_sayfa(_gratis_urun(stockStatus="OUT_OF_STOCK"))), [])

    def test_veri_yoksa_bos(self):
        self.assertEqual(gratis.ayristir("<html></html>"), [])


class Rossmann(unittest.TestCase):
    def test_kart_fiyati_kullanilmaz(self):
        u = rossmann.ayristir(_rossmann_sayfa())[0]
        self.assertEqual(u.fiyat, 99.0)
        self.assertIsNone(u.liste_fiyat)
        self.assertEqual(u.id, "rossmann:sr1")
        self.assertEqual(u.url, "https://www.rossmann.com.tr/ruj-p-sr1")

    def test_stokta_olmayan_atlanir(self):
        self.assertEqual(rossmann.ayristir(_rossmann_sayfa(is_in_stock=0)), [])


if __name__ == "__main__":
    unittest.main()
