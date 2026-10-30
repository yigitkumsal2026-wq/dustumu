"""Rossmann: kategori sayfasına gömülü ürün JSON'u (_source).

Listede üstü çizili fiyat yok; indirim, botun kendi fiyat geçmişiyle doğrulanır.
Rossmann Kart fiyatı (crm_price) herkese açık olmadığı için kullanılmaz.
"""
from __future__ import annotations

import json
import logging
import re

from .. import http
from . import Urun

log = logging.getLogger(__name__)
KOK = "https://www.rossmann.com.tr"
GORSEL = "https://cdn.rossmann.com.tr/media/catalog/product"
_cozucu = json.JSONDecoder()


def ayristir(html: str, kategori: str | None = None) -> list[Urun]:
    sonuc: dict[str, Urun] = {}
    for m in re.finditer(r'"_source":\{', html):
        try:
            p, _ = _cozucu.raw_decode(html, m.end() - 1)
        except ValueError:
            continue
        anahtar = p.get("url_key")
        fiyat = float(p.get("special_price") or p.get("price") or 0)
        if not (anahtar and p.get("name") and fiyat > 0 and p.get("is_in_stock")):
            continue
        u = Urun(
            kaynak="rossmann", kod=anahtar.rsplit("-p-", 1)[-1], ad=p["name"].strip(), url=f"{KOK}/{anahtar}",
            fiyat=fiyat, gorsel=GORSEL + p["image"] if p.get("image") else None,
            marka=p.get("brand"), kategori=kategori,
        )
        sonuc.setdefault(u.id, u)
    return list(sonuc.values())


def topla(ayar: dict) -> list[Urun]:
    urunler: dict[str, Urun] = {}
    for yol in ayar.get("sayfalar", []):
        for sayfa in range(1, ayar.get("sayfa_basina_derinlik", 1) + 1):
            url = f"{KOK}{yol}" + (f"?p={sayfa}" if sayfa > 1 else "")
            try:
                html = http.getir(url, bekle=ayar.get("sayfa_basina_bekleme_sn", 4), headers=http.BOT_BASLIK)
            except Exception as e:
                log.warning("Rossmann %s alınamadı: %s", url, e)
                if isinstance(e, http.Engellendi):
                    return list(urunler.values())
                break
            yeni = [u for u in ayristir(html, yol.strip("/")) if u.id not in urunler]
            for u in yeni:
                urunler[u.id] = u
            if not yeni:
                break
    return list(urunler.values())
