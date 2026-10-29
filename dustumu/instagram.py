"""Instagram Graph API (Instagram Login) ile yayın + yorum->DM.

Resmi API kullanır: şifre istemez, hesabı riske atan "otomatik tıklama" botu değildir.
Gerekenler (README'de adım adım): Profesyonel (İşletme/İçerik Üretici) hesap,
Meta geliştirici uygulaması, IG_USER_ID ve uzun ömürlü IG_ACCESS_TOKEN.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time
from datetime import datetime, timedelta

import requests

from . import config
from .db import kv_al, kv_yaz

log = logging.getLogger(__name__)


class IGHata(Exception):
    pass


def _facebook() -> bool:
    """IG_GIRIS=facebook: Facebook sayfasına bağlı hesap + süresiz sayfa token'ı (scripts/fb_kurulum.py)."""
    return config.env("IG_GIRIS", "instagram").lower() == "facebook"


def _api() -> str:
    alan = "graph.facebook.com" if _facebook() else "graph.instagram.com"
    return f"https://{alan}/{config.env('IG_API_VERSION', 'v23.0')}"


# ------------------------------------------------------------------ token
def _fernet():
    anahtar = config.env("DURUM_ANAHTARI")
    if not anahtar:
        return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(anahtar.encode()).digest()))


def token(c) -> str:
    """Önce veritabanındaki (yenilenmiş, şifreli) token, yoksa ortam değişkeni."""
    f = _fernet()
    kayit = kv_al(c, "ig_token")
    if f and kayit:
        try:
            return f.decrypt(kayit["sifreli"].encode()).decode()
        except Exception:
            log.warning("Kayıtlı token çözülemedi, ortam değişkeni kullanılacak.")
    t = config.env("IG_ACCESS_TOKEN")
    if not t:
        raise IGHata("IG_ACCESS_TOKEN tanımlı değil.")
    return t


def token_yenile(c, zorla: bool = False) -> None:
    """Uzun ömürlü token 60 gün geçerlidir; haftada bir yenileyip süresini uzatır."""
    if _facebook():  # sayfa token'ı süresiz, yenileme gerekmez
        return
    son = kv_al(c, "ig_token_yenileme")
    if not zorla and son and datetime.fromisoformat(son) > config.simdi() - timedelta(days=7):
        return
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token(c)}, timeout=30)
    if r.status_code != 200:
        log.warning("Token yenilenemedi: %s", r.text[:300])
        return
    yeni = r.json()["access_token"]
    f = _fernet()
    if f:
        kv_yaz(c, "ig_token", {"sifreli": f.encrypt(yeni.encode()).decode()})
    else:
        log.warning("DURUM_ANAHTARI yok: yenilenen token saklanamadı (60 günde bir elle yenilemen gerekir).")
    kv_yaz(c, "ig_token_yenileme", config.simdi().isoformat())
    log.info("Instagram token yenilendi (%s gün geçerli).", r.json().get("expires_in", 0) // 86400)


# ------------------------------------------------------------------ istek
def _istek(c, yontem: str, yol: str, **params):
    params["access_token"] = token(c)
    r = requests.request(yontem, f"{_api()}/{yol}", params=params if yontem == "GET" else None,
                         data=params if yontem != "GET" else None, timeout=60)
    veri = r.json() if r.content else {}
    if r.status_code != 200 or "error" in veri:
        raise IGHata(f"{yol}: {veri.get('error', {}).get('message', r.text[:300])}")
    return veri


def _kullanici() -> str:
    u = config.env("IG_USER_ID")
    if not u:
        raise IGHata("IG_USER_ID tanımlı değil.")
    return u


def kota(c) -> dict:
    v = _istek(c, "GET", f"{_kullanici()}/content_publishing_limit", fields="quota_usage,config")
    return (v.get("data") or [{}])[0]


def _hazir_olmasini_bekle(c, kap_id: str, sure: int = 120) -> None:
    bas = time.time()
    while time.time() - bas < sure:
        durum = _istek(c, "GET", kap_id, fields="status_code").get("status_code")
        if durum == "FINISHED":
            return
        if durum in ("ERROR", "EXPIRED"):
            raise IGHata(f"Medya işlenemedi ({durum}). Görsel adresi herkese açık JPEG mi?")
        time.sleep(4)
    raise IGHata("Medya işleme zaman aşımı")


def _yayinla(c, kap_id: str) -> str:
    _hazir_olmasini_bekle(c, kap_id)
    return _istek(c, "POST", f"{_kullanici()}/media_publish", creation_id=kap_id)["id"]


def gorsel_paylas(c, gorsel_url: str, aciklama: str) -> str:
    kap = _istek(c, "POST", f"{_kullanici()}/media", image_url=gorsel_url, caption=aciklama)["id"]
    return _yayinla(c, kap)


def carousel_paylas(c, gorsel_urller: list[str], aciklama: str) -> str:
    cocuklar = []
    for u in gorsel_urller[:10]:  # Instagram sınırı: 10 kare
        cocuklar.append(_istek(c, "POST", f"{_kullanici()}/media", image_url=u, is_carousel_item="true")["id"])
    for k in cocuklar:
        _hazir_olmasini_bekle(c, k)
    kap = _istek(c, "POST", f"{_kullanici()}/media", media_type="CAROUSEL",
                 children=",".join(cocuklar), caption=aciklama)["id"]
    return _yayinla(c, kap)


def hikaye_paylas(c, gorsel_url: str) -> str:
    kap = _istek(c, "POST", f"{_kullanici()}/media", media_type="STORIES", image_url=gorsel_url)["id"]
    return _yayinla(c, kap)


# ------------------------------------------------------------------ yorum -> DM
def yorumlara_dm(c, link_bul) -> int:
    """Son gönderilerde anahtar kelime yazanlara linki özel mesajla gönderir.

    link_bul(media_id) -> (metin) ; o gönderinin fırsat linklerini döner.
    Instagram kuralı: yoruma özel yanıt en geç 7 gün içinde ve yorum başına bir kez.
    """
    a = config.ayarlar()["yorum_dm"]
    kelimeler = [k.lower() for k in a["anahtar_kelimeler"]]
    gonderilen = 0
    medyalar = _istek(c, "GET", f"{_kullanici()}/media", fields="id,timestamp", limit=15).get("data", [])
    sinir = datetime.now().astimezone() - timedelta(days=6)
    for m in medyalar:
        if datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) < sinir:
            continue
        metin = link_bul(m["id"])
        if not metin:
            continue
        yorumlar = _istek(c, "GET", f"{m['id']}/comments", fields="id,text,username", limit=50).get("data", [])
        for y in yorumlar:
            if gonderilen >= a["calistirma_basina_max"]:
                return gonderilen
            if not any(k in (y.get("text") or "").lower() for k in kelimeler):
                continue
            if c.execute("SELECT 1 FROM yanitlanan_yorumlar WHERE yorum_id=?", (y["id"],)).fetchone():
                continue
            try:
                gonderen = "me" if _facebook() else _kullanici()  # facebook: sayfa adına
                requests.post(f"{_api()}/{gonderen}/messages", timeout=30,
                              params={"access_token": token(c)},
                              json={"recipient": {"comment_id": y["id"]}, "message": {"text": metin}}
                              ).raise_for_status()
                gonderilen += 1
            except requests.RequestException as e:
                log.warning("DM gönderilemedi (%s): %s", y["id"], e)
            c.execute("INSERT OR IGNORE INTO yanitlanan_yorumlar VALUES(?,?)", (y["id"], config.simdi().isoformat()))
            time.sleep(3)  # art arda hızlı mesaj atma
    return gonderilen
