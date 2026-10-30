"""Reels videosu, 1080x1920 MP4 (H.264/AAC, ses.py'den telifsiz müzik ve efekt). Market broşürü düzeni:
ışıklı zemin, indirim rozeti, fiyat bloğu, çerçeveli ürün kartı. Her Reels'te renkler, zemin deseni, rozet ve
fiyat etiketi biçimi, hareketler ve yerleşim değişir (stil_sec). Ekrandaki koşul ve tarihler fırsatın kendi verisinden gelir."""
from __future__ import annotations

import math
import random
import subprocess
import tempfile
from datetime import date
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter

from . import config, render, ses
from .calendar_tr import tr_tarih
from .render import SH, W, font
from .sources import KAYNAK_ADLARI

FPS = 30
KAPAK_SN, URUN_SN, SON_SN = 1.7, 2.4, 2.0
KART_Y, KART_H = 640, 800
SS = 3  # şekiller 3 kat büyük çizilip küçültülür: kenarlar yumuşak olur

# z: zemin üst/alt renk, g: orta parıltı, i: ışık rengi. Rozet ve blok renkleri zemine göre seçildi.
PALETLER = (
    {"ad": "altın", "z": ("#5E4706", "#1E1502"), "g": (214, 164, 24), "i": (255, 226, 120), "kart": "#FFD400",
     "rozet": ("#F4323D", "#D00814"), "rozet_kenar": "#FFFFFF", "rozet_yazi": "#FFFFFF", "serit": "#FFD400", "serit_yazi": "#E30A17",
     "blok": ("#F01A27", "#C80612"), "blok_ic": "#FFD400", "blok_yazi": "#E30A17", "eski": "#FFFFFF", "cizgi": "#0B4FC4",
     "kosul": "#FFD400", "kosul_yazi": "#3A2A00", "tarih": ("#0B4FC4", "#062F86")},
    {"ad": "kırmızı", "z": ("#7A0610", "#240104"), "g": (226, 28, 44), "i": (255, 214, 150), "kart": "#FFD400",
     "rozet": ("#FFE24A", "#FFC400"), "rozet_kenar": "#FFFFFF", "rozet_yazi": "#C00010", "serit": "#FFFFFF", "serit_yazi": "#C00010",
     "blok": ("#FFE24A", "#FFC400"), "blok_ic": "#FFFFFF", "blok_yazi": "#D00814", "eski": "#5A3A00", "cizgi": "#D00814",
     "kosul": "#FFFFFF", "kosul_yazi": "#7A0610", "tarih": ("#111111", "#333333")},
    {"ad": "mavi", "z": ("#0A2A78", "#030B24"), "g": (30, 91, 224), "i": (143, 199, 255), "kart": "#FFD400",
     "rozet": ("#FF3B47", "#D00814"), "rozet_kenar": "#FFD400", "rozet_yazi": "#FFFFFF", "serit": "#FFFFFF", "serit_yazi": "#0A2A78",
     "blok": ("#FFE24A", "#FFC400"), "blok_ic": "#D00814", "blok_yazi": "#FFFFFF", "eski": "#0A2A78", "cizgi": "#D00814",
     "kosul": "#FFFFFF", "kosul_yazi": "#0A2A78", "tarih": ("#E30A17", "#A80712")},
    {"ad": "mor", "z": ("#4A148C", "#14052C"), "g": (142, 45, 226), "i": (235, 190, 255), "kart": "#FF4D8D",
     "rozet": ("#FF5C9A", "#E01E6C"), "rozet_kenar": "#FFFFFF", "rozet_yazi": "#FFFFFF", "serit": "#FFE24A", "serit_yazi": "#4A148C",
     "blok": ("#FF5C9A", "#E01E6C"), "blok_ic": "#FFFFFF", "blok_yazi": "#6A1B9A", "eski": "#FFFFFF", "cizgi": "#FFE24A",
     "kosul": "#FFE24A", "kosul_yazi": "#4A148C", "tarih": ("#6A1B9A", "#4A148C")},
    {"ad": "yeşil", "z": ("#075E3B", "#021C12"), "g": (18, 166, 99), "i": (182, 255, 214), "kart": "#FFD400",
     "rozet": ("#FF8A1F", "#F05A00"), "rozet_kenar": "#FFFFFF", "rozet_yazi": "#FFFFFF", "serit": "#FFD400", "serit_yazi": "#075E3B",
     "blok": ("#FF8A1F", "#F05A00"), "blok_ic": "#FFE24A", "blok_yazi": "#075E3B", "eski": "#FFFFFF", "cizgi": "#075E3B",
     "kosul": "#FFFFFF", "kosul_yazi": "#075E3B", "tarih": ("#0B8A57", "#075E3B")},
    {"ad": "siyah", "z": ("#232326", "#050506"), "g": (86, 86, 94), "i": (255, 212, 0), "kart": "#FFD400",
     "rozet": ("#FFE24A", "#FFC400"), "rozet_kenar": "#111111", "rozet_yazi": "#111111", "serit": "#E30A17", "serit_yazi": "#FFFFFF",
     "blok": ("#FFE24A", "#FFC400"), "blok_ic": "#111111", "blok_yazi": "#FFD400", "eski": "#111111", "cizgi": "#E30A17",
     "kosul": "#FFD400", "kosul_yazi": "#111111", "tarih": ("#111111", "#333333")},
)
ROZETLER = ("kalkan", "patlama", "daire", "altigen")
BLOKLAR = ("yuvarlak", "bilet", "kesik")
ROZET_HAREKET = ("yukari", "nabiz", "salin", "yana")
FIYAT_GIRIS = ("yandan", "ustten", "zum", "alttan", "ters_yandan")
DESENLER = ("sahne", "bokeh", "isin", "serit")


