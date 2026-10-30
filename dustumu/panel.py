"""Yerel inceleme paneli: http://localhost:5000

Bulutta otomatik çalışmadan önce her şeyi burada görür, dener, düzeltirsin:
fırsatlar + fiyat geçmişi, üretilen görseller ve açıklamalar, sahte indirimler,
manuel fırsat ekleme, link sayfası önizlemesi.
"""
from __future__ import annotations

import json
import logging
import threading
import webbrowser

import yaml
from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for

from . import config, db, planner, site, verify
from .calendar_tr import yaklasan_ozel_gunler
from .sources import KAYNAK_ADLARI, KAYNAK_RENK, manuel

log = logging.getLogger(__name__)
app = Flask(__name__)
_is = {"calisiyor": False, "mesaj": ""}


def _arka_planda(ad: str, fn) -> None:
    if _is["calisiyor"]:
        return

    def calis():
        _is.update(calisiyor=True, mesaj=f"{ad} çalışıyor…")
        try:
            with db.oturum() as c:
                fn(c)
            _is["mesaj"] = f"✓ {ad} tamamlandı"
        except Exception as e:
            log.exception(ad)
            _is["mesaj"] = f"✗ {ad} hata: {e}"
        finally:
            _is["calisiyor"] = False
    threading.Thread(target=calis, daemon=True).start()


def _sparkline(fiyatlar: list[float], w=120, h=34) -> str:
    if len(fiyatlar) < 2:
        return ""
    lo, hi = min(fiyatlar), max(fiyatlar)
    aralik = (hi - lo) or 1
    nok = " ".join(f"{i * w / (len(fiyatlar) - 1):.1f},{h - 4 - (p - lo) / aralik * (h - 8):.1f}"
                   for i, p in enumerate(fiyatlar))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="fiyat geçmişi">'
            f'<polyline points="{nok}" fill="none" stroke="currentColor" stroke-width="2"/></svg>')


