"""Gratis: kategori sayfasına gömülü ürün verisi (Next.js akışı, self.__next_f).

Fiyatlar kuruş cinsindendir. Gratis Kart fiyatı (promotionPrice) herkese açık olmadığı için
kullanılmaz; kartsız fiyat ve fiyat geçmişi esas alınır.
"""
from __future__ import annotations

import json
import logging
import re

from .. import http
from . import Urun

log = logging.getLogger(__name__)
KOK = "https://www.gratis.com"
_cozucu = json.JSONDecoder()


def _urun_listesi(html: str) -> list[dict]:
    metin = "".join(json.loads(m.group(1)) for m in
                    re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html))
    i = metin.find('"products":[')
    return _cozucu.raw_decode(metin, i + len('"products":'))[0] if i >= 0 else []


def ayristir(html: str, kategori: str | None = None) -> list[Urun]:
    sonuc = []
    for p in _urun_listesi(html):
        a, fiyatlar = p.get("attributes") or {}, p.get("prices") or {}
        fiyat, normal = fiyatlar.get("discountedPrice"), fiyatlar.get("normalPrice")
        if not (p.get("id") and a.get("displayName") and p.get("shareLink") and fiyat):
            continue
        if not p.get("isActive") or "OUT" in str(p.get("stockStatus")).upper():
            continue
        gorseller = p.get("imageUrls") or []
        sonuc.append(Urun(
            kaynak="gratis", kod=str(p["id"]), ad=a["displayName"].strip(), url=p["shareLink"], fiyat=fiyat / 100,
            liste_fiyat=normal / 100 if normal and normal > fiyat else None,
            gorsel=gorseller[0].get("fileUrl") if gorseller else None, marka=a.get("brand"), kategori=kategori,
        ))
    return sonuc


def topla(ayar: dict) -> list[Urun]:
    urunler: dict[str, Urun] = {}
    for yol in ayar.get("sayfalar", []):
        for sayfa in range(1, ayar.get("sayfa_basina_derinlik", 1) + 1):
            url = f"{KOK}{yol}" + (f"?page={sayfa}" if sayfa > 1 else "")
            try:
                html = http.getir(url, bekle=ayar.get("sayfa_basina_bekleme_sn", 4), headers=http.BOT_BASLIK)
            except Exception as e:
                log.warning("Gratis %s alınamadı: %s", url, e)
                if isinstance(e, http.Engellendi):
                    return list(urunler.values())
                break
            yeni = [u for u in ayristir(html, yol.strip("/")) if u.id not in urunler]
            for u in yeni:
                urunler[u.id] = u
            if not yeni:
                break
    return list(urunler.values())
