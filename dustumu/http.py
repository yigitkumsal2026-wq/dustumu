"""Nazik HTTP istemcisi: robots.txt'e uyar, siteye yüklenmez, hata olursa tekrar dener.

Bot koruması (Cloudflare/Akamai vb.) olan sitelerde korumayı aşmaya çalışmaz;
403/429 alınırsa o kaynak o çalıştırmada atlanır.
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

_oturum = requests.Session()
_oturum.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5"})
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_son_istek: dict[str, float] = {}


class Engellendi(Exception):
    """Site isteği reddetti (bot koruması / hız sınırı) veya robots.txt izin vermiyor."""


def _robots_izin(url: str) -> bool:
    p = urlparse(url)
    kok = f"{p.scheme}://{p.netloc}"
    if kok not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _oturum.get(kok + "/robots.txt", timeout=15)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                _robots[kok] = rp
            else:
                _robots[kok] = None  # robots.txt yok -> kısıtlama yok
        except requests.RequestException:
            _robots[kok] = None
    rp = _robots[kok]
    return True if rp is None else rp.can_fetch("*", url)


def getir(url: str, *, bekle: float = 2.0, json: bool = False, deneme: int = 3, **kw):
    if not _robots_izin(url):
        raise Engellendi(f"robots.txt izin vermiyor: {url}")
    alan = urlparse(url).netloc
    gecen = time.time() - _son_istek.get(alan, 0)
    if gecen < bekle:
        time.sleep(bekle - gecen)
    son_hata: Exception | None = None
    for i in range(deneme):
        try:
            r = _oturum.get(url, timeout=30, **kw)
            _son_istek[alan] = time.time()
            if r.status_code in (401, 403, 429):
                raise Engellendi(f"{alan} isteği reddetti ({r.status_code})")
            r.raise_for_status()
            return r.json() if json else r.text
        except Engellendi:
            raise
        except (requests.RequestException, ValueError) as e:
            son_hata = e
            time.sleep(2 * (i + 1))
    raise son_hata  # type: ignore[misc]


def indir(url: str) -> bytes:
    r = _oturum.get(url, timeout=30)
    r.raise_for_status()
    return r.content
