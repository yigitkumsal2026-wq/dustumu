"""Gönderi açıklamaları. Aynı kalıbı tekrar tekrar kullanmamak için şablonlar döner
(tekrarlayan metin hem sıkıcıdır hem de spam sinyali verir)."""
from __future__ import annotations

import random

from . import config
from .render import para, son_gun
from .sources import KAYNAK_ADLARI


def _son_gun(f: dict) -> str | None:
    """'3 Kasım' (aktüelde bitiş tahmini olduğundan yok)."""
    if not son_gun(f):
        return None
    from datetime import date
    from .calendar_tr import tr_tarih
    return tr_tarih(date.fromisoformat(str(f["bitis"])[:10]), False)

GIRISLER = [
    "🔻 %{i} DÜŞTÜ! {ad}",
    "🚨 Fiyat alarmı: {ad}",
    "👀 Bunu görmeden geçme: {ad}",
    "💸 Cebinde {t} TL kalsın: {ad}",
    "📉 Fiyatı gerçekten düştü: {ad}",
    "🔥 Günün fırsatı: {ad}",
]
AKTUEL_GIRIS = [
    "🛒 {m} aktüel: {ad}",
    "📢 {g} {m}'de: {ad}",
    "🗓️ {m} aktüel listesinde: {ad}",
]
GUVEN_SATIRI = {
    "dogrulandi": "✔️ Gerçek indirim: son 30 günün en düşük fiyatından da ucuz. Fiyat geçmişini biz takip ediyoruz.",
    "beyan": "ℹ️ Satıcının indirimi; fiyat geçmişini takibe aldık.",
    "editor": "⭐ Editör seçimi.",
    "aktuel": "🗓️ Aktüel ürün, stoklarla sınırlıdır.",
}
TEMEL_ETIKET = ["#indirim", "#fırsat", "#düştümü", "#kampanya", "#indirimvar", "#ucuz"]
KAYNAK_ETIKET = {
    "migros": ["#migros", "#marketindirimleri"], "sok": ["#şok", "#şokmarket", "#marketindirimleri"],
    "bim": ["#bim", "#bimaktüel", "#aktüel"], "a101": ["#a101", "#a101aktüel", "#aktüel"],
    "n11": ["#n11", "#onlinealışveriş"], "trendyol": ["#trendyol", "#trendyolindirim"],
    "hepsiburada": ["#hepsiburada"], "amazon": ["#amazon", "#amazontürkiye"],
}


def _etiketler(kaynaklar: list[str], ekstra: list[str] | None = None) -> str:
    n = config.ayarlar()["yayin"]["hashtag_sayisi"]
    secim: list[str] = []
    for k in kaynaklar:
        secim += KAYNAK_ETIKET.get(k, [])[:2]
    secim += ekstra or []
    secim += random.sample(TEMEL_ETIKET, len(TEMEL_ETIKET))
    return " ".join(list(dict.fromkeys(["#düştümü"] + secim))[:n])


def _link_satirlari() -> list[str]:
    if config.ayarlar()["yorum_dm"]["aktif"]:
        return ['💬 Yorumlara "LİNK" yaz, DM\'den gönderelim.']
    return []


REKLAM_DEGIL = "📢 Reklam değildir. Hiçbir markayla iş birliğimiz yok, ücret almıyoruz; fiyatları kendimiz takip ediyoruz."


def _money_satiri(firsatlar: list[dict]) -> list[str]:
    afis = next((f.get("gecerlilik") for f in firsatlar if f["kaynak"] == "bim_indirim"), None)
    if afis:
        return [f"📋 BİM indirim afişi {afis}: oranlar afişteki eski fiyata göredir, marka ve stok mağazaya göre değişebilir."]
    donem = next((f.get("gecerlilik") for f in firsatlar if f["kaynak"] == "migroskop"), None)
    if not donem:
        return []
    return [f"💳 Migroskop {donem}: fiyatlar Money veya Money Bonus ile geçerlidir, indirim oranı Money'siz fiyata göredir. "
            "Ürünler her mağazada bulunmayabilir."]