SABLON = r"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Düştü Mü? Panel</title>
<style>
:root{--z:#F6F5F1;--k:#fff;--y:#111;--s:#6B7280;--c:#E7E5DF;--sari:#FFD60A;--kir:#E63946;--yes:#16A34A}
@media (prefers-color-scheme:dark){:root{--z:#0F0F12;--k:#1A1A20;--y:#F4F4F5;--s:#A1A1AA;--c:#2A2A33}}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,sans-serif;background:var(--z);color:var(--y)}
header{background:var(--sari);color:#111;padding:14px 20px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{margin:0;font-size:22px;font-weight:900}.mod{font-weight:800;padding:4px 10px;border-radius:999px;background:#111;color:var(--sari);font-size:13px}
nav{display:flex;gap:6px;padding:12px 20px;flex-wrap:wrap;border-bottom:1px solid var(--c)}
nav a{color:var(--y);text-decoration:none;font-weight:700;padding:8px 12px;border-radius:10px}nav a.on{background:var(--y);color:var(--z)}
main{padding:20px;max-width:1300px;margin:0 auto}
.kutular{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:18px}
.kutu{background:var(--k);border:1px solid var(--c);border-radius:14px;padding:14px}.kutu b{display:block;font-size:26px}.kutu span{color:var(--s);font-size:13px;font-weight:600}
.butonlar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px}
button,.btn{font:700 14px system-ui;border:0;background:var(--y);color:var(--z);padding:10px 14px;border-radius:10px;cursor:pointer;text-decoration:none;display:inline-block}
button.ikincil{background:transparent;color:var(--y);border:2px solid var(--y)}button.tehlike{background:var(--kir);color:#fff}
.mesaj{padding:10px 14px;border-radius:10px;background:var(--k);border:1px solid var(--c);margin-bottom:14px;font-weight:600}
.posts{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.post{background:var(--k);border:1px solid var(--c);border-radius:16px;overflow:hidden}
.post .gorseller{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;background:#000}
.post .gorseller img{width:100%;flex:none;scroll-snap-align:start;display:block}
.post .ic{padding:12px 14px}.post pre{white-space:pre-wrap;font:13px/1.45 system-ui;margin:8px 0;max-height:220px;overflow:auto}
.etiket{display:inline-block;font-size:12px;font-weight:800;padding:3px 9px;border-radius:999px;background:var(--c)}
.etiket.yayinlandi{background:var(--yes);color:#fff}.etiket.hata{background:var(--kir);color:#fff}.etiket.planlandi{background:var(--sari);color:#111}
table{width:100%;border-collapse:collapse;background:var(--k);border-radius:14px;overflow:hidden}
td,th{padding:8px 10px;border-bottom:1px solid var(--c);text-align:left;font-size:14px;vertical-align:middle}th{font-size:12px;color:var(--s);text-transform:uppercase}
td img{width:54px;height:54px;object-fit:contain;background:#fff;border-radius:8px}
.mag{font-size:12px;font-weight:800;padding:3px 8px;border-radius:999px;white-space:nowrap}
.g-dogrulandi{color:var(--yes);font-weight:800}.g-beyan{color:var(--s);font-weight:700}.g-editor{color:#7B2FF7;font-weight:800}
form.satir{display:inline}
.form{background:var(--k);border:1px solid var(--c);border-radius:14px;padding:18px;display:grid;gap:12px;max-width:640px}
.form label{display:grid;gap:4px;font-weight:700;font-size:14px}.form input,.form select{font:15px system-ui;padding:10px;border-radius:8px;border:1px solid var(--c);background:var(--z);color:var(--y)}
.ipucu{color:var(--s);font-size:13px}
</style></head><body>
<header><h1>DÜŞTÜ MÜ? ⬇ Panel</h1>
<span class="mod">{{ 'CANLI: Instagram açık' if canli else 'DENEME MODU: Instagram kapalı' }}</span>
<a class="btn" style="background:#111;color:#FFD60A" href="{{ url_for('site_dosya', yol='index.html') }}" target="_blank">Link sayfasını önizle ↗</a></header>
<nav>{% for k,ad in sekmeler %}<a href="{{ url_for('ana', sekme=k) }}" class="{{ 'on' if k==sekme }}">{{ ad }}</a>{% endfor %}</nav>
<main>
{% if mesaj %}<div class="mesaj">{{ mesaj }}{% if calisiyor %} <script>setTimeout(()=>location.reload(),4000)</script>{% endif %}</div>{% endif %}
<div class="kutular">
 <div class="kutu"><b>{{ ist.get('incelenen',0) }}</b><span>son taramada incelenen ürün</span></div>
 <div class="kutu"><b>{{ aktif }}</b><span>aktif fırsat</span></div>
 <div class="kutu"><b>{{ ist.get('sahte',0) }}</b><span>elenen sahte indirim</span></div>
 <div class="kutu"><b>{{ bugun_sayi }}/{{ limit }}</b><span>bugünkü feed gönderisi / limit</span></div>
 <div class="kutu"><b>{{ (sonraki or '—')[11:16] or '—' }}</b><span>sonraki en erken paylaşım</span></div>
</div>
<div class="butonlar">
 <form method="post" action="{{ url_for('islem', ad='topla') }}"><button>1. Fiyatları topla + doğrula</button></form>
 <form method="post" action="{{ url_for('islem', ad='planla') }}"><button>2. Gönderi planla (zamanlamaya uyar)</button></form>
 <form method="post" action="{{ url_for('islem', ad='zorla') }}"><button class="ikincil">Gönderi planla (hemen, zorla)</button></form>
 <form method="post" action="{{ url_for('islem', ad='site') }}"><button class="ikincil">Link sayfasını üret</button></form>
</div>

{% if sekme=='gonderiler' %}
 <p class="ipucu">Üretilen gönderiler. Deneme modunda Instagram'a gitmez; burada nasıl görüneceğini incelersin. Carousel'de görseller yana kayar.</p>
 <div class="posts">{% for g in gonderiler %}<div class="post">
  <div class="gorseller">{% for a in g.gorseller %}{% if a.endswith('.mp4') %}<video src="{{ url_for('gorsel', ad=a) }}" controls preload="none" style="width:100%"></video>{% else %}<img src="{{ url_for('gorsel', ad=a) }}" alt="" loading="lazy">{% endif %}{% endfor %}</div>
  <div class="ic"><span class="etiket {{ g.durum }}">{{ g.durum }}</span> <span class="etiket">{{ g.tur }}</span> <span class="ipucu">{{ g.planlanan[:16].replace('T',' ') }}</span>
  {% if g.hata %}<p style="color:var(--kir)">{{ g.hata }}</p>{% endif %}
  {% if g.aciklama %}<pre>{{ g.aciklama }}</pre>{% endif %}
  {% if g.durum=='planlandi' %}<form method="post" action="{{ url_for('gonderi_iptal', gid=g.id) }}"><button class="tehlike">İptal et</button></form>{% endif %}
  </div></div>{% else %}<p>Henüz gönderi yok. Önce "Fiyatları topla", sonra "Gönderi planla (hemen)".</p>{% endfor %}</div>

{% elif sekme=='firsatlar' %}
 <table><thead><tr><th></th><th>Kod</th><th>Ürün</th><th>Mağaza</th><th>Fiyat</th><th>İndirim</th><th>Güven</th><th>30 gün</th><th>Puan</th><th></th></tr></thead><tbody>
 {% for f in firsatlar %}<tr>
  <td><img src="{{ f.gorsel }}" referrerpolicy="no-referrer" alt=""></td><td><b>{{ f.kod }}</b></td>
  <td><a href="{{ f.url }}" target="_blank" style="color:inherit">{{ f.ad[:70] }}</a><div class="ipucu">{{ f.ref_aciklama or '' }}</div></td>
  <td><span class="mag" style="background:{{ renk(f.kaynak)[0] }};color:{{ renk(f.kaynak)[1] }}">{{ kad(f.kaynak) }}</span></td>
  <td><b>{{ '%.2f'|format(f.fiyat) }}</b>{% if f.eski_fiyat>f.fiyat %}<div class="ipucu"><s>{{ '%.2f'|format(f.eski_fiyat) }}</s></div>{% endif %}</td>
  <td>{{ '%'~f.indirim if f.guven!='aktuel' else 'aktüel' }}</td><td class="g-{{ f.guven }}">{{ f.guven }}</td>
  <td>{{ f.spark|safe }}</td><td>{{ f.puan }}</td>
  <td style="white-space:nowrap"><form class="satir" method="post" action="{{ url_for('firsat_hazirla', kod=f.kod) }}"><button title="Bu fırsat için şimdi gönderi üret">Gönderi yap</button></form>
  <form class="satir" method="post" action="{{ url_for('kara_liste', uid=f.urun_id) }}"><button class="ikincil" title="Bir daha önerme">Gizle</button></form></td>
 </tr>{% else %}<tr><td colspan="10">Fırsat yok. "Fiyatları topla"ya bas.</td></tr>{% endfor %}</tbody></table>
 <p class="ipucu">İlk günlerde fiyat geçmişi birikmediği için çoğu fırsat "beyan" (satıcı indirimi) görünür. 3+ gün sonra geçmişle teyit edilenler "dogrulandi" olur.</p>

{% elif sekme=='sahte' %}
 <p class="ipucu">Satıcı büyük indirim gösteriyor ama son 30 günde fiyat zaten bu seviyedeydi. Bunlar paylaşılmaz (link sayfasında "yakalanan sahte indirimler" olarak listelenir — güzel bir içerik fikri!).</p>
 <table><thead><tr><th>Ürün</th><th>Mağaza</th><th>İddia</th><th>Bugün</th><th>30 gün en düşük</th></tr></thead><tbody>
 {% for s in sahteler %}<tr><td><a href="{{ s.url }}" target="_blank" style="color:inherit">{{ s.ad[:80] }}</a></td><td>{{ kad(s.kaynak) }}</td><td>%{{ s.beyan }} ({{ s.liste }})</td><td>{{ s.fiyat }}</td><td>{{ s.min30 or '—' }}</td></tr>
 {% else %}<tr><td colspan="5">Henüz yok. Sahte indirim tespiti için birkaç günlük fiyat geçmişi gerekir.</td></tr>{% endfor %}</tbody></table>

{% elif sekme=='ekle' %}
 <p class="ipucu">Trendyol, Hepsiburada, Amazon, A101 gibi bot koruması olan sitelerdeki fırsatları buradan ekle. Affiliate linkini yapıştırırsan gelir elde edersin. Bitiş tarihi geçince otomatik kalkar.</p>
 <form class="form" method="post" action="{{ url_for('manuel_ekle') }}">
  <label>Ürün adı<input name="ad" required maxlength="140"></label>
  <label>Link (affiliate linkin varsa onu yapıştır)<input name="url" type="url" required></label>
  <label>Mağaza<select name="kaynak">{% for k in ['trendyol','hepsiburada','amazon','a101','n11','migros','bim','sok','carrefoursa','diger'] %}<option value="{{ k }}">{{ kad(k) }}</option>{% endfor %}</select></label>
  <label>İndirimli fiyat (TL)<input name="fiyat" type="number" step="0.01" min="0" required></label>
  <label>Eski fiyat (TL)<input name="eski_fiyat" type="number" step="0.01" min="0" required></label>
  <label>Ürün görseli URL'si<input name="gorsel" type="url" required><span class="ipucu">Ürün sayfasındaki resme sağ tık → "Resim adresini kopyala"</span></label>
  <label>Bitiş tarihi (opsiyonel)<input name="bitis" type="date"></label>
  <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" name="affiliate" value="1"> Bu bir affiliate (gelir ortaklığı) linki</label>
  <button>Ekle ve doğrula</button>
 </form>
 {% if manueller %}<h3>Eklenenler</h3><table><tbody>{% for m in manueller %}<tr><td>{{ m.ad }}</td><td>{{ kad(m.kaynak) }}</td><td>{{ m.fiyat }} / {{ m.eski_fiyat }}</td><td>{{ m.bitis or '' }}</td>
 <td><form method="post" action="{{ url_for('manuel_sil', i=loop.index0) }}"><button class="tehlike">Sil</button></form></td></tr>{% endfor %}</tbody></table>{% endif %}

{% elif sekme=='takvim' %}
 <table><thead><tr><th>Tarih</th><th>Etkinlik</th><th>Kalan</th></tr></thead><tbody>
 {% for o in ozel %}<tr><td>{{ o.tarih }}</td><td>{{ o.ad }}</td><td>{{ o.kalan }} gün</td></tr>{% endfor %}</tbody></table>
 <p class="ipucu">Market haftalık günleri ve bayram tarihleri config.yaml / dustumu/calendar_tr.py içinden düzenlenir.</p>
{% endif %}
</main></body></html>"""

SEKMELER = [("gonderiler", "Gönderiler"), ("firsatlar", "Fırsatlar"), ("sahte", "Sahte indirimler"),
            ("ekle", "Manuel fırsat ekle"), ("takvim", "İndirim takvimi")]


@app.route("/")
def ana():
    sekme = request.args.get("sekme", "gonderiler")
    with db.oturum() as c:
        s = config.simdi()
        gonderiler = [dict(r) | {"gorseller": json.loads(r["gorseller"])}
                      for r in c.execute("SELECT * FROM gonderiler ORDER BY id DESC LIMIT 60")]
        firsatlar = []
        if sekme == "firsatlar":
            for f in planner.aktif_firsatlar(c)[:300]:
                gec = [r["fiyat"] for r in c.execute(
                    "SELECT fiyat FROM fiyatlar WHERE urun_id=? ORDER BY tarih DESC LIMIT 30", (f["urun_id"],))][::-1]
                firsatlar.append(f | {"spark": _sparkline(gec)})
        veri = dict(
            sekme=sekme, sekmeler=SEKMELER, canli=config.ayarlar()["yayin"]["instagram_aktif"],
            mesaj=_is["mesaj"], calisiyor=_is["calisiyor"], ist=db.kv_al(c, "son_istatistik", {}),
            aktif=c.execute("SELECT COUNT(*) FROM firsatlar WHERE aktif=1").fetchone()[0],
            bugun_sayi=planner._bugun_sayisi(c, s.date().isoformat(), planner.FEED_TURLERI),
            limit=planner.gunluk_limit(s.date()), sonraki=db.kv_al(c, "sonraki_uygun"),
            gonderiler=gonderiler, firsatlar=firsatlar, sahteler=db.kv_al(c, "son_sahteler", []),
            manueller=manuel.oku(), ozel=yaklasan_ozel_gunler(s.date(), 365),
            renk=lambda k: KAYNAK_RENK.get(k, KAYNAK_RENK["diger"]), kad=lambda k: KAYNAK_ADLARI.get(k, k),
        )
    return render_template_string(SABLON, **veri)


@app.post("/islem/<ad>")
def islem(ad):
    import main as cli
    isler = {
        "topla": ("Fiyat toplama", lambda c: (cli.topla(c), site.olustur(c))),
        "planla": ("Planlama", lambda c: (cli.planla(c), site.olustur(c))),
        "zorla": ("Zorla planlama", lambda c: (cli.planla(c, True), site.olustur(c))),
        "site": ("Site üretimi", site.olustur),
    }
    if ad in isler:
        _arka_planda(*isler[ad])
    return redirect(request.referrer or url_for("ana"))


@app.post("/firsat/<int:kod>/hazirla")
def firsat_hazirla(kod):
    _arka_planda(f"KOD {kod} gönderisi", lambda c: (planner.tekli_hazirla(c, kod), site.olustur(c)))
    return redirect(url_for("ana", sekme="gonderiler"))


@app.post("/gonderi/<int:gid>/iptal")
def gonderi_iptal(gid):
    with db.oturum() as c:
        c.execute("UPDATE gonderiler SET durum='iptal' WHERE id=? AND durum='planlandi'", (gid,))
    return redirect(url_for("ana", sekme="gonderiler"))


@app.post("/kara-liste/<path:uid>")
def kara_liste(uid):
    d = {}
    if config.KARA_LISTE_DOSYA.exists():
        d = yaml.safe_load(config.KARA_LISTE_DOSYA.read_text(encoding="utf-8")) or {}
    d.setdefault("urunler", [])
    d.setdefault("kelimeler", [])
    if uid not in d["urunler"]:
        d["urunler"].append(uid)
    config.KARA_LISTE_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    config.KARA_LISTE_DOSYA.write_text("# Paylaşılmayacak ürün id'leri ve kelimeler\n" +
                                       yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    with db.oturum() as c:
        c.execute("UPDATE firsatlar SET aktif=0 WHERE urun_id=?", (uid,))
    return redirect(url_for("ana", sekme="firsatlar"))


@app.post("/manuel")
def manuel_ekle():
    f = request.form
    kayitlar = manuel.oku()
    kayitlar.append({k: v for k, v in {
        "ad": f["ad"].strip(), "url": f["url"].strip(), "kaynak": f["kaynak"], "fiyat": float(f["fiyat"]),
        "eski_fiyat": float(f["eski_fiyat"]), "gorsel": f["gorsel"].strip(), "bitis": f.get("bitis") or None,
        "affiliate": bool(f.get("affiliate")),
    }.items() if v not in (None, "")})
    manuel.yaz(kayitlar)

    def isle(c):
        bugun = config.simdi().date()
        verify.kaydet(c, manuel.topla({}), bugun)
        verify.firsatlari_guncelle(c, bugun)
        site.olustur(c)
    _arka_planda("Manuel fırsat", isle)
    return redirect(url_for("ana", sekme="firsatlar"))


@app.post("/manuel/<int:i>/sil")
def manuel_sil(i):
    kayitlar = manuel.oku()
    if 0 <= i < len(kayitlar):
        kayitlar.pop(i)
        manuel.yaz(kayitlar)
    return redirect(url_for("ana", sekme="ekle"))


@app.route("/g/<path:ad>")
def gorsel(ad):
    return send_from_directory(config.GORSEL, ad)


@app.route("/site/<path:yol>")
def site_dosya(yol):
    hedef = config.SITE / yol
    if hedef.is_dir():
        yol = yol.rstrip("/") + "/index.html"
    return send_from_directory(config.SITE, yol)


def baslat(port: int = 5000) -> None:
    config.klasorleri_hazirla()
    with db.oturum() as c:
        if not (config.SITE / "index.html").exists():
            site.olustur(c)
    url = f"http://localhost:{port}"
    print(f"\n  Panel açılıyor: {url}\n  Kapatmak için Ctrl+C\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