def stil_sec(no: int) -> dict:
    """Uzunlukları ortak böleni az listelerden seçer: art arda iki Reels'te her parça değişir, kombinasyon geç tekrarlar."""
    return {"p": PALETLER[no % len(PALETLER)], "rozet": ROZETLER[no % len(ROZETLER)], "blok": BLOKLAR[no % len(BLOKLAR)],
            "rozet_hareket": ROZET_HAREKET[(no + no // 4) % len(ROZET_HAREKET)], "giris": FIYAT_GIRIS[no % len(FIYAT_GIRIS)],
            "desen": DESENLER[(no + no // 6) % len(DESENLER)], "ayna": no % 2 == 1}


def _ease(t: float) -> float:
    t = min(max(t, 0), 1)
    return 1 - (1 - t) ** 3


def _firla(t: float) -> float:
    """0->1, sonda hafif taşıp oturur."""
    t = min(max(t, 0), 1)
    return 1 + 2.7 * (t - 1) ** 3 + 1.7 * (t - 1) ** 2


def _buyuk(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def _golgeli(k: Image.Image, bosluk: int = 30, kay: int = 12, koyu: int = 130, bulanik: int = 14) -> Image.Image:
    """Katmanın çevresine yumuşak gölge ekler (konum hesapları için bosluk kadar büyür)."""
    t = Image.new("RGBA", (k.width + bosluk * 2, k.height + bosluk * 2), (0, 0, 0, 0))
    g = Image.new("RGBA", t.size, (0, 0, 0, 0))
    g.paste((0, 0, 0, koyu), (bosluk, bosluk + kay), k.getchannel("A"))
    t.alpha_composite(g.filter(ImageFilter.GaussianBlur(bulanik)))
    t.alpha_composite(k, (bosluk, bosluk))
    return t


def _sekil(w: int, h: int, ciz) -> Image.Image:
    b = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    ciz(ImageDraw.Draw(b), SS)
    return b.resize((w, h), Image.LANCZOS)


def _maske(w: int, h: int, ciz) -> Image.Image:
    b = Image.new("L", (w * SS, h * SS), 0)
    ciz(ImageDraw.Draw(b), SS)
    return b.resize((w, h), Image.LANCZOS)


def _boyali(w: int, h: int, maske: Image.Image, renkler: tuple[str, str]) -> Image.Image:
    k = render._gradyan(w, h, *renkler).convert("RGBA")
    k.putalpha(maske)
    return k


def _ortala(d, cx: float, y: float, metin: str, f, renk: str, **k) -> None:
    d.text((cx - d.textlength(metin, font=f) / 2, y), metin, font=f, fill=renk, **k)


def _sigan(d, metin: str, ad: str, boyut: int, genislik: int):
    return render._sigdir(d, metin, ad, boyut, genislik)


# ------------------------------------------------------------------ zemin
def _desen(d: ImageDraw.ImageDraw, ad: str, faz: int, isik: tuple[int, int, int]) -> None:
    r, g, b = isik
    rnd = random.Random(11)
    if ad == "sahne":  # altta uzaklaştıkça küçülen ışık sıraları, tek-çift yanıp söner
        for _ in range(9):
            x, y, ry = rnd.randint(0, W), rnd.randint(0, 1400), rnd.randint(50, 120)
            d.ellipse((x - ry, y - ry, x + ry, y + ry), fill=(r, g, b, 45 if (rnd.random() < 0.5) == bool(faz) else 14))
        for sira, (y, ry, adet) in enumerate(((1520, 34, 9), (1625, 46, 7), (1745, 62, 6), (1880, 82, 5))):
            for j in range(adet):
                x = (j + 0.5 + (sira % 2) * 0.25) * W / adet
                d.ellipse((x - ry, y - ry * 0.3, x + ry, y + ry * 0.3), fill=(r, g, b, 225 if (j + sira) % 2 == faz else 70))
    elif ad == "bokeh":  # ekranın her yerinde iri, yumuşak daireler
        for _ in range(34):
            x, y, ry = rnd.randint(-40, W + 40), rnd.randint(0, SH), rnd.randint(30, 130)
            d.ellipse((x - ry, y - ry, x + ry, y + ry), fill=(r, g, b, 70 if (rnd.random() < 0.5) == bool(faz) else 18))
    elif ad == "isin":  # üstten yayılan ışınlar
        for j in range(14):
            a0 = math.pi * (j + faz * 0.5) / 14
            a1 = a0 + math.pi / 28
            d.polygon([(W / 2, -200), (W / 2 + 3000 * math.cos(a0), -200 + 3000 * math.sin(a0)),
                       (W / 2 + 3000 * math.cos(a1), -200 + 3000 * math.sin(a1))], fill=(r, g, b, 42))
    else:  # çapraz parlak şeritler
        for j in range(-3, 14):
            x = j * 190 + faz * 95
            d.polygon([(x, 0), (x + 70, 0), (x + 70 - 700, SH), (x - 700, SH)], fill=(r, g, b, 34))


@lru_cache(maxsize=2)
def _zeminler(paleti: str, desen: str) -> tuple[Image.Image, Image.Image]:
    p = next(x for x in PALETLER if x["ad"] == paleti)
    taban = render._gradyan(W, SH, *p["z"]).convert("RGBA")
    parilti = Image.new("RGBA", (W, SH), (0, 0, 0, 0))
    ImageDraw.Draw(parilti).ellipse((-200, 150, W + 200, 1500), fill=(*p["g"], 200))
    taban.alpha_composite(parilti.filter(ImageFilter.GaussianBlur(170)))
    sonuc = []
    for faz in range(2):
        k = Image.new("RGBA", (W, SH), (0, 0, 0, 0))
        _desen(ImageDraw.Draw(k), desen, faz, p["i"])
        z = taban.copy()
        z.alpha_composite(k.filter(ImageFilter.GaussianBlur(7)))
        sonuc.append(z.convert("RGB"))
    return sonuc[0], sonuc[1]


def _zemin(stil: dict, t: float) -> Image.Image:
    a, b = _zeminler(stil["p"]["ad"], stil["desen"])
    return Image.blend(a, b, 0.5 + 0.5 * math.sin(t * 2 * math.pi * 0.9)).convert("RGBA")


# ------------------------------------------------------------------ parçalar
def _rozet_sekli(ad: str, d, s: int, oran: float, deger: int = 255) -> None:
    """400x400 alanda ortadan oran kadar küçültülmüş şekil."""
    m = 200

    def nokta(x, y):
        return ((m + (x - m) * oran) * s, (m + (y - m) * oran) * s)
    if ad == "daire":
        d.ellipse((*nokta(14, 14), *nokta(386, 386)), fill=deger)
    elif ad == "patlama":
        d.polygon([nokta(m + (196 if i % 2 == 0 else 166) * math.cos(math.pi * i / 16),
                         m + (196 if i % 2 == 0 else 166) * math.sin(math.pi * i / 16)) for i in range(32)], fill=deger)
    elif ad == "altigen":
        d.polygon([nokta(m + 194 * math.cos(math.pi / 3 * i + math.pi / 6), m + 194 * math.sin(math.pi / 3 * i + math.pi / 6))
                   for i in range(6)], fill=deger)
    else:
        d.polygon([nokta(x, y) for x, y in ((30, 90), (200, 14), (370, 90), (370, 250), (200, 390), (30, 250))], fill=deger)


def _rozet(f: dict, stil: dict) -> Image.Image:
    p = stil["p"]
    w = h = 400
    k = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    kenar = _sekil(w, h, lambda d, s: _rozet_sekli(stil["rozet"], d, s, 1.0, p["rozet_kenar"]))
    k.alpha_composite(kenar)
    k.alpha_composite(_boyali(w, h, _maske(w, h, lambda d, s: _rozet_sekli(stil["rozet"], d, s, 0.88)), p["rozet"]))

    def serit(d, s):
        d.polygon([(x * s, y * s) for x, y in ((0, 232), (28, 232), (28, 300), (0, 300), (14, 266))], fill=p["serit"])
        d.polygon([(x * s, y * s) for x, y in ((400, 232), (372, 232), (372, 300), (400, 300), (386, 266))], fill=p["serit"])
        d.rectangle((16 * s, 222 * s, 384 * s, 296 * s), fill=p["serit"])
    k.alpha_composite(_sekil(w, h, serit))
    d = ImageDraw.Draw(k)
    if f["guven"] == "aktuel":
        _ortala(d, 200, 100, "YENİ", font("black", 104), p["rozet_yazi"])
        _ortala(d, 200, 234, "AKTÜEL", font("black", 50), p["serit_yazi"])
    else:
        sayi = str(int(f["indirim"]))
        fs, fy = font("black", 138), font("black", 66)
        gs = d.textlength(sayi, font=fs) + d.textlength("%", font=fy) + 6
        x = 200 - gs / 2
        d.text((x, 118), "%", font=fy, fill=p["rozet_yazi"])
        d.text((x + d.textlength("%", font=fy) + 6, 56), sayi, font=fs, fill=p["rozet_yazi"])
        _ortala(d, 200, 234, "İNDİRİM", font("black", 50), p["serit_yazi"])
    return _golgeli(k, koyu=150)


def _blok_maskesi(ad: str, w: int, h: int) -> Image.Image:
    def ciz(d, s):
        if ad == "kesik":
            c = 46
            d.polygon([(x * s, y * s) for x, y in ((c, 0), (w - c, 0), (w, c), (w, h - c), (w - c, h), (c, h), (0, h - c), (0, c))], fill=255)
        else:
            d.rounded_rectangle((0, 0, (w - 1) * s, (h - 1) * s), 34 * s, fill=255)
            if ad == "bilet":  # kenar çentikleri
                for x in (0, w):
                    d.ellipse(((x - 20) * s, (h / 2 - 20) * s, (x + 20) * s, (h / 2 + 20) * s), fill=0)
    return _maske(w, h, ciz)


def _fiyat_yaz(d, x0: int, x1: int, y: int, h: int, fiyat: float, renk: str) -> None:
    """149,95 -> büyük 149, üstte küçük ,95, yanında ₺; hepsi kutuya sığar ve ortalanır."""
    parca = render.para(fiyat).split(",")
    tam, kurus = parca[0], ("," + parca[1]) if len(parca) > 1 else ""
    boyut = 190
    while boyut > 60:
        fb, fk, ft = font("black", boyut), font("black", int(boyut * 0.42)), font("black", int(boyut * 0.5))
        gen = d.textlength(tam, font=fb) + max(d.textlength(kurus, font=fk), d.textlength("₺", font=ft)) + 14
        if gen <= x1 - x0 - 24 and fb.getbbox(tam)[3] - fb.getbbox(tam)[1] <= h - 20:
            break
        boyut -= 6
    bb = fb.getbbox(tam)
    x = (x0 + x1 - gen) / 2
    yb = y + (h - (bb[3] - bb[1])) / 2 - bb[1]
    d.text((x, yb), tam, font=fb, fill=renk)
    xs = x + d.textlength(tam, font=fb) + 14
    if kurus:
        d.text((xs, yb + bb[1]), kurus, font=fk, fill=renk)
        d.text((xs, yb + bb[1] + fk.size + 8), "₺", font=ft, fill=renk)
    else:
        d.text((xs, yb + bb[3] - ft.getbbox("₺")[3]), "₺", font=ft, fill=renk)


def _fiyat_blok(f: dict, stil: dict) -> Image.Image:
    p = stil["p"]
    w, h = 500, 350
    eski_var = f["guven"] != "aktuel" and f["eski_fiyat"] > f["fiyat"]
    ust = 118 if eski_var else 22
    k = _boyali(w, h, _blok_maskesi(stil["blok"], w, h), p["blok"])
    k.alpha_composite(_sekil(w, h, lambda d, s: d.rounded_rectangle((26 * s, ust * s, (w - 27) * s, (h - 24) * s), 22 * s, fill=p["blok_ic"])))
    d = ImageDraw.Draw(k)
    if eski_var:
        eski = render.para(f["eski_fiyat"]) + " ₺"
        fe = _sigan(d, eski, "black", 84, w - 110)
        bb = d.textbbox((0, 0), eski, font=fe)
        ex = (w - (bb[2] - bb[0])) / 2 - bb[0]
        d.text((ex, 12 - bb[1] + (96 - (bb[3] - bb[1])) / 2), eski, font=fe, fill=p["eski"])
        k.alpha_composite(_sekil(w, 118, lambda c, s: c.line((ex * s, 90 * s, (ex + bb[2] - bb[0]) * s, 28 * s), fill=p["cizgi"], width=10 * s)))
    _fiyat_yaz(d, 26, w - 26, ust, h - 24 - ust, f["fiyat"], p["blok_yazi"])
    return _golgeli(k, koyu=170)


def _kosul_metni(f: dict) -> tuple[str, str]:
    if f["guven"] == "aktuel":
        return "AKTÜEL ÜRÜN", "STOKLARLA SINIRLIDIR"
    if f["kaynak"] == "migroskop":
        return "MONEY'Lİ FİYAT", "İNDİRİM MONEY'SİZ FİYATA GÖRE"
    if f["kaynak"] == "bim_indirim":
        return "AFİŞ FİYATI", "İNDİRİM AFİŞTEKİ ESKİ FİYATA GÖRE"
    if f["guven"] == "dogrulandi":
        return "GERÇEK İNDİRİM", "SON 30 GÜNÜN EN DÜŞÜĞÜNDEN UCUZ"
    return "İNDİRİMLİ FİYAT", "İNDİRİM LİSTE FİYATINA GÖRE"


def _kosul(f: dict, stil: dict) -> Image.Image:
    p = stil["p"]
    w, h = 500, 92
    k = _sekil(w, h, lambda d, s: d.rounded_rectangle((0, 0, (w - 1) * s, (h - 1) * s), 18 * s, fill=p["kosul"]))
    d = ImageDraw.Draw(k)
    u, a = _kosul_metni(f)
    _ortala(d, w / 2, 10, u, font("black", 30), p["kosul_yazi"])
    _ortala(d, w / 2, 50, a, _sigan(d, a, "bold", 24, w - 30), p["kosul_yazi"])
    return _golgeli(k, bosluk=20, kay=6, koyu=120, bulanik=8)


def _tarih_rozeti(f: dict, bugun: date, stil: dict) -> Image.Image:
    w, h = 330, 128
    ad = _buyuk(KAYNAK_ADLARI.get(f["kaynak"], f["kaynak"]))
    son = render.son_gun(f)
    if son:
        alt = f"SON GÜN {son}"
    elif f["guven"] == "aktuel" and f.get("gecerlilik"):
        alt = _buyuk(f["gecerlilik"])
    else:
        alt = _buyuk(tr_tarih(bugun, False))
    k = _sekil(w, h, lambda d, s: d.rounded_rectangle((0, 0, (w - 1) * s, (h - 1) * s), 22 * s, fill="#DDE7F5"))
    k.alpha_composite(_boyali(w, h, _maske(w, h, lambda d, s: d.rounded_rectangle((6 * s, 6 * s, (w - 7) * s, (h - 7) * s), 18 * s, fill=255)), stil["p"]["tarih"]))
    d = ImageDraw.Draw(k)
    _ortala(d, w / 2, 22, ad, _sigan(d, ad, "black", 40, w - 40), "#FFFFFF")
    _ortala(d, w / 2, 76, alt, _sigan(d, alt, "bold", 28, w - 40), "#FFFFFF")
    return k


def _kart(f: dict, bugun: date, stil: dict) -> Image.Image:
    w, h = 1000, KART_H

    def ciz(d, s):
        d.rounded_rectangle((0, 0, (w - 1) * s, (h - 1) * s), 56 * s, fill=stil["p"]["kart"])
        d.rounded_rectangle((20 * s, 20 * s, (w - 21) * s, (h - 21) * s), 40 * s, fill="#FFFFFF")
    k = _sekil(w, h, ciz)
    k.alpha_composite(_tarih_rozeti(f, bugun, stil), (w - 330 - 44, 44))
    return _golgeli(k, koyu=150)


def _ad_bandi(f: dict) -> Image.Image:
    w, h = 1000, 130
    k = _sekil(w, h, lambda d, s: d.rounded_rectangle((0, 0, (w - 1) * s, (h - 1) * s), 26 * s, fill=(12, 10, 8, 225)))
    d = ImageDraw.Draw(k)
    fa = font("xbold", 40)
    satirlar = render._sar(d, f["ad"], fa, w - 70, 2)
    y = (h - len(satirlar) * 50) / 2
    for s in satirlar:
        _ortala(d, w / 2, y, s, fa, "#FFFFFF")
        y += 50
    return k


def _imza(reklam_degil: bool) -> Image.Image:
    metin = "@" + config.ayarlar()["marka"]["instagram_kullanici"] + ("  ·  REKLAM DEĞİLDİR" if reklam_degil else "")
    k = Image.new("RGBA", (W, 40), (0, 0, 0, 0))
    _ortala(ImageDraw.Draw(k), W / 2, 2, metin, font("bold", 26), "#FFFFFF")
    return k


def _olcekli(k: Image.Image, o: float) -> Image.Image:
    return k.resize((max(int(k.width * o), 1), max(int(k.height * o), 1)), Image.BICUBIC)


def _ortadan(kare: Image.Image, k: Image.Image, cx: float, cy: float) -> None:
    x, y = int(cx - k.width / 2), int(cy - k.height / 2)
    if x >= W or y >= SH or x + k.width <= 0 or y + k.height <= 0:
        return
    kare.alpha_composite(k, (max(x, 0), max(y, 0)), (max(-x, 0), max(-y, 0)))


def _girisli(kare: Image.Image, k: Image.Image, cx: float, cy: float, t: float, giris: str, yon: int) -> None:
    """Fiyat parçası stilin giriş hareketiyle gelir; yon: en yakın ekran kenarı (+1 sağ, -1 sol)."""
    o = _firla(t / 0.35)
    if t <= 0:
        return
    if giris == "zum":
        _ortadan(kare, _olcekli(k, max(o, 0.02)), cx, cy)
    elif giris == "ustten":
        _ortadan(kare, k, cx, cy - (1 - o) * 700)
    elif giris == "alttan":
        _ortadan(kare, k, cx, cy + (1 - o) * 1000)
    elif giris == "ters_yandan":
        _ortadan(kare, k, cx - yon * (1 - o) * 1100, cy)
    else:
        _ortadan(kare, k, cx + yon * (1 - o) * 700, cy)


def _rozet_ciz(kare: Image.Image, rozet: Image.Image, cx: float, cy: float, t: float, hareket: str) -> None:
    """Rozet fırlar, sonra stilin sürekli hareketini yapar."""
    if t <= 0:
        return
    o = max(_firla(t / 0.28), 0.02)
    dalga = math.sin(t * 2 * math.pi * 1.25)
    k = rozet
    if hareket == "nabiz":
        o *= 1 + 0.07 * dalga
    elif hareket == "salin":
        k = k.rotate(9 * dalga, resample=Image.BICUBIC)
    elif hareket == "yana":
        cx += 16 * dalga
    else:
        cy += 18 * dalga
    _ortadan(kare, _olcekli(k, o), cx, cy)


# ------------------------------------------------------------------ sahneler
def _urun_kareleri(f: dict, bugun: date, reklam_degil: bool, stil: dict):
    rozet, blok, kosul = _rozet(f, stil), _fiyat_blok(f, stil), _kosul(f, stil)
    kart, band, imza = _kart(f, bugun, stil), _ad_bandi(f), _imza(reklam_degil)
    urun = render._urun_gorseli(f.get("gorsel"), 620, 660)
    kart_cy = KART_Y + KART_H / 2
    rozet_x, blok_x, yon = (818, 310, -1) if stil["ayna"] else (262, 770, 1)
    for i in range(int(URUN_SN * FPS)):
        t = i / FPS
        kare = _zemin(stil, t)
        # Kart ve ürün alttan gelir, ürün yerine otururken büyür.
        kay = (1 - _ease(t / 0.3)) * 1100
        _ortadan(kare, kart, W / 2, kart_cy + kay)
        if urun:
            o = 0.86 + 0.14 * _firla((t - 0.08) / 0.3) + 0.012 * t
            _ortadan(kare, _olcekli(urun, o), 395, kart_cy + 20 + kay)
        _ortadan(kare, band, W / 2, KART_Y + KART_H + 82 + kay)
        if kay < 1:
            kare.alpha_composite(imza, (0, KART_Y + KART_H + 158))
        _girisli(kare, blok, blok_x, 325, t - 0.12, stil["giris"], yon)
        _girisli(kare, kosul, blok_x, 560, t - 0.28, stil["giris"], yon)
        _rozet_ciz(kare, rozet, rozet_x, 375, t - 0.22, stil["rozet_hareket"])
        yield kare.convert("RGB").tobytes()


def _plaka(satirlar: list[str], stil: dict) -> Image.Image:
    """Dış renkli çerçeve içinde iki satırlık plaka; son satır çerçevenin üstünde."""
    p = stil["p"]
    w, h = 980, 760
    k = _boyali(w, h, _blok_maskesi(stil["blok"], w, h), p["blok"])
    k.alpha_composite(_sekil(w, h, lambda d, s: d.rounded_rectangle((28 * s, 26 * s, (w - 29) * s, 520 * s), 30 * s, fill=p["blok_ic"])))
    d = ImageDraw.Draw(k)
    y = 60
    for s in satirlar[:2]:
        fs = _sigan(d, s, "black", 190, w - 120)
        bb = fs.getbbox(s)
        _ortala(d, w / 2, y - bb[1] + (210 - (bb[3] - bb[1])) / 2, s, fs, p["blok_yazi"])
        y += 225
    fs = _sigan(d, satirlar[2], "black", 150, w - 90)
    bb = fs.getbbox(satirlar[2])
    _ortala(d, w / 2, 532 - bb[1] + (200 - (bb[3] - bb[1])) / 2, satirlar[2], fs, p["eski"])
    return _golgeli(k, koyu=170, bulanik=20)


def _yazi_sahnesi(satirlar: list[str], alt: str | None, sure: float, stil: dict):
    plaka = _plaka(satirlar, stil)
    alt_k = None
    if alt:
        fa = font("black", 50)
        ga = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(alt, font=fa)) + 80
        alt_k = _boyali(ga, 96, _maske(ga, 96, lambda d, s: d.rounded_rectangle((0, 0, (ga - 1) * s, 95 * s), 26 * s, fill=255)), stil["p"]["tarih"])
        _ortala(ImageDraw.Draw(alt_k), ga / 2, 18, alt, fa, "#FFFFFF")
        alt_k = _golgeli(alt_k, bosluk=20, kay=6, bulanik=8)
    for i in range(int(sure * FPS)):
        t = i / FPS
        kare = _zemin(stil, t)
        _girisli(kare, plaka, W / 2, 700, t, "zum" if stil["giris"] in ("yandan", "ters_yandan") else stil["giris"], 1)
        if alt_k:
            _ortadan(kare, alt_k, W / 2 + (1 - _firla((t - 0.4) / 0.3)) * 1000, 1190 + 8 * math.sin(t * 2 * math.pi * 1.25))
        yield kare.convert("RGB").tobytes()


def _ses_olaylari(n: int) -> list[tuple[str, float]]:
    """Görüntüdeki girişlerle aynı anda çalan efektler."""
    olay = [("pop", 0.05), ("pop", 0.55)]
    for i in range(n):
        b = KAPAK_SN + i * URUN_SN
        olay += [("ufleme", b - 0.12), ("pop", b + 0.3), ("ding", b + 0.42)]
    return olay + [("ufleme", KAPAK_SN + n * URUN_SN - 0.12), ("pop", KAPAK_SN + n * URUN_SN + 0.1)]


def uret(firsatlar: list[dict], kapak_satirlari: tuple[str, str, str], hedef: Path, reklam_degil: bool = True,
         stil_no: int = 0) -> Path:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as g:
        sure = KAPAK_SN + len(firsatlar) * URUN_SN + SON_SN
        wav = ses.uret(Path(g) / "ses.wav", sure, _ses_olaylari(len(firsatlar)), stil_no)
        return _kodla(firsatlar, kapak_satirlari, hedef, reklam_degil, stil_no, wav)


def _kodla(firsatlar: list[dict], kapak_satirlari: tuple[str, str, str], hedef: Path, reklam_degil: bool,
           stil_no: int, wav: Path) -> Path:
    stil = stil_sec(stil_no)
    bugun = config.simdi().date()
    oranlar = [int(f["indirim"]) for f in firsatlar if f["guven"] != "aktuel"]
    kapak_alt = f"EN FAZLA %{max(oranlar)} İNDİRİM" if oranlar else None
    hesap = "@" + config.ayarlar()["marka"]["instagram_kullanici"]
    p = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{SH}", "-r", str(FPS), "-i", "-",
                          "-i", str(wav), "-map", "0:v", "-map", "1:a", "-shortest", "-ac", "2",
                          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                          "-profile:v", "high", "-g", "60", "-c:a", "aac", "-b:a", "128k",
                          "-movflags", "+faststart", str(hedef)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for parca in _yazi_sahnesi(list(kapak_satirlari), kapak_alt, KAPAK_SN, stil):
            p.stdin.write(parca)
        for f in firsatlar:
            for parca in _urun_kareleri(f, bugun, reklam_degil, stil):
                p.stdin.write(parca)
        for parca in _yazi_sahnesi(["DÜŞEN FİYATI", "KAÇIRMA", "TAKİP ET"], hesap, SON_SN, stil):
            p.stdin.write(parca)
        _, hata = p.communicate(timeout=240)
    except Exception:
        p.kill()
        raise
    if p.returncode:
        raise RuntimeError(f"ffmpeg: {hata.decode(errors='replace')[:300]}")
    return hedef
