"""Planlanan gönderileri Instagram'a (ve isteğe bağlı Telegram'a) gönderir."""
from __future__ import annotations

import json
import logging
import time

import requests

from . import config, instagram, telegram
from .sources import affiliate_link

log = logging.getLogger(__name__)


def _url(ad: str) -> str:
    return f"{config.ayarlar()['marka']['site_url']}/g/{ad}"


def _yayinda_mi(url: str, sure: int = 240) -> bool:
    """GitHub Pages dağıtımı birkaç dakika sürebilir; görsel erişilebilir olana kadar bekle."""
    bas = time.time()
    while time.time() - bas < sure:
        try:
            r = requests.head(url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith(("image/", "video/")):
                return True
        except requests.RequestException:
            pass
        time.sleep(10)
    return False


def bekleyenleri_yayinla(c) -> dict:
    y = config.ayarlar()["yayin"]
    sonuc = {"yayinlandi": 0, "deneme": 0, "hata": 0}
    bekleyen = c.execute("SELECT * FROM gonderiler WHERE durum='planlandi' ORDER BY id").fetchall()
    if not bekleyen:
        return sonuc
    if y["instagram_aktif"]:
        instagram.token_yenile(c)
        try:
            k = instagram.kota(c)
            log.info("Instagram API kotası: %s / %s", k.get("quota_usage"), (k.get("config") or {}).get("quota_total"))
            if k.get("quota_usage", 0) >= (k.get("config") or {}).get("quota_total", 100) - 5:
                log.warning("API kotası dolmak üzere, yayın ertelendi.")
                return sonuc
        except instagram.IGHata as e:
            log.warning("Kota okunamadı: %s", e)

    for g in bekleyen:
        gorseller = json.loads(g["gorseller"])
        simdi = config.simdi().isoformat(timespec="seconds")
        if not y["instagram_aktif"]:
            c.execute("UPDATE gonderiler SET durum='deneme', yayin_zamani=? WHERE id=?", (simdi, g["id"]))
            c.commit()
            sonuc["deneme"] += 1
            if telegram.taslak_gonder([config.GORSEL / a for a in gorseller], g["tur"], g["aciklama"]):
                sonuc["taslak"] = sonuc.get("taslak", 0) + 1
            continue
        try:
            urller = [_url(a) for a in gorseller]
            if not _yayinda_mi(urller[-1]):
                raise instagram.IGHata(f"Görsel henüz yayında değil: {urller[-1]}")
            if g["tur"] == "carousel":
                ig_id = instagram.carousel_paylas(c, urller, g["aciklama"])
            elif g["tur"] == "reel":
                ig_id = instagram.reel_paylas(c, urller[0], g["aciklama"])
            elif g["tur"] == "hikaye":
                ig_id = instagram.hikaye_paylas(c, urller[0])
            else:
                ig_id = instagram.gorsel_paylas(c, urller[0], g["aciklama"])
            c.execute("UPDATE gonderiler SET durum='yayinlandi', yayin_zamani=?, ig_id=? WHERE id=?",
                      (simdi, ig_id, g["id"]))
            c.commit()
            sonuc["yayinlandi"] += 1
            log.info("Yayınlandı: gönderi %s (%s) -> %s", g["id"], g["tur"], ig_id)
            _telegrama_yansit(c, g)
            time.sleep(20)  # aynı çalıştırmadaki gönderiler (feed + hikâye) arasında kısa ara
        except Exception as e:
            c.execute("UPDATE gonderiler SET durum='hata', hata=? WHERE id=?", (str(e)[:500], g["id"]))
            c.commit()
            sonuc["hata"] += 1
            log.error("Gönderi %s yayınlanamadı: %s", g["id"], e)
            telegram.hata_bildir(f"Gönderi {g['id']} yayınlanamadı: {e}")
    return sonuc


def _telegrama_yansit(c, g) -> None:
    if g["tur"] not in ("tekli", "carousel"):
        return
    kodlar = json.loads(g["kodlar"])
    if not kodlar:
        return
    r = c.execute("SELECT u.kaynak, u.url FROM firsatlar f JOIN urunler u ON u.id=f.urun_id WHERE f.kod=?",
                  (kodlar[0],)).fetchone()
    if not r:
        return
    link = (affiliate_link(r["kaynak"], r["url"]) if g["tur"] == "tekli"
            else config.ayarlar()["marka"]["site_url"])
    telegram.firsat_gonder(config.GORSEL / json.loads(g["gorseller"])[0], g["aciklama"], link)


def dm_metni_bul(c):
    """Instagram medya id'si -> o gönderideki fırsatların linkleri (DM metni)."""
    site = config.ayarlar()["marka"]["site_url"]

    def bul(media_id: str) -> str | None:
        g = c.execute("SELECT kodlar FROM gonderiler WHERE ig_id=?", (media_id,)).fetchone()
        if not g:
            return None
        kodlar = json.loads(g["kodlar"])
        if not kodlar:
            return f"Merhaba! 👋 Tüm güncel fırsatlar burada: {site}"
        satirlar = ["Merhaba! 👋 İstediğin fırsat linki:"]
        for k in kodlar[:6]:
            r = c.execute("SELECT u.ad FROM firsatlar f JOIN urunler u ON u.id=f.urun_id WHERE f.kod=?", (k,)).fetchone()
            if r:
                satirlar.append(f"• {r['ad'][:60]} → {site}/k/{k}")
        satirlar.append("Fiyatlar değişebilir, hızlı davranmanı öneririz. 🛒")
        return "\n".join(satirlar)
    return bul
