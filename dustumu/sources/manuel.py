"""Elle eklenen fırsatlar (Trendyol, Hepsiburada, Amazon, A101...).

data/manuel_firsatlar.yaml dosyasından okunur. Panelden ya da GitHub'da dosyayı
düzenleyerek eklenebilir.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date

import yaml

from .. import config
from . import Urun, link

log = logging.getLogger(__name__)
MARKET_KAYNAKLARI = {"a101", "bim", "sok", "migros", "carrefoursa"}
LINK_DOSYA = config.MANUEL_DOSYA.parent / "linkler.txt"


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
    return sonuc + linklerden(bugun)


def linkler() -> list[tuple[str, str | None]]:
    """data/linkler.txt: her satırda bir link, istersen yanında bitiş tarihi (2026-11-30)."""
    if not LINK_DOSYA.exists():
        return []
    sonuc = []
    for satir in LINK_DOSYA.read_text(encoding="utf-8").splitlines():
        parcalar = satir.split("#")[0].split()
        if parcalar and parcalar[0].startswith("http"):
            tarih = next((p for p in parcalar[1:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)), None)
            sonuc.append((parcalar[0], tarih))
    return sonuc


def linklerden(bugun: date) -> list[Urun]:
    sonuc = []
    for url, tarih in linkler():
        if tarih and date.fromisoformat(tarih) < bugun:
            continue
        try:
            b = link.oku(url)
        except Exception as e:
            log.warning("Link okunamadı (fiyatı manuel_firsatlar.yaml'a elle yaz): %s — %s", url, e)
            continue
        esik = config.ayarlar()["dogrulama"]["min_gercek_indirim"]
        if not b["eski_fiyat"] or (b["eski_fiyat"] - b["fiyat"]) / b["eski_fiyat"] * 100 < esik:
            log.info("Linkteki ürün şu an indirimde değil (ya da indirim %%%d altı), atlandı: %s", esik, b["ad"])
            continue
        sonuc.append(Urun(
            kaynak=b["kaynak"], kod=b["kod"], ad=b["ad"], url=url, fiyat=b["fiyat"], liste_fiyat=b["eski_fiyat"],
            gorsel=b["gorsel"], tur="market" if b["kaynak"] in MARKET_KAYNAKLARI else "eticaret",
            bitis=tarih or b["bitis"], ekstra={"manuel": True, "link": True},
        ))
    log.info("linkler.txt: %d link, %d indirimli ürün okundu", len(linkler()), len(sonuc))
    return sonuc
