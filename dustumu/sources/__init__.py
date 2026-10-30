"""İndirim kaynakları. Her kaynak `topla(ayar) -> list[Urun]` fonksiyonu sunar."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Urun:
    kaynak: str               # n11, migros, sok, bim, trendyol...
    kod: str                  # kaynaktaki benzersiz kimlik
    ad: str
    url: str
    fiyat: float
    liste_fiyat: float | None = None
    gorsel: str | None = None
    marka: str | None = None
    kategori: str | None = None
    tur: str = "eticaret"     # market | eticaret
    gecerlilik: str | None = None
    bitis: str | None = None  # YYYY-MM-DD
    ekstra: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.kaynak}:{self.kod}"


KAYNAK_ADLARI = {
    "n11": "n11", "migros": "Migros", "sok": "ŞOK", "bim": "BİM", "a101": "A101",
    "trendyol": "Trendyol", "hepsiburada": "Hepsiburada", "amazon": "Amazon",
    "carrefoursa": "CarrefourSA", "rossmann": "Rossmann", "gratis": "Gratis", "migroskop": "Migroskop",
    "diger": "Fırsat",
}

# Görsellerdeki mağaza rozet renkleri (arka plan, yazı)
KAYNAK_RENK = {
    "n11": ("#5B2D8E", "#FFFFFF"), "migros": ("#FF7F00", "#FFFFFF"),
    "sok": ("#FFD400", "#1A1A1A"), "bim": ("#E30613", "#FFFFFF"),
    "a101": ("#00A0E3", "#FFFFFF"), "trendyol": ("#F27A1A", "#FFFFFF"),
    "hepsiburada": ("#FF6000", "#FFFFFF"), "amazon": ("#232F3E", "#FF9900"),
    "carrefoursa": ("#004E9F", "#FFFFFF"), "rossmann": ("#C8102E", "#FFFFFF"),
    "gratis": ("#E6007E", "#FFFFFF"), "migroskop": ("#FF7F00", "#FFFFFF"), "diger": ("#111111", "#FFFFFF"),
}


def tl(metin: str) -> float:
    """'4.990,00 ₺' / '12599' / '6369.02' -> float."""
    s = re.sub(r"[^\d,.]", "", metin or "")
    if not s:
        raise ValueError(f"fiyat yok: {metin!r}")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.search(r"\.\d{3}$", s):
        s = s.replace(".", "")
    return float(s)


def affiliate_link(kaynak: str, url: str) -> str:
    """config.yaml'daki affiliate şablonunu uygular: '{url}?tag=x' -> url zaten '?' içeriyorsa '&' kullanır."""
    from .. import config
    sablon = (config.ayarlar().get("affiliate") or {}).get(kaynak) or ""
    if not sablon or "{url}" not in sablon:
        return url
    sonuc = sablon.replace("{url}", url)
    if "?" in url:
        bas, son = sonuc.split(url, 1)
        sonuc = bas + url + son.replace("?", "&", 1)
    return sonuc


def tr_baslik(metin: str) -> str:
    """'KUMTEL 11 DİLİM ISITICI' -> 'Kumtel 11 Dilim Isıtıcı' (Python'un title()'ı Türkçede bozuk)."""
    def kucuk(s: str) -> str:
        return s.replace("I", "ı").replace("İ", "i").lower()

    def kelime(k: str) -> str:
        k = kucuk(k)
        if not k:
            return k
        ilk = {"i": "İ", "ı": "I"}.get(k[0], k[0].upper())
        return ilk + k[1:]
    return " ".join(kelime(k) for k in metin.split())


def tum_kaynaklar():
    from . import bim, gratis, manuel, migros, migroskop, n11, rossmann, sok
    return {"n11": n11, "migros": migros, "migroskop": migroskop, "sok": sok, "bim": bim, "rossmann": rossmann,
            "gratis": gratis, "manuel": manuel}