def _alt_bilgi(affiliate: bool) -> list[str]:
    s = [f"⏰ Fiyatlar {config.simdi():%d.%m.%Y %H:%M} itibarıyladır; stok ve fiyat değişebilir."]
    s.append(config.ayarlar()["affiliate"]["aciklama_etiketi"] if affiliate else REKLAM_DEGIL)
    return s


def tekli(f: dict, affiliate: bool = False) -> str:
    m = KAYNAK_ADLARI.get(f["kaynak"], f["kaynak"])
    t = para(round(f["eski_fiyat"] - f["fiyat"]))
    if f["guven"] == "aktuel":
        giris = random.choice(AKTUEL_GIRIS).format(m=m, ad=f["ad"], g=f.get("gecerlilik") or "Bu hafta")
        fiyat = [f"🏷️ {para(f['fiyat'])} TL", f"📅 {f.get('gecerlilik') or ''}".strip()]
    else:
        giris = random.choice(GIRISLER).format(i=int(f["indirim"]), ad=f["ad"], t=t)
        fiyat = [f"❌ {para(f['eski_fiyat'])} TL → ✅ {para(f['fiyat'])} TL", f"💰 {t} TL tasarruf (%{int(f['indirim'])})"]
        if _son_gun(f):
            fiyat.append(f"⏳ Son gün: {_son_gun(f)}")
    satirlar = [giris, "", *fiyat, GUVEN_SATIRI[f["guven"]], f"🏪 {m}", *_money_satiri([f]), "", *_link_satirlari(),
                "📌 Kaydet, ihtiyacı olan arkadaşını etiketle!", *_alt_bilgi(affiliate), "",
                _etiketler([f["kaynak"]])]
    return "\n".join(satirlar)


def carousel(firsatlar: list[dict], baslik: str, affiliate: bool = False, cagri: str | None = None) -> str:
    satirlar = [f"🛒 {baslik}", cagri or f"Kaydır, {len(firsatlar)} fırsatın hepsini gör 👉", ""]
    for f in firsatlar:
        m = KAYNAK_ADLARI.get(f["kaynak"], f["kaynak"])
        if f["guven"] == "aktuel":
            satirlar.append(f"• {f['ad']} — {para(f['fiyat'])} TL ({m})")
        else:
            satirlar.append(f"• {f['ad']} — {para(f['eski_fiyat'])} → {para(f['fiyat'])} TL "
                            f"(%{int(f['indirim'])}, {m})" + (f" · son gün {_son_gun(f)}" if _son_gun(f) else ""))
    satirlar += ["", *_money_satiri(firsatlar), *_link_satirlari(), "📌 Kaydet, alışverişe çıkmadan bak!", *_alt_bilgi(affiliate), "",
                 _etiketler(list(dict.fromkeys(f["kaynak"] for f in firsatlar)), ["#marketindirimleri"] if any(f["tur"] == "market" for f in firsatlar) else ["#onlinealışveriş"])]
    return "\n".join(satirlar)


def takvim(market: list[dict], ozel: list[dict]) -> str:
    from .calendar_tr import tr_tarih
    s = ["🗓️ BU HAFTA İNDİRİM TAKVİMİ", "Kaydet, hangi gün nereye gideceğini bil 👇", ""]
    for o in market:
        s.append(f"• {tr_tarih(o['tarih'])}: {o['baslik']}")
    if ozel:
        s += ["", "🔥 Yaklaşan büyük indirim günleri:"]
        s += [f"• {tr_tarih(o['tarih'], False)} — {o['ad']}" for o in ozel[:4]]
    s += ["", "🔔 Bildirimleri aç, fırsatları ilk sen gör!", "",
          _etiketler(["bim", "a101", "sok"], ["#aktüelürünler", "#marketindirimleri"])]
    return "\n".join(s)
