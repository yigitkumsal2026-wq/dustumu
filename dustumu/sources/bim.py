"""BİM Aktüel Ürünler: kataloglar tarihleriyle gelir (indirim günleri buradan çıkar)."""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from .. import config, http
from . import Urun, tl, tr_baslik

log = logging.getLogger(__name__)
KOK = "https://www.bim.com.tr"
SAYFA = KOK + "/Categories/100/aktuel-urunler.aspx"
AYLAR = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6, "temmuz": 7,
         "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}


def etiket_tarihi(etiket: str, bugun: date) -> tuple[date, date | None] | None:
    """'30 Ekim Cuma' -> (30 Eki, None); '24-30 Ekim' -> (24 Eki, 30 Eki)."""
    m = re.search(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)", etiket)
    if not m:
        return None
    ay = AYLAR.get(m.group(3).lower().replace("i̇", "i"))
    if not ay:
        return None
    yil = bugun.year + (1 if ay < bugun.month - 6 else 0) - (1 if ay > bugun.month + 6 else 0)
    bas = date(yil, ay, int(m.group(1)))
    bit = date(yil, ay, int(m.group(2))) if m.group(2) else None
    return bas, bit


def katalog_listesi(html: str, bugun: date) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    katalog = {}
    for a in soup.select("a[href*='Bim_AktuelTarihKey']"):
        m = re.search(r"Bim_AktuelTarihKey=(\d+)", a["href"])
        etiket = a.get_text(" ", strip=True)
        t = etiket_tarihi(etiket, bugun)
        if m and t and m.group(1) not in katalog:
            katalog[m.group(1)] = {"anahtar": m.group(1), "etiket": etiket, "baslangic": t[0], "bitis": t[1]}
    return sorted(katalog.values(), key=lambda k: k["baslangic"])


def urunleri_ayristir(html: str, katalog: dict) -> list[Urun]:
    soup = BeautifulSoup(html, "lxml")
    sonuc = []
    for p in soup.select(".product"):
        baslik = p.select_one(".title")
        tam = p.select_one(".quantify")
        if not (baslik and tam):
            continue
        kusur = p.select_one(".kusurArea .number")
        try:
            fiyat = tl(tam.get_text(strip=True) + (kusur.get_text(strip=True) if kusur else "00"))
        except ValueError:
            continue
        link = p.select_one("a[href*='aktuel']")
        img = p.select_one("img.img-fluid")
        alt = p.select_one(".subTitle")
        ad = " ".join(x for x in [alt.get_text(" ", strip=True) if alt else "", baslik.get_text(" ", strip=True)] if x)
        href = link["href"] if link else SAYFA
        gorsel = img.get("src") if img else None
        if gorsel:
            gorsel = gorsel.replace("_kucuk_", "_buyuk_") if "_kucuk_" in gorsel else gorsel
        # BİM fiyatın bitiş tarihini vermez: aktüel ürünler stoklarla sınırlıdır, ~7 gün sayıyoruz.
        bitis = katalog["bitis"] or (katalog["baslangic"] + timedelta(days=7))
        sonuc.append(Urun(
            kaynak="bim", kod=re.sub(r"\W+", "-", href.strip("/"))[-80:], ad=tr_baslik(ad),
            url=KOK + href if href.startswith("/") else href, fiyat=fiyat, gorsel=gorsel, tur="market",
            gecerlilik=katalog["etiket"], bitis=bitis.isoformat(),
            ekstra={"baslangic": katalog["baslangic"].isoformat()},
        ))
    return sonuc


def topla(ayar: dict) -> list[Urun]:
    bugun = config.simdi().date()
    ana = http.getir(SAYFA, bekle=3)
    kataloglar = [k for k in katalog_listesi(ana, bugun)
                  if bugun - timedelta(days=3) <= k["baslangic"] <= bugun + timedelta(days=7)]
    urunler: dict[str, Urun] = {}
    for k in kataloglar:
        try:
            html = http.getir(f"{SAYFA}?top=1&Bim_AktuelTarihKey={k['anahtar']}", bekle=3)
        except Exception as e:
            log.warning("BİM katalog %s alınamadı: %s", k["etiket"], e)
            continue
        for u in urunleri_ayristir(html, k):
            urunler.setdefault(u.id, u)
    return list(urunler.values())


def takvim(bugun: date | None = None) -> list[dict]:
    """Yaklaşan BİM aktüel günleri (haftalık takvim gönderisi için)."""
    bugun = bugun or config.simdi().date()
    try:
        return [k for k in katalog_listesi(http.getir(SAYFA, bekle=3), bugun)
                if bugun <= k["baslangic"] <= bugun + timedelta(days=7)]
    except Exception as e:
        log.warning("BİM takvimi alınamadı: %s", e)
        return []
