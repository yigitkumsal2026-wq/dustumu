"""ŞOK Market: "Haftanın Fırsatları" sayfasındaki ürün kartları."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import http
from . import Urun, tl

log = logging.getLogger(__name__)
KOK = "https://www.sokmarket.com.tr"


def _buyuk_gorsel(src: str | None) -> str | None:
    if not src:
        return None
    # CDN dönüşümünü kaldırıp orijinal dosyayı al (dönüşüm sadece boşluk ekleyerek büyütüyor).
    return re.sub(r"/cdn-cgi/image/[^/]+", "", src)


def ayristir(html: str) -> list[Urun]:
    soup = BeautifulSoup(html, "lxml")
    sonuc = []
    for a in soup.select("a[href*='-p-']"):
        fiyat_el = a.select_one('[data-testid="discountedPrice"]')
        eski_el = a.select_one('[data-testid="price"]')
        baslik = a.select_one("h2")
        if not (eski_el and baslik):
            continue
        try:
            if fiyat_el:
                fiyat, eski = tl(fiyat_el.get_text()), tl(eski_el.get_text())
            else:
                fiyat, eski = tl(eski_el.get_text()), None
        except ValueError:
            continue
        href = a["href"]
        m = re.search(r"-p-(\d+)", href)
        img = a.select_one("img")
        sonuc.append(Urun(
            kaynak="sok", kod=m.group(1) if m else href, ad=baslik.get_text(" ", strip=True),
            url=KOK + href if href.startswith("/") else href, fiyat=fiyat,
            liste_fiyat=eski if eski and eski > fiyat else None,
            gorsel=_buyuk_gorsel(img.get("src") if img else None), tur="market",
            gecerlilik="Haftanın Fırsatları",
        ))
    return sonuc


def topla(ayar: dict) -> list[Urun]:
    urunler: dict[str, Urun] = {}
    for yol in ayar.get("sayfalar", []):
        for sayfa in range(1, 4):
            url = f"{KOK}{yol}" + (f"?page={sayfa}" if sayfa > 1 else "")
            try:
                bulunan = ayristir(http.getir(url, bekle=3))
            except Exception as e:
                log.warning("ŞOK %s alınamadı: %s", url, e)
                break
            yeni = [u for u in bulunan if u.id not in urunler]
            for u in yeni:
                urunler[u.id] = u
            if not yeni:  # sayfalama desteklenmiyorsa aynı ürünler döner
                break
    return list(urunler.values())
