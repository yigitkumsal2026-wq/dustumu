"""İndirim günleri takvimi: market haftalık günleri + e-ticaret kampanya günleri."""
from __future__ import annotations

from datetime import date, timedelta

from . import config

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık"]

# Dini bayramlar ay takvimine göre kayar (Diyanet takvimine göre, gerekirse güncelle).
BAYRAMLAR = {
    2026: [("Kurban Bayramı", date(2026, 5, 27))],
    2027: [("Ramazan Bayramı", date(2027, 3, 9)), ("Kurban Bayramı", date(2027, 5, 16))],
    2028: [("Ramazan Bayramı", date(2028, 2, 26)), ("Kurban Bayramı", date(2028, 5, 4))],
}


def _ayin_ninci_gunu(yil: int, ay: int, haftagunu: int, n: int) -> date:
    d = date(yil, ay, 1)
    d += timedelta(days=(haftagunu - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def tr_tarih(d: date, gun_adi: bool = True) -> str:
    s = f"{d.day} {AYLAR[d.month]}"
    return f"{s} {GUNLER[d.weekday()]}" if gun_adi else s


def ozel_gunler(yil: int) -> list[dict]:
    bf = _ayin_ninci_gunu(yil, 11, 3, 4) + timedelta(days=1)  # Şükran Günü'nden sonraki Cuma
    g = [
        ("Sevgililer Günü indirimleri", date(yil, 2, 14), "eticaret"),
        ("Kadınlar Günü indirimleri", date(yil, 3, 8), "eticaret"),
        ("Anneler Günü indirimleri", _ayin_ninci_gunu(yil, 5, 6, 2), "eticaret"),
        ("Babalar Günü indirimleri", _ayin_ninci_gunu(yil, 6, 6, 3), "eticaret"),
        ("Prime Day (Amazon, tahmini)", _ayin_ninci_gunu(yil, 7, 1, 2), "eticaret"),
        ("Okula Dönüş kampanyaları", date(yil, 9, 1), "eticaret"),
        ("9.9 indirimleri", date(yil, 9, 9), "eticaret"),
        ("10.10 indirimleri", date(yil, 10, 10), "eticaret"),
        ("Efsane / Muhteşem Kasım başlıyor", date(yil, 11, 1), "eticaret"),
        ("11.11 Bekarlar Günü indirimleri", date(yil, 11, 11), "eticaret"),
        ("Black Friday (Kara Cuma)", bf, "eticaret"),
        ("Cyber Monday", bf + timedelta(days=3), "eticaret"),
        ("12.12 indirimleri", date(yil, 12, 12), "eticaret"),
        ("Yılbaşı indirimleri", date(yil, 12, 20), "eticaret"),
    ]
    g += [(f"{ad} öncesi market indirimleri", d - timedelta(days=4), "market") for ad, d in BAYRAMLAR.get(yil, [])]
    return [{"ad": a, "tarih": d, "tur": t} for a, d, t in sorted(g, key=lambda x: x[1])]


def yaklasan_ozel_gunler(bugun: date, gun: int = 45) -> list[dict]:
    tum = ozel_gunler(bugun.year) + ozel_gunler(bugun.year + 1)
    return [o | {"kalan": (o["tarih"] - bugun).days} for o in tum if 0 <= (o["tarih"] - bugun).days <= gun]


def bu_hafta_market(bugun: date, bim_katalog: list[dict] | None = None) -> list[dict]:
    """Önümüzdeki 7 günün market indirim günleri (tarih sıralı)."""
    olaylar = []
    for m in config.ayarlar().get("market_gunleri", []):
        d = bugun + timedelta(days=(m["gun"] - bugun.weekday()) % 7)
        olaylar.append({"market": m["market"], "tarih": d, "baslik": m["baslik"]})
    for k in bim_katalog or []:
        t = k["baslangic"]
        t = date.fromisoformat(t) if isinstance(t, str) else t
        if bugun <= t <= bugun + timedelta(days=7):
            olaylar.append({"market": "bim", "tarih": t, "baslik": f"BİM aktüel: {k['etiket']}"})
    if not bim_katalog:  # BİM sitesi okunamazsa bilinen günler
        for g in (1, 4):
            olaylar.append({"market": "bim", "tarih": bugun + timedelta(days=(g - bugun.weekday()) % 7),
                            "baslik": "BİM aktüel ürünler"})
    return sorted(olaylar, key=lambda o: o["tarih"])
