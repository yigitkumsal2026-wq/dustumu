"""DÜŞTÜ MÜ? — İndirim otomasyonu komut satırı.

Kullanım:
  python main.py calistir        # hepsi bir arada: topla + planla + site + yayınla
  python main.py panel           # yerel inceleme paneli (http://localhost:5000)
  python main.py topla           # sadece fiyatları topla ve indirimleri doğrula
  python main.py planla [--zorla]# paylaşım planla ve görselleri üret (--zorla: saat/limit kontrolü yok)
  python main.py site            # link sayfasını üret
  python main.py yayinla         # planlanmış gönderileri yayınla
  python main.py yorumlar        # "LİNK" yazanlara DM gönder
  python main.py hazirla         # (bulut 1. adım) topla + planla + site
  python main.py ig-test         # Instagram bağlantısını ve kotayı kontrol et
  python main.py durum           # özet
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime, timedelta

from dustumu import config, db, planner, site, telegram, verify, yayin
from dustumu.sources import tum_kaynaklar

log = logging.getLogger("dustumu")


def topla(c, zorla: bool = True) -> None:
    a = config.ayarlar()["kaynaklar"]
    simdi = config.simdi()
    bugun = simdi.date()
    son = db.kv_al(c, "son_toplama")
    if not zorla and son and simdi - datetime.fromisoformat(son) < timedelta(hours=a["toplama_araligi_saat"]):
        log.info("Fiyat taraması atlandı (son tarama %s).", son[11:16])
        return
    db.kv_yaz(c, "son_toplama", simdi.isoformat(timespec="seconds"))
    for ad, modul in tum_kaynaklar().items():
        if not a.get(ad, {}).get("aktif"):
            continue
        try:
            urunler = modul.topla(a[ad])
            verify.kaydet(c, urunler, bugun)
            c.commit()
            log.info("%-7s %4d ürün", ad, len(urunler))
        except Exception as e:
            log.error("%s kaynağı başarısız: %s", ad, e)
            telegram.hata_bildir(f"{ad} kaynağı başarısız: {e}")
    if a.get("bim", {}).get("aktif"):
        from dustumu.sources import bim
        katalog = [k | {"baslangic": k["baslangic"].isoformat(), "bitis": k["bitis"].isoformat() if k["bitis"] else None}
                   for k in bim.takvim(bugun)]
        if katalog:
            db.kv_yaz(c, "bim_katalog_cache", katalog)
    verify.firsatlari_guncelle(c, bugun)
    verify.eski_kayitlari_temizle(c, bugun)


def planla(c, zorla=False) -> None:
    ids = planner.planla(c, zorla=zorla, bim_katalog=db.kv_al(c, "bim_katalog_cache"))
    for i in ids:
        g = c.execute("SELECT tur, gorseller FROM gonderiler WHERE id=?", (i,)).fetchone()
        log.info("Planlandı #%s %s -> %s", i, g["tur"], g["gorseller"])


def durum(c) -> None:
    ist = db.kv_al(c, "son_istatistik", {})
    print(f"Son değerlendirme: {ist}")
    print(f"Aktif fırsat: {c.execute('SELECT COUNT(*) FROM firsatlar WHERE aktif=1').fetchone()[0]}")
    print(f"Bugünkü limit: {planner.gunluk_limit(config.simdi().date())} feed gönderisi")
    for r in c.execute("SELECT durum, COUNT(*) n FROM gonderiler GROUP BY durum"):
        print(f"  gönderi {r['durum']}: {r['n']}")
    print(f"Sonraki uygun paylaşım: {db.kv_al(c, 'sonraki_uygun')}")


def ig_test(c) -> None:
    from dustumu import instagram
    import requests
    t = instagram.token(c)
    r = requests.get(f"{instagram._api()}/me", params={"fields": "user_id,username,account_type", "access_token": t}, timeout=30)
    print("Hesap:", r.json())
    print("Kota:", instagram.kota(c))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Düştü Mü? indirim otomasyonu")
    p.add_argument("komut", choices=["calistir", "panel", "topla", "planla", "site", "yayinla", "yorumlar",
                                      "hazirla", "ig-test", "durum"])
    p.add_argument("--zorla", action="store_true", help="saat/limit kontrolü olmadan planla")
    p.add_argument("--port", type=int, default=5000)
    arg = p.parse_args()

    if arg.komut == "panel":
        from dustumu.panel import baslat
        baslat(arg.port)
        return 0

    with db.oturum() as c:
        try:
            if arg.komut in ("topla", "hazirla", "calistir"):
                # "topla" komutu her zaman tarar; otomatik akışlar aralığa uyar.
                topla(c, zorla=arg.komut == "topla" or arg.zorla)
            if arg.komut in ("planla", "hazirla", "calistir"):
                planla(c, arg.zorla)
            if arg.komut in ("site", "hazirla", "calistir"):
                site.olustur(c)
                log.info("Site üretildi: %s", config.SITE / "index.html")
            if arg.komut in ("yayinla", "calistir"):
                log.info("Yayın sonucu: %s", yayin.bekleyenleri_yayinla(c))
            if arg.komut == "yorumlar" and config.ayarlar()["yorum_dm"]["aktif"]:
                from dustumu import instagram
                log.info("DM gönderildi: %s", instagram.yorumlara_dm(c, yayin.dm_metni_bul(c)))
            if arg.komut == "ig-test":
                ig_test(c)
            if arg.komut == "durum":
                durum(c)
        except Exception as e:
            c.commit()
            log.error("Hata: %s", e)
            telegram.hata_bildir(f"{arg.komut} komutu çöktü:\n{traceback.format_exc()[-1500:]}")
            raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
