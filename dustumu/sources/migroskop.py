"""Migroskop dijital kataloğu: sayfadaki ürün kartları (migroskop.migros.com.tr/migroskop).

Katalogda eski fiyat yoktur; "indirimli" ürünlerde Money'siz ve Money'li iki fiyat yazar. Katalog
fiyatları Money veya Money Bonus ile geçerlidir, bu yüzden liste_fiyat Money'siz fiyattır.
Tek fiyatlı (raf) ürünlerde indirim bilinmediği için paylaşılmazlar; kampanya rozetli ürünlerde
fiyat olmadığı için kayda alınmazlar. Reklam sayfalarındaki fiyatlar sadece görseldedir, okunmaz.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .. import config, http
from . import Urun, tl

log = logging.getLogger(__name__)
URL = "https://migroskop.migros.com.tr/migroskop"
AYLAR = {"OCAK": (1, "Ocak"), "SUBAT": (2, "Şubat"), "ŞUBAT": (2, "Şubat"), "MART": (3, "Mart"), "NISAN": (4, "Nisan"),
         "NİSAN": (4, "Nisan"), "MAYIS": (5, "Mayıs"), "HAZIRAN": (6, "Haziran"), "TEMMUZ": (7, "Temmuz"),
         "AGUSTOS": (8, "Ağustos"), "AĞUSTOS": (8, "Ağustos"), "EYLUL": (9, "Eylül"), "EYLÜL": (9, "Eylül"),
         "EKIM": (10, "Ekim"), "EKİM": (10, "Ekim"), "KASIM": (11, "Kasım"), "ARALIK": (12, "Aralık")}
_DONEM = re.compile(r"(\d{1,2})(?:\s+([A-ZÇĞİÖŞÜ]+))?-(\d{1,2})\s+([A-ZÇĞİÖŞÜ]+)\s+MIGROSKOP")


def donem(html: str, bugun: date) -> tuple[str, str] | None:
    """Reklam görsellerinin adından: ('22 Ekim-4 Kasım', '2026-11-04'). İlk geçen dönem güncel sayıdır."""
    m = _DONEM.search(html)
    if not m or m.group(4) not in AYLAR or (m.group(2) and m.group(2) not in AYLAR):
        return None
    ay, ay_ad = AYLAR[m.group(4)]
    yil = bugun.year + 1 if ay < bugun.month - 6 else bugun.year
    bas = f"{m.group(1)} {AYLAR[m.group(2)][1]}" if m.group(2) else m.group(1)
    return f"{bas}-{m.group(3)} {ay_ad}", date(yil, ay, int(m.group(3))).isoformat()


def _fiyat(kutu) -> float:
    return tl("".join(s.get_text(strip=True) for s in kutu.select(".first span, .second span:first-child")))


def ayristir(html: str, bugun: date) -> list[Urun]:
    d = donem(html, bugun)
    if not d:
        log.warning("Migroskop dönemi okunamadı, ürünler alınmadı.")
        return []
    gecerlilik, bitis = d
    sonuc: dict[str, Urun] = {}
    for sayfa in BeautifulSoup(html, "lxml").select("div.page"):
        no = sayfa.select_one(".pn")
        for k in sayfa.select("div.product[data-pid]"):
            baslik, img = k.select_one("h1.title"), k.select_one(".image img")
            kutu = k.select_one(".price-content[name]")
            if not (baslik and kutu):
                continue
            fiyatlar = kutu.select(".price-text")
            money = kutu.select_one("h6") and "MONEY" in kutu.select_one("h6").get_text().upper()
            try:
                if len(fiyatlar) == 2 and money:
                    normal, fiyat = _fiyat(fiyatlar[0]), _fiyat(fiyatlar[1])
                elif len(fiyatlar) == 1:
                    normal, fiyat = None, _fiyat(fiyatlar[0])
                else:
                    continue
            except ValueError:
                continue
            u = Urun(
                kaynak="migroskop", kod=k["data-pid"], ad=re.sub(r"\s+", " ", baslik.get_text(" ", strip=True)),
                url=f"{URL}#sayfa/{no.get('data-page-number')}" if no else URL, fiyat=fiyat,
                liste_fiyat=normal if normal and normal > fiyat else None,
                gorsel=img.get("src") if img else None, tur="market", gecerlilik=gecerlilik, bitis=bitis,
            )
            sonuc.setdefault(u.id, u)
    return list(sonuc.values())


def topla(ayar: dict) -> list[Urun]:
    return ayristir(http.getir(URL, bekle=3, headers=http.BOT_BASLIK), config.simdi().date())
