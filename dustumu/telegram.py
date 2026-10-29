"""İsteğe bağlı Telegram: fırsat kanalı (tıklanabilir link!) + hata bildirimi."""
from __future__ import annotations

import json
import logging

import requests

from . import config

log = logging.getLogger(__name__)


def _api(metot: str) -> str | None:
    t = config.env("TELEGRAM_BOT_TOKEN")
    return f"https://api.telegram.org/bot{t}/{metot}" if t else None


def firsat_gonder(gorsel_yolu, metin: str, link: str) -> None:
    a = config.ayarlar()["telegram"]
    kanal, url = config.env("TELEGRAM_KANAL"), _api("sendPhoto")
    if not (a["firsat_kanali_aktif"] and kanal and url):
        return
    try:
        with open(gorsel_yolu, "rb") as f:
            requests.post(url, timeout=60, files={"photo": f}, data={
                "chat_id": kanal, "caption": metin[:1000],
                "reply_markup": '{"inline_keyboard":[[{"text":"🛒 Fırsata git","url":"%s"}]]}' % link,
            }).raise_for_status()
    except Exception as e:
        log.warning("Telegram'a gönderilemedi: %s", e)


_TUR_ADI = {"carousel": "📸 Kaydırmalı gönderi (carousel)", "tekli": "📸 Tekli gönderi", "hikaye": "📱 Hikâye"}


def taslak_gonder(gorsel_yollari: list, tur: str, aciklama: str) -> bool:
    """Yarı otomatik mod: hazır görselleri + açıklamayı sahibine gönderir, o da elle paylaşır."""
    sohbet = config.env("TELEGRAM_SAHIP_ID")
    if not (config.ayarlar()["telegram"]["taslak_aktif"] and sohbet and _api("sendMessage")):
        return False
    try:
        dosyalar = {f"g{i}": open(y, "rb") for i, y in enumerate(gorsel_yollari[:10])}
        try:
            if len(dosyalar) == 1:
                requests.post(_api("sendPhoto"), timeout=120, files={"photo": dosyalar["g0"]},
                              data={"chat_id": sohbet}).raise_for_status()
            else:
                medya = [{"type": "photo", "media": f"attach://{ad}"} for ad in dosyalar]
                requests.post(_api("sendMediaGroup"), timeout=180, files=dosyalar,
                              data={"chat_id": sohbet, "media": json.dumps(medya)}).raise_for_status()
        finally:
            for f in dosyalar.values():
                f.close()
        baslik = f"{_TUR_ADI.get(tur, tur)} hazır — görselleri sırayla kaydedip paylaş."
        requests.post(_api("sendMessage"), timeout=30, data={"chat_id": sohbet, "text": baslik}).raise_for_status()
        if tur != "hikaye" and aciklama:
            # Ayrı mesaj: Telegram'da basılı tutup tek dokunuşla kopyalanabilsin.
            requests.post(_api("sendMessage"), timeout=30,
                          data={"chat_id": sohbet, "text": aciklama[:4096]}).raise_for_status()
        return True
    except Exception as e:
        log.warning("Taslak Telegram'a gönderilemedi: %s", e)
        return False


def hata_bildir(metin: str) -> None:
    sohbet, url = config.env("TELEGRAM_SAHIP_ID"), _api("sendMessage")
    if not (config.ayarlar()["telegram"]["hata_bildirimi_aktif"] and sohbet and url):
        return
    try:
        requests.post(url, timeout=30, data={"chat_id": sohbet, "text": f"⚠️ Düştü Mü botu:\n{metin[:3500]}"})
    except requests.RequestException:
        pass
