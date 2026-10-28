"""Migros Sanal Market: kategori listelerini indirim yüzdesine göre sıralı çeker."""
from __future__ import annotations

import logging

from .. import http
from . import Urun

log = logging.getLogger(__name__)
API = "https://www.migros.com.tr/rest/search/screens/{kat}?sayfa={sayfa}&sirala=indirim-yuzdesine-gore"


def ayristir(veri: dict, kat: str) -> list[Urun]:
    sonuc = []
    for p in veri.get("data", {}).get("searchInfo", {}).get("storeProductInfos", []):
        if p.get("status") != "IN_SALE":
            continue
        fiyat, normal = p.get("shownPrice"), p.get("regularPrice")
        if not fiyat:
            continue
        gorsel = None
        if p.get("images"):
            u = p["images"][0].get("urls", {})
            gorsel = u.get("PRODUCT_HD") or u.get("PRODUCT_DETAIL")
        kart_sarti = bool(p.get("crmDiscountTags"))
        sonuc.append(Urun(
            kaynak="migros", kod=str(p.get("sku") or p["id"]), ad=p["name"].strip(),
            url=f"https://www.migros.com.tr/{p['prettyName']}",
            fiyat=fiyat / 100, liste_fiyat=(normal / 100) if normal and normal > fiyat else None,
            gorsel=gorsel, marka=(p.get("brand") or {}).get("name"),
            kategori=(p.get("category") or {}).get("name") or kat, tur="market",
            ekstra={"kart_sarti": kart_sarti, "birim_fiyat": p.get("unitPrice")},
        ))
    return sonuc


def topla(ayar: dict) -> list[Urun]:
    urunler: dict[str, Urun] = {}
    for kat in ayar.get("kategoriler", []):
        for sayfa in range(1, ayar.get("kategori_basina_sayfa", 2) + 1):
            try:
                veri = http.getir(API.format(kat=kat, sayfa=sayfa), json=True,
                                  bekle=ayar.get("sayfa_basina_bekleme_sn", 3))
            except Exception as e:
                log.warning("Migros %s/%s alınamadı: %s", kat, sayfa, e)
                break
            sayfa_urunleri = ayristir(veri, kat)
            for u in sayfa_urunleri:
                urunler.setdefault(u.id, u)
            # İndirime göre sıralı: indirimsiz ürünlere gelince dur.
            if not sayfa_urunleri or not any(u.liste_fiyat for u in sayfa_urunleri):
                break
    return list(urunler.values())
