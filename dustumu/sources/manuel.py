"""Elle eklenen fırsatlar (Trendyol, Hepsiburada, Amazon, A101...).

data/manuel_firsatlar.yaml dosyasından okunur. Panelden ya da GitHub'da dosyayı
düzenleyerek eklenebilir.
"""
from __future__ import annotations

import hashlib
from datetime import date

import yaml

from .. import config
from . import Urun

MARKET_KAYNAKLARI = {"a101", "bim", "sok", "migros", "carrefoursa"}


def oku() -> list[dict]:
    if not config.MANUEL_DOSYA.exists():
        return []
    with open(config.MANUEL_DOSYA, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("firsatlar") or []


def yaz(kayitlar: list[dict]) -> None:
    config.MANUEL_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    with open(config.MANUEL_DOSYA, "w", encoding="utf-8") as f:
        f.write("# Elle eklenen fırsatlar. Alanlar: ad, url, fiyat, eski_fiyat, kaynak, gorsel, bitis (YYYY-AA-GG)\n")
        yaml.safe_dump({"firsatlar": kayitlar}, f, allow_unicode=True, sort_keys=False)


def topla(ayar: dict) -> list[Urun]:
    bugun = config.simdi().date()
    sonuc = []
    for k in oku():
        if k.get("bitis") and date.fromisoformat(str(k["bitis"])) < bugun:
            continue
        kaynak = str(k.get("kaynak") or "diger").lower()
        kod = k.get("kod") or hashlib.md5(k["url"].encode()).hexdigest()[:10]
        sonuc.append(Urun(
            kaynak=kaynak, kod=str(kod), ad=k["ad"], url=k["url"], fiyat=float(k["fiyat"]),
            liste_fiyat=float(k["eski_fiyat"]) if k.get("eski_fiyat") else None,
            gorsel=k.get("gorsel"), kategori=k.get("kategori"),
            tur="market" if kaynak in MARKET_KAYNAKLARI else "eticaret",
            gecerlilik=k.get("gecerlilik"), bitis=str(k["bitis"]) if k.get("bitis") else None,
            ekstra={"manuel": True, "affiliate": bool(k.get("affiliate"))},
        ))
    return sonuc
