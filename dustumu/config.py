"""Ayarların ve klasör yollarının tek merkezi."""
from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv opsiyonel
    load_dotenv = None

KOK = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(KOK / ".env")

# Durum klasörü: veritabanı + üretilen site + görseller.
# GitHub Actions'ta "veri" dalından geri yüklenir.
DURUM = Path(os.environ.get("DURUM_KLASORU", KOK / "durum")).resolve()
DB_YOLU = DURUM / "dustumu.db"
SITE = DURUM / "site"
GORSEL = SITE / "g"
FONTLAR = KOK / "assets" / "fonts"
MANUEL_DOSYA = KOK / "data" / "manuel_firsatlar.yaml"
KARA_LISTE_DOSYA = KOK / "data" / "kara_liste.yaml"


@lru_cache
def ayarlar() -> dict:
    with open(KOK / "config.yaml", encoding="utf-8") as f:
        a = yaml.safe_load(f)
    # Ortam değişkeni site adresini ezebilir (Actions'ta otomatik ayarlanır).
    if os.environ.get("SITE_URL"):
        a["marka"]["site_url"] = os.environ["SITE_URL"]
    a["marka"]["site_url"] = a["marka"]["site_url"].rstrip("/")
    # GitHub'da Settings > Variables'tan INSTAGRAM_AKTIF=true/false ile açıp kapatılabilir.
    if os.environ.get("INSTAGRAM_AKTIF"):
        a["yayin"]["instagram_aktif"] = os.environ["INSTAGRAM_AKTIF"].strip().lower() in ("1", "true", "evet")
    if os.environ.get("YORUM_DM_AKTIF"):
        a["yorum_dm"]["aktif"] = os.environ["YORUM_DM_AKTIF"].strip().lower() in ("1", "true", "evet")
    return a


def tz() -> ZoneInfo:
    return ZoneInfo(ayarlar()["marka"]["zaman_dilimi"])


def simdi() -> datetime:
    return datetime.now(tz())


def env(ad: str, varsayilan: str = "") -> str:
    return os.environ.get(ad, varsayilan).strip()


def klasorleri_hazirla() -> None:
    for k in (DURUM, SITE, GORSEL, MANUEL_DOSYA.parent):
        k.mkdir(parents=True, exist_ok=True)
