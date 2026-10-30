"""Instagram görselleri: tekli fırsat, market carousel kapağı, haftalık takvim, hikâye.

Feed: 1080x1350 (4:5, akışta en çok yer kaplayan oran). Hikâye: 1080x1920.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config, http
from .sources import KAYNAK_ADLARI, KAYNAK_RENK

log = logging.getLogger(__name__)
W, H = 1080, 1350
SH = 1920

# Akışta dikkat çeken, birbirinden belirgin farklı temalar (gönderiden gönderiye döner).
TEMALAR = [
    {"ust": "#FFD60A", "alt": "#FFB703", "yazi": "#111111", "panel": "#111111", "vurgu": "#E63946"},
    {"ust": "#FF3B30", "alt": "#C1121F", "yazi": "#FFFFFF", "panel": "#111111", "vurgu": "#FFD60A"},
    {"ust": "#7B2FF7", "alt": "#4C1D95", "yazi": "#FFFFFF", "panel": "#0B0B14", "vurgu": "#FFD60A"},
    {"ust": "#00C2A8", "alt": "#00897B", "yazi": "#0B0B0B", "panel": "#0B0B0B", "vurgu": "#FF3B30"},
]
YESIL = "#16A34A"


@lru_cache
def font(ad: str, boyut: int) -> ImageFont.FreeTypeFont:
    dosya = {"anton": "Anton-Regular.ttf", "black": "Montserrat-Black.ttf", "xbold": "Montserrat-ExtraBold.ttf",
             "bold": "Montserrat-Bold.ttf", "semi": "Montserrat-SemiBold.ttf"}[ad]
    return ImageFont.truetype(str(config.FONTLAR / dosya), boyut)


def para(x: float) -> str:
    """1299.9 -> '1.299,90' ; 1299.0 -> '1.299'"""
    if abs(x - round(x)) < 0.005:
        return f"{round(x):,}".replace(",", ".")
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _gradyan(w: int, h: int, ust: str, alt: str) -> Image.Image:
    a, b = _hex(ust), _hex(alt)
    serit = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        serit.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    return serit.resize((w, h))


def _sar(d: ImageDraw.ImageDraw, metin: str, f: ImageFont.FreeTypeFont, genislik: int, max_satir: int) -> list[str]:
    kelimeler, satirlar, s = metin.split(), [], ""
    for k in kelimeler:
        aday = f"{s} {k}".strip()
        if d.textlength(aday, font=f) <= genislik:
            s = aday
        else:
            if s:
                satirlar.append(s)
            s = k
        if len(satirlar) == max_satir:
            break
    if s and len(satirlar) < max_satir:
        satirlar.append(s)
    if len(satirlar) == max_satir and " ".join(satirlar) != " ".join(kelimeler):
        son = satirlar[-1]
        while d.textlength(son + "…", font=f) > genislik and " " in son:
            son = son.rsplit(" ", 1)[0]
        satirlar[-1] = son + "…"
    return satirlar


def _sigdir(d, metin, ad, boyut, genislik, min_boyut=24):
    while boyut > min_boyut and d.textlength(metin, font=font(ad, boyut)) > genislik:
        boyut -= 4
    return font(ad, boyut)


def _yuvarlak_kutu(img, xy, r, dolgu, golge=True):
    if golge:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).rounded_rectangle((xy[0] + 6, xy[1] + 14, xy[2] + 6, xy[3] + 14), r, fill=(0, 0, 0, 90))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(img).rounded_rectangle(xy, r, fill=dolgu)


def _tik(d, x, y, s, renk, kalinlik=7):
    d.line([(x, y + s * 0.55), (x + s * 0.38, y + s * 0.9), (x + s, y + s * 0.15)], fill=renk, width=kalinlik, joint="curve")


def _asagi_ok(d, x, y, s, renk):
    d.polygon([(x + s * 0.3, y), (x + s * 0.7, y), (x + s * 0.7, y + s * 0.5), (x + s, y + s * 0.5),
               (x + s * 0.5, y + s), (x, y + s * 0.5), (x + s * 0.3, y + s * 0.5)], fill=renk)


def _logo(d, x, y, renk, boyut=54, ok_renk="#E63946"):
    f = font("anton", boyut)
    d.text((x, y), "DÜŞTÜ MÜ?", font=f, fill=renk)
    w = d.textlength("DÜŞTÜ MÜ?", font=f)
    _asagi_ok(d, x + w + 12, y + boyut * 0.28, boyut * 0.8, ok_renk)


def _rozet(d, x, y, metin, arka, yazi, f, pad=(26, 12)):
    w = d.textlength(metin, font=f)
    kutu = (x, y, x + w + pad[0] * 2, y + f.size + pad[1] * 2 + 4)
    d.rounded_rectangle(kutu, radius=(kutu[3] - kutu[1]) // 2, fill=arka)
    d.text((x + pad[0], y + pad[1] - 2), metin, font=f, fill=yazi)
    return kutu


def _urun_gorseli(url: str | None, kutu_w: int, kutu_h: int) -> Image.Image | None:
    if not url:
        return None
    try:
        im = Image.open(io.BytesIO(http.indir(url)))
        im = ImageOps.exif_transpose(im).convert("RGBA")
    except Exception as e:
        log.warning("Görsel indirilemedi %s: %s", url, e)
        return None
    bbox = Image.new("RGB", im.size, (255, 255, 255))
    bbox.paste(im, mask=im.split()[3])
    fark = ImageOps.invert(bbox.convert("L")).point(lambda p: 255 if p > 12 else 0).getbbox()
    if fark:  # ürün etrafındaki boş beyazı kırp
        im = im.crop(fark)
    im.thumbnail((kutu_w, kutu_h), Image.LANCZOS)
    if im.width < kutu_w * 0.75 and im.height < kutu_h * 0.75:
        # Küçük görselleri büyüt ama en fazla 2.2 kat (fazlası bulanıklaşır), sonra keskinleştir.
        oran = min(kutu_w * 0.85 / im.width, kutu_h * 0.85 / im.height, 2.2)
        im = im.resize((int(im.width * oran), int(im.height * oran)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
    return im


def _indirim_cikartmasi(img, merkez, r, metin, renk, aci=-12, ust_yazi="İNDİRİM"):
    s = Image.new("RGBA", (r * 2 + 40, r * 2 + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    import math
    n, noktalar = 22, []
    for i in range(n * 2):  # patlama/yıldız şekli
        a = math.pi * i / n
        rr = r if i % 2 == 0 else r * 0.86
        noktalar.append((r + 20 + rr * math.cos(a), r + 20 + rr * math.sin(a)))
    d.polygon(noktalar, fill=renk)
    f = _sigdir(d, metin, "anton", int(r * 0.95), int(r * 1.5))
    tw = d.textlength(metin, font=f)
    d.text((r + 20 - tw / 2, r + 20 - f.size * 0.72), metin, font=f, fill="#FFFFFF")
    f2 = font("black", int(r * 0.24))
    tw2 = d.textlength(ust_yazi, font=f2)
    d.text((r + 20 - tw2 / 2, r + 20 + f.size * 0.42), ust_yazi, font=f2, fill="#FFFFFF")
    s = s.rotate(aci, resample=Image.BICUBIC, expand=False)
    golge = Image.new("RGBA", s.size, (0, 0, 0, 0))
    golge.paste((0, 0, 0, 110), mask=s.split()[3])
    golge = golge.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(golge, (merkez[0] - s.width // 2 + 6, merkez[1] - s.height // 2 + 10))
    img.alpha_composite(s, (merkez[0] - s.width // 2, merkez[1] - s.height // 2))


def son_gun(f: dict) -> str | None:
    """Kesin bitiş tarihi varsa '3 KASIM' biçiminde döner (aktüelde bitiş tahmini olduğundan yok)."""
    if not f.get("bitis") or f["guven"] == "aktuel":
        return None
    from datetime import date
    from .calendar_tr import tr_tarih
    return tr_tarih(date.fromisoformat(str(f["bitis"])[:10]), False).replace("i", "İ").upper()


# ------------------------------------------------------------------ tekli fırsat
def firsat_gorseli(f: dict, hedef: Path, hikaye: bool = False, reklam_degil: bool = True) -> Path:
    """f: fırsat sözlüğü (kod, ad, fiyat, eski_fiyat, indirim, guven, kaynak, gorsel, gecerlilik)."""
    yuk = SH if hikaye else H
    tema = TEMALAR[f["kod"] % len(TEMALAR)]
    img = _gradyan(W, yuk, tema["ust"], tema["alt"]).convert("RGBA")
    d = ImageDraw.Draw(img)
    pad = 60
    ust = 160 if hikaye else 48

    # Üst satır: logo + mağaza rozeti
    _logo(d, pad, ust, tema["yazi"], 58, tema["vurgu"] if tema["ust"] != "#FF3B30" else "#FFD60A")
    k_ad = KAYNAK_ADLARI.get(f["kaynak"], f["kaynak"].title())
    k_renk = KAYNAK_RENK.get(f["kaynak"], KAYNAK_RENK["diger"])
    fk = font("black", 34)
    kw = d.textlength(k_ad, font=fk) + 52
    _rozet(d, W - pad - kw, ust + 4, k_ad, k_renk[0], k_renk[1], fk)

    # Ürün kartı
    kart_y = ust + 102
    kart_h = 900 if hikaye else 680
    _yuvarlak_kutu(img, (pad, kart_y, W - pad, kart_y + kart_h), 44, "#FFFFFF")
    d = ImageDraw.Draw(img)
    # Ürün, sağ üstteki çıkartmaya çarpmasın diye biraz sola ve aşağı yerleşir.
    alan_w, alan_h = 660, kart_h - 150
    urun = _urun_gorseli(f.get("gorsel"), alan_w, alan_h)
    if urun:
        merkez_x = pad + (W - pad * 2 - 200) // 2 + 40
        img.alpha_composite(urun, (merkez_x - urun.width // 2, kart_y + 90 + (alan_h - urun.height) // 2))

    # İndirim çıkartması (kartın sağ üstü, kenardan taşarak)
    cikartma_merkez = (W - pad - 100, kart_y + 150)
    if f["guven"] == "aktuel":
        _indirim_cikartmasi(img, cikartma_merkez, 140, "AKTÜEL", tema["vurgu"], ust_yazi="ÜRÜN")
    else:
        _indirim_cikartmasi(img, cikartma_merkez, 140, f"%{int(f['indirim'])}", tema["vurgu"])
    d = ImageDraw.Draw(img)

    # Güven rozeti (kartın sol üstü)
    if f["guven"] in ("dogrulandi", "editor"):
        metin = "GERÇEK İNDİRİM" if f["guven"] == "dogrulandi" else "EDİTÖR SEÇİMİ"
        fr = font("black", 28)
        kutu = _rozet(d, pad + 28, kart_y + 28, "     " + metin, YESIL, "#FFFFFF", fr, pad=(22, 12))
        _tik(d, kutu[0] + 22, kutu[1] + 14, 30, "#FFFFFF", 6)

    # Bitiş tarihi (sadece kesin bilinen tarih; aktüelde bitiş tahminidir, gösterilmez)
    son = son_gun(f)
    if son:
        y_son = kart_y + 28 + (76 if f["guven"] in ("dogrulandi", "editor") else 0)
        _rozet(d, pad + 28, y_son, f"SON GÜN: {son}", "#E63946", "#FFFFFF", font("black", 28), pad=(22, 12))

    # Tasarruf şeridi (kartın sol altı)
    tasarruf = f["eski_fiyat"] - f["fiyat"]
    if f["guven"] != "aktuel" and tasarruf >= 1:
        ft = font("black", 30)
        metin = f"{para(round(tasarruf))} TL TASARRUF"
        _rozet(d, pad + 28, kart_y + kart_h - 28 - ft.size - 28, metin, "#111111", "#FFD60A", ft, pad=(24, 12))

    # Alt panel: ad + fiyatlar
    panel_y = kart_y + kart_h + 28
    panel_alt = panel_y + 362
    d.rounded_rectangle((pad, panel_y, W - pad, panel_alt), 40, fill=tema["panel"])
    ic = pad + 44
    fad = font("bold", 42)
    y = panel_y + 30
    for s in _sar(d, f["ad"], fad, W - ic * 2, 2):
        d.text((ic, y), s, font=fad, fill="#F1F1F1")
        y += 54

    taban = panel_alt - 34  # fiyatların oturacağı alt çizgi
    yeni = para(f["fiyat"]) + " TL"
    fyeni = _sigdir(d, yeni, "anton", 150, 600)
    bb = d.textbbox((0, 0), yeni, font=fyeni)
    acik_renk = "#FFD60A" if tema["vurgu"] == "#E63946" else tema["vurgu"]
    if f["guven"] != "aktuel" and f["eski_fiyat"] > f["fiyat"]:
        eski = para(f["eski_fiyat"]) + " TL"
        fe = _sigdir(d, eski, "xbold", 52, W - ic * 2 - (bb[2] - bb[0]) - 40)
        ebb = d.textbbox((0, 0), eski, font=fe)
        ey = taban - ebb[3] - 6
        d.text((ic, ey), eski, font=fe, fill="#9CA3AF")
        orta = ey + (ebb[1] + ebb[3]) / 2
        d.line((ic - 6, orta, ic + ebb[2] + 6, orta), fill=tema["vurgu"], width=7)
        if f["kaynak"] == "migroskop":
            ust_not = "Money'siz fiyat"
            fm = font("black", 30)
            d.text((W - ic - d.textlength("MONEY'Lİ FİYAT", font=fm), taban - bb[3] - 38), "MONEY'Lİ FİYAT", font=fm, fill=acik_renk)
        elif f["kaynak"] == "bim_indirim":
            ust_not = "afişteki eski fiyat"
        else:
            ust_not = "30 günün en düşük fiyatı" if f["guven"] == "dogrulandi" else "liste fiyatı"
        d.text((ic, ey + ebb[1] - 40), ust_not, font=font("semi", 26), fill="#9CA3AF")
        x_yeni = W - ic - bb[2]
    else:
        x_yeni = ic
        if f.get("gecerlilik"):
            fg = font("black", 34)
            d.text((W - ic - d.textlength(f["gecerlilik"].upper(), font=fg), taban - 90),
                   f["gecerlilik"].upper(), font=fg, fill=acik_renk)
            d.text((W - ic - d.textlength("TARİHİNDEN İTİBAREN", font=font("semi", 24)), taban - 40),
                   "TARİHİNDEN İTİBAREN", font=font("semi", 24), fill="#9CA3AF")
    d.text((x_yeni, taban - bb[3]), yeni, font=fyeni, fill="#FFFFFF")

    # En alt: çağrı
    alt_y = panel_alt + (40 if hikaye else 24)
    fcta = font("black", 36)
    cta = "REKLAM DEĞİLDİR  •  KAYDET" if reklam_degil else "KAYDET  •  ARKADAŞINA GÖNDER"
    d.text(((W - d.textlength(cta, font=fcta)) / 2, alt_y), cta, font=fcta, fill=tema["yazi"])
    fdm = font("semi", 26)
    dm = "Yorumlara LİNK yaz, DM'den gönderelim" if config.ayarlar()["yorum_dm"]["aktif"] else "Fiyatlar paylaşım anındaki fiyatlardır"
    d.text(((W - d.textlength(dm, font=fdm)) / 2, alt_y + 50), dm, font=fdm, fill=tema["yazi"])

    hedef.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(hedef, "JPEG", quality=92, optimize=True, progressive=True)
    return hedef


# ------------------------------------------------------------------ market carousel kapağı
KAPAK_TEMALAR = [
    {"ust": "#FFD60A", "alt": "#FF9F1C", "yazi": "#111111", "vurgu": "#E63946"},
    {"ust": "#FF3B30", "alt": "#B5121B", "yazi": "#FFFFFF", "vurgu": "#FFD60A"},
    {"ust": "#7B2FF7", "alt": "#4C1D95", "yazi": "#FFFFFF", "vurgu": "#FFD60A"},
    {"ust": "#00C2A8", "alt": "#00796B", "yazi": "#0B0B0B", "vurgu": "#FFFFFF"},
    {"ust": "#2563EB", "alt": "#1E3A8A", "yazi": "#FFFFFF", "vurgu": "#FFD60A"},
    {"ust": "#FF4D8D", "alt": "#C2185B", "yazi": "#FFFFFF", "vurgu": "#FFE14D"},
    {"ust": "#1F1F1F", "alt": "#000000", "yazi": "#FFFFFF", "vurgu": "#FFD60A"},
]


def carousel_kapak(firsatlar: list[dict], baslik_tarih: str, hedef: Path, renk: int = 0,
                   satirlar: tuple[str, str, str] = ("BUGÜN", "MARKETTE", "NE DÜŞTÜ?")) -> Path:
    tema = KAPAK_TEMALAR[renk % len(KAPAK_TEMALAR)]
    img = _gradyan(W, H, tema["ust"], tema["alt"]).convert("RGBA")
    d = ImageDraw.Draw(img)
    pad = 64
    _logo(d, pad, 56, tema["yazi"], 58, tema["vurgu"])
    for (y, metin), dolgu in zip(zip((190, 350, 510), satirlar), (tema["yazi"], tema["yazi"], tema["vurgu"])):
        d.text((pad, y), metin, font=_sigdir(d, metin, "anton", 150, W - pad * 2), fill=dolgu)
    d.text((pad, 722), baslik_tarih.replace("i", "İ").upper(), font=font("black", 40), fill=tema["yazi"])

    # Küçük ürün önizlemeleri
    n = min(3, len(firsatlar))
    kw = (W - pad * 2 - 30 * (n - 1)) // max(n, 1)
    for i, f in enumerate(firsatlar[:n]):
        x = pad + i * (kw + 30)
        _yuvarlak_kutu(img, (x, 780, x + kw, 780 + kw), 32, "#FFFFFF")
        u = _urun_gorseli(f.get("gorsel"), kw - 50, kw - 50)
        if u:
            img.alpha_composite(u, (x + (kw - u.width) // 2, 780 + (kw - u.height) // 2))
        d = ImageDraw.Draw(img)
        if f["guven"] != "aktuel":
            _rozet(d, x + 14, 794, f"%{int(f['indirim'])}", "#E63946", "#FFFFFF", font("anton", 40), pad=(16, 6))

    marketler = list(dict.fromkeys(f["kaynak"] for f in firsatlar))
    x = pad
    for m in marketler[:5]:
        r = KAYNAK_RENK.get(m, KAYNAK_RENK["diger"])
        k = _rozet(d, x, 1150, KAYNAK_ADLARI.get(m, m), r[0], r[1], font("black", 34))
        x = k[2] + 16
    f_k = font("black", 40)
    kay = "KAYDIR  >>>"
    d.text((W - pad - d.textlength(kay, font=f_k), 1240), kay, font=f_k, fill=tema["yazi"])
    img.convert("RGB").save(hedef, "JPEG", quality=92, optimize=True)
    return hedef


# ------------------------------------------------------------------ haftalık takvim
def takvim_gorseli(market: list[dict], ozel: list[dict], hedef: Path) -> Path:
    from .calendar_tr import tr_tarih
    img = _gradyan(W, H, "#111111", "#1F1147").convert("RGBA")
    d = ImageDraw.Draw(img)
    pad = 64
    _logo(d, pad, 56, "#FFFFFF", 54, "#FFD60A")
    d.text((pad, 160), "BU HAFTA", font=font("anton", 120), fill="#FFFFFF")
    d.text((pad, 290), "İNDİRİM TAKVİMİ", font=font("anton", 120), fill="#FFD60A")
    y = 460
    for o in market[:8]:
        r = KAYNAK_RENK.get(o["market"], KAYNAK_RENK["diger"])
        d.rounded_rectangle((pad, y, W - pad, y + 82), 24, fill="#FFFFFF")
        k = _rozet(d, pad + 16, y + 12, KAYNAK_ADLARI.get(o["market"], o["market"]), r[0], r[1], font("black", 30), pad=(18, 8))
        d.text((k[2] + 22, y + 10), tr_tarih(o["tarih"]), font=font("black", 30), fill="#111111")
        d.text((k[2] + 22, y + 46), o["baslik"], font=_sigdir(d, o["baslik"], "semi", 24, W - pad - k[2] - 50), fill="#4B5563")
        y += 96
    if ozel:
        d.text((pad, y + 10), "YAKLAŞAN BÜYÜK İNDİRİMLER", font=font("black", 34), fill="#FFD60A")
        y += 62
        for o in ozel[:3]:
            metin = f"{tr_tarih(o['tarih'], False)} • {o['ad']}" + (f"  ({o['kalan']} gün)" if o["kalan"] else "  (BUGÜN)")
            d.text((pad, y), metin, font=_sigdir(d, metin, "bold", 32, W - pad * 2), fill="#FFFFFF")
            y += 46
    f_s = font("black", 32)
    s = "KAYDET • ARKADAŞINA GÖNDER"
    d.text(((W - d.textlength(s, font=f_s)) / 2, H - 80), s, font=f_s, fill="#FFD60A")
    img.convert("RGB").save(hedef, "JPEG", quality=92, optimize=True)
    return hedef
