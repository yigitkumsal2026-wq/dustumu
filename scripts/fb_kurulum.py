"""Facebook girişiyle Instagram bağlantısını kurar (Instagram girişi seçeneği olmayan uygulamalar için).

.env dosyasına şu üçünü yaz, sonra:  python scripts/fb_kurulum.py
    FB_APP_ID=        (Uygulama ayarları > Temel > Uygulama Kimliği)
    FB_APP_SECRET=    (aynı yer > Uygulama Gizli Anahtarı)
    FB_KISA_TOKEN=    (Graph API Gezgini'nden alınan kullanıcı token'ı)

Kısa ömürlü token -> uzun ömürlü kullanıcı token'ı -> SÜRESİZ sayfa token'ı.
Sayfaya bağlı Instagram hesabını bulur, GitHub secret/variable'larını gh ile kaydeder.
Token ekrana yazılmaz.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from dustumu import config  # noqa: E402  (.env'i yükler)

API = f"https://graph.facebook.com/{config.env('IG_API_VERSION', 'v23.0')}"
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def _get(yol: str, **params) -> dict:
    v = requests.get(f"{API}/{yol}", params=params, timeout=30).json()
    if "error" in v:
        sys.exit(f"HATA ({yol}): {v['error'].get('message')}")
    return v


def _gh(*args: str, girdi: str | None = None) -> None:
    subprocess.run([GH, *args], input=girdi, text=True, check=True, cwd=KOK)


def main() -> int:
    app_id, gizli, kisa = (config.env(a) for a in ("FB_APP_ID", "FB_APP_SECRET", "FB_KISA_TOKEN"))
    if not (app_id and gizli and kisa):
        sys.exit(".env içinde FB_APP_ID, FB_APP_SECRET ve FB_KISA_TOKEN dolu olmalı.")

    uzun = _get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                client_secret=gizli, fb_exchange_token=kisa)["access_token"]
    sayfalar = _get("me/accounts", access_token=uzun,
                    fields="id,name,access_token,instagram_business_account{id,username}").get("data", [])
    bagli = [s for s in sayfalar if s.get("instagram_business_account")]
    if not bagli:
        adlar = ", ".join(s["name"] for s in sayfalar) or "hiç sayfa yok"
        sys.exit(f"Instagram'a bağlı sayfa bulunamadı (görünen sayfalar: {adlar}). "
                 "Token alırken sayfayı ve Instagram hesabını seçtiğinden emin ol.")
    s = bagli[0]
    ig = s["instagram_business_account"]
    print(f"Sayfa: {s['name']}  ->  Instagram: @{ig.get('username')} (id {ig['id']})")

    test = _get(ig["id"], fields="id,username", access_token=s["access_token"])
    print(f"Bağlantı testi tamam: @{test.get('username')}")

    depo = os.environ.get("GITHUB_DEPO", "yigitkumsal2026-wq/dustumu")
    _gh("secret", "set", "IG_USER_ID", "--repo", depo, girdi=ig["id"])
    _gh("secret", "set", "IG_ACCESS_TOKEN", "--repo", depo, girdi=s["access_token"])
    _gh("variable", "set", "IG_GIRIS", "--repo", depo, "--body", "facebook")
    print("GitHub'a kaydedildi: IG_USER_ID, IG_ACCESS_TOKEN (secret), IG_GIRIS=facebook (variable).")
    print("Güvenlik için .env içindeki FB_KISA_TOKEN ve FB_APP_SECRET satırlarını silebilirsin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
