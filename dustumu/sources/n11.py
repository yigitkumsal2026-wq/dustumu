"""n11: arama sonuçlarındaki schema.org JSON-LD verisinden fiyat okur."""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .. import http
from . import Urun, tl

log = logging.getLogger(__name__)


def _jsonld_urunler(html: str):
    soup = BeautifulSoup(html, "lxml")
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            veri = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(veri, dict) and veri.get("@type") == "ItemList":
            for el in veri.get("itemListElement", []):
                item = el.get("item") or {}
                if item.get("@type") == "Product":
                    yield item


def ayristir(html: str, arama: str) -> list[Urun]:
    sonuc = []
    for p in _jsonld_urunler(html):
        teklif = p.get("offers") or {}
        if isinstance(teklif, list):
            teklif = teklif[0] if teklif else {}
        url = teklif.get("url") or p.get("url")
        if not url or "price" not in teklif:
            continue
        if teklif.get("availability", "").endswith("OutOfStock"):
            continue
        liste = None
        spec = teklif.get("priceSpecification")
        if isinstance(spec, dict) and spec.get("priceType", "").endswith("ListPrice"):
            liste = tl(str(spec.get("price")))
        m = re.search(r"-(\d+)(?:\?|$)", url)
        gorsel = p.get("image")
        if isinstance(gorsel, list):
            gorsel = gorsel[0] if gorsel else None
        sonuc.append(Urun(
            kaynak="n11", kod=m.group(1) if m else url, ad=p.get("name", "").strip(), url=url,
            fiyat=tl(str(teklif["price"])), liste_fiyat=liste, gorsel=gorsel,
            marka=(p.get("brand") or {}).get("name"), kategori=arama, tur="eticaret",
        ))
    return sonuc


def topla(ayar: dict) -> list[Urun]:
    urunler: dict[str, Urun] = {}
    for arama in ayar.get("aramalar", []):
        url = f"https://www.n11.com/arama?q={quote(arama)}&srt=DISCOUNT_RATE_DESC"
        try:
            html = http.getir(url, bekle=ayar.get("sayfa_basina_bekleme_sn", 4))
        except Exception as e:
            log.warning("n11 '%s' alınamadı: %s", arama, e)
            if isinstance(e, http.Engellendi):
                break
            continue
        for u in ayristir(html, arama):
            urunler.setdefault(u.id, u)
    return list(urunler.values())
