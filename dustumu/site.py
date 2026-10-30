"""Bio'daki link sayfası (statik site). GitHub Pages'te ücretsiz yayınlanır.

Instagram açıklamasındaki linkler tıklanamaz; takipçi profildeki tek linke gelir,
fırsat KODUNU arar ya da listeden seçer. Her fırsatın kısa linki de vardır: /k/<kod>
"""
from __future__ import annotations

import html
import json
import shutil
import time
from datetime import timedelta

from . import config
from .calendar_tr import bu_hafta_market, tr_tarih, yaklasan_ozel_gunler
from .db import kv_al
from .planner import aktif_firsatlar
from .sources import KAYNAK_ADLARI, KAYNAK_RENK, affiliate_link

YONLENDIR = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>{baslik} | Düştü Mü?</title><meta http-equiv="refresh" content="1;url={link}">
<style>body{{font-family:system-ui,sans-serif;background:#FFD60A;color:#111;display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:16px}}
a{{display:inline-block;margin-top:16px;background:#111;color:#FFD60A;padding:14px 22px;border-radius:999px;font-weight:800;text-decoration:none}}</style>
</head><body><div><h1>KOD {kod}</h1><p>{baslik}</p><a href="{link}" rel="nofollow sponsored">Fırsata git →</a>
<p style="font-size:13px;margin-top:24px">Yönlendiriliyorsun… <a style="all:unset;text-decoration:underline;cursor:pointer" href="../../">Tüm fırsatlar</a></p></div>
<script>setTimeout(function(){{location.replace({link_js})}},400)</script></body></html>"""


def _firsat_json(f: dict) -> dict:
    return {
        "kod": f["kod"], "ad": f["ad"], "kaynak": KAYNAK_ADLARI.get(f["kaynak"], f["kaynak"]),
        "renk": KAYNAK_RENK.get(f["kaynak"], KAYNAK_RENK["diger"]), "tur": f["tur"],
        "fiyat": f["fiyat"], "eski": f["eski_fiyat"], "indirim": f["indirim"], "guven": f["guven"],
        "gorsel": f["gorsel"], "gecerlilik": f.get("gecerlilik") or "", "tarih": f["olusma"],
        "link": affiliate_link(f["kaynak"], f["url"]),
    }


def olustur(c) -> None:
    config.klasorleri_hazirla()
    a = config.ayarlar()
    bugun = config.simdi().date()
    firsatlar = aktif_firsatlar(c)
    # Paylaşılmış fırsatlar en üstte (takipçi o kodu arıyor), sonra puana göre.
    paylasilan = {k for r in c.execute("SELECT kodlar FROM gonderiler WHERE durum IN ('yayinlandi','deneme','planlandi')")
                  for k in json.loads(r["kodlar"])}
    firsatlar.sort(key=lambda f: (f["kod"] not in paylasilan, -f["puan"]))
    veriler = [_firsat_json(f) | {"paylasildi": f["kod"] in paylasilan} for f in firsatlar[:400]]

    # Kısa yönlendirme linkleri: aktif + son 30 günde paylaşılmış (pasifleşmiş olsa bile)
    k_klasor = config.SITE / "k"
    eskiler = {p.name for p in k_klasor.iterdir()} if k_klasor.exists() else set()
    sinir = (bugun - timedelta(days=30)).isoformat()
    for r in c.execute("""SELECT f.kod, u.ad, u.url, u.kaynak FROM firsatlar f JOIN urunler u ON u.id=f.urun_id
                          WHERE f.aktif=1 OR f.guncelleme>=?""", (sinir,)):
        link = affiliate_link(r["kaynak"], r["url"])
        hedef = k_klasor / str(r["kod"])
        hedef.mkdir(parents=True, exist_ok=True)
        (hedef / "index.html").write_text(YONLENDIR.format(
            kod=r["kod"], baslik=html.escape(r["ad"]), link=html.escape(link, quote=True),
            link_js=json.dumps(link)), encoding="utf-8")
        eskiler.discard(str(r["kod"]))
    for ad in eskiler:  # süresi geçmiş kısa linkler (OneDrive kilitlerse sonraki tura kalır)
        shutil.rmtree(k_klasor / ad, ignore_errors=True)

    takvim = [{"market": KAYNAK_ADLARI.get(o["market"], o["market"]), "renk": KAYNAK_RENK.get(o["market"], KAYNAK_RENK["diger"]),
               "tarih": tr_tarih(o["tarih"]), "baslik": o["baslik"]}
              for o in bu_hafta_market(bugun, kv_al(c, "bim_katalog_cache"))]
    ozel = [{"ad": o["ad"], "tarih": tr_tarih(o["tarih"], False), "kalan": o["kalan"]}
            for o in yaklasan_ozel_gunler(bugun, 60)]
    sahte = kv_al(c, "son_sahteler", [])[:12]
    ist = kv_al(c, "son_istatistik", {})

    sayfa = (config.KOK / "dustumu" / "site_sablon.html").read_text(encoding="utf-8")
    sayfa = (sayfa.replace("__VERI__", json.dumps({
        "firsatlar": veriler, "takvim": takvim, "ozel": ozel, "sahte": sahte, "istatistik": ist,
        "guncelleme": config.simdi().strftime("%d.%m.%Y %H:%M"),
        "instagram": a["marka"]["instagram_kullanici"],
    }, ensure_ascii=False).replace("</", "<\\/")))
    (config.SITE / "index.html").write_text(sayfa, encoding="utf-8")
    (config.SITE / ".nojekyll").write_text("", encoding="utf-8")
    (config.SITE / "robots.txt").write_text("User-agent: *\nDisallow: /k/\nDisallow: /hazir/\n", encoding="utf-8")
    hazir_sayfasi(c)
    for p in (config.KOK / "dustumu" / "sayfalar").glob("*.html"):  # gizlilik, koşullar, veri silme
        (config.SITE / p.stem).mkdir(exist_ok=True)
        shutil.copyfile(p, config.SITE / p.stem / "index.html")
    gorselleri_temizle()


def hazir_sayfasi(c, gun: int = 3) -> None:
    """Yarı otomatik mod: elle paylaşılacak gönderiler (görsel indir + açıklama kopyala)."""
    sinir = (config.simdi() - timedelta(days=gun)).isoformat(timespec="seconds")
    gonderiler = []
    for g in c.execute("""SELECT id, tur, gorseller, aciklama, planlanan FROM gonderiler
                          WHERE durum IN ('planlandi','deneme') AND tur!='reel' AND planlanan>=?
                          ORDER BY planlanan DESC LIMIT 20""",
                       (sinir,)):
        gorseller = [a for a in json.loads(g["gorseller"]) if (config.GORSEL / a).exists()]
        if gorseller:
            gonderiler.append({"id": g["id"], "tur": g["tur"], "gorseller": gorseller,
                               "aciklama": "" if g["tur"] == "hikaye" else g["aciklama"],
                               "planlanan": g["planlanan"]})
    sayfa = (config.KOK / "dustumu" / "hazir_sablon.html").read_text(encoding="utf-8")
    sayfa = sayfa.replace("__VERI__", json.dumps({
        "gonderiler": gonderiler, "guncelleme": config.simdi().strftime("%d.%m.%Y %H:%M"),
    }, ensure_ascii=False).replace("</", "<\\/"))
    klasor = config.SITE / "hazir"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / "index.html").write_text(sayfa, encoding="utf-8")


def gorselleri_temizle(gun: int = 10) -> None:
    """Instagram görseli yayın anında kopyalar; eski dosyaları tutmaya gerek yok."""
    sinir = time.time() - gun * 86400
    for desen in ("*.jpg", "*.mp4"):
        for p in config.GORSEL.glob(desen):
            if p.stat().st_mtime < sinir:
                p.unlink(missing_ok=True)
