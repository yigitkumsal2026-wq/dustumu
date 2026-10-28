"""İsteğe bağlı Telegram: fırsat kanalı (tıklanabilir link!) + hata bildirimi."""
from __future__ import annotations

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


def hata_bildir(metin: str) -> None:
    sohbet, url = config.env("TELEGRAM_SAHIP_ID"), _api("sendMessage")
    if not (config.ayarlar()["telegram"]["hata_bildirimi_aktif"] and sohbet and url):
        return
    try:
        requests.post(url, timeout=30, data={"chat_id": sohbet, "text": f"⚠️ Düştü Mü botu:\n{metin[:3500]}"})
    except requests.RequestException:
        pass
