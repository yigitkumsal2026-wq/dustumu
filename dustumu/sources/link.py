"""Sadece linki verilen ürünün adını, görselini ve fiyatını ürün sayfasından okur.

Tek, normal bir istek atar (http.getir: robots.txt'e uyar). Site isteği reddederse
(bot koruması) korumayı aşmaya çalışmaz; o ürün için fiyatı elle yazmak gerekir.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse

from .. import http

ALANLAR = {"trendyol": "trendyol", "hepsiburada": "hepsiburada", "amazon": "amazon", "a101": "a101",
           "n11": "n11", "migros": "migros", "sokmarket": "sok", "bim": "bim", "carrefoursa": "carrefoursa",
           "teknosa": "teknosa", "mediamarkt": "mediamarkt", "boyner": "boyner", "lcw": "lcw"}


def kaynak_bul(url: str) -> str:
    alan = urlparse(url).netloc.lower()
    return next((k for parca, k in ALANLAR.items() if parca in alan), "diger")


def _jsonld_urun(html: str) -> dict:
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        for o in d if isinstance(d, list) else d.get("@graph", [d]):
            if isinstance(o, dict) and o.get("@type") == "Product":
                return o
    return {}


def _ilk_gorsel(img) -> str | None:
    if isinstance(img, list):
        return _ilk_gorsel(img[0]) if img else None
    if isinstance(img, dict):
        return _ilk_gorsel(img.get("contentUrl") or img.get("url"))
    return img


def _meta(html: str, ad: str) -> str | None:
    m = re.search(rf'<meta[^>]+property="{re.escape(ad)}"[^>]+content="([^"]+)"', html)
    return m.group(1) if m else None


def oku(url: str) -> dict:
    """{'ad','gorsel','fiyat','eski_fiyat','kaynak','kod','bitis'} döner; okunamazsa hata fırlatır."""
    html = http.getir(url, bekle=3)
    urun = _jsonld_urun(html)
    teklif = urun.get("offers") or {}
    if isinstance(teklif, list):
        teklif = teklif[0] if teklif else {}
    ad = urun.get("name") or _meta(html, "og:title")
    gorsel = _ilk_gorsel(urun.get("image")) or _meta(html, "og:image")
    fiyat = teklif.get("price") or teklif.get("lowPrice")
    eski = None
    bitis = (teklif.get("priceValidUntil") or "")[:10] or None

    # Trendyol: sayfada gösterilen satıcının (winnerVariant) satış ve üstü çizili fiyatı
    m = re.search(r'"winnerVariant":\{.*?"price":\{.*?"discountedPrice":\{"value":([\d.]+).*?'
                  r'"originalPrice":\{"value":([\d.]+)', html, re.S)
    if m:
        fiyat, eski = m.group(1), m.group(2)

    if not (ad and fiyat):
        raise ValueError("sayfada ürün adı/fiyatı bulunamadı")
    fiyat = float(fiyat)
    eski = float(eski) if eski and float(eski) > fiyat else None
    yol = urlparse(url)
    return {"ad": re.sub(r"\s+-\s+Fiyatı.*$", "", ad).strip(), "gorsel": gorsel, "fiyat": fiyat,
            "eski_fiyat": eski, "kaynak": kaynak_bul(url), "bitis": bitis,
            "kod": hashlib.md5(f"{yol.netloc}{yol.path}".encode()).hexdigest()[:10]}
