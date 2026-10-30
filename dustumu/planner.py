"""Ne zaman, ne paylaşılacağına karar verir.

Hesabın bot gibi görünmemesi için:
  * Yeni hesapta düşük başlayıp kademeli artan günlük limit (ısınma)
  * İki gönderi arasında en az X dakika + rastgele sapma (hep aynı dakikada paylaşmaz)
  * Sadece gündüz saatlerinde; etkileşimin yüksek olduğu "altın saatlere" öncelik
  * Aynı ürünü N gün içinde tekrar paylaşmaz, içerik türlerini karıştırır
"""
from __future__ import annotations

import json
import logging
import random
import re
import sqlite3
from datetime import date, datetime, timedelta

from . import captions, config, reel, render
from .calendar_tr import bu_hafta_market, tr_tarih, yaklasan_ozel_gunler
from .db import kv_al, kv_yaz
from .sources import KAYNAK_ADLARI

log = logging.getLogger(__name__)
FEED_TURLERI = ("tekli", "carousel", "takvim", "reel")
MARKA_TIP_SINIRI = 2  # Bir gönderide aynı markadan/aynı tipten en fazla bu kadar ürün
URUN_TIPLERI = {
    "deterjan": ("deterjan",), "deodorant": ("deodorant", "roll on", "roll-on"), "şampuan": ("şampuan",),
    "diş macunu": ("diş macun",), "yumuşatıcı": ("yumuşatıcı",), "çikolata": ("çikolata",), "kahve": ("kahve",),
    "bisküvi": ("bisküvi",), "peynir": ("peynir",), "yoğurt": ("yoğurt",), "sucuk": ("sucuk",), "parfüm": ("parfüm",),
}


def gunluk_limit(bugun: date) -> int:
    y = config.ayarlar()["yayin"]
    yas = (bugun - date.fromisoformat(str(y["hesap_acilis"]))).days
    limit = 1
    for adim in sorted(y["isinma_plani"], key=lambda a: a["gun"]):
        if yas >= adim["gun"]:
            limit = adim["gonderi"]
    return min(limit, y["gunluk_max_gonderi"])


def _bugun_sayisi(c, gun: str, turler) -> int:
    soru = ",".join("?" * len(turler))
    return c.execute(f"""SELECT COUNT(*) FROM gonderiler WHERE substr(planlanan,1,10)=? AND tur IN ({soru})
                         AND durum IN ('planlandi','yayinlandi','deneme')""", (gun, *turler)).fetchone()[0]


def _altin_saat(s: datetime) -> bool:
    return any(a <= s.hour < b for a, b in config.ayarlar()["yayin"]["altin_saatler"])


def zaman_uygun_mu(c: sqlite3.Connection, s: datetime, zorla: bool = False) -> tuple[bool, str]:
    y = config.ayarlar()["yayin"]
    if zorla:
        return True, "zorla"
    if not (y["aktif_saatler"]["baslangic"] <= s.hour < y["aktif_saatler"]["bitis"]):
        return False, "aktif saat dışında"
    limit = gunluk_limit(s.date())
    yapilan = _bugun_sayisi(c, s.date().isoformat(), FEED_TURLERI)
    if yapilan >= limit:
        return False, f"günlük limit doldu ({yapilan}/{limit})"
    sonraki = kv_al(c, "sonraki_uygun")
    if sonraki and s < datetime.fromisoformat(sonraki):
        return False, f"bekleme süresi ({sonraki[11:16]}'e kadar)"
    if not _altin_saat(s):
        # Altın saat dışında da paylaşır ama seyrek: kalan hak çoksa daha olası.
        kalan_saat = max(y["aktif_saatler"]["bitis"] - s.hour, 1)
        olasilik = min(0.9, 0.25 + (limit - yapilan) / kalan_saat)
        if random.random() > olasilik:
            return False, "altın saat dışı, bu tur atlandı"
    return True, "uygun"


def _son_paylasilan_urunler(c, gun: int) -> set[str]:
    sinir = (config.simdi() - timedelta(days=gun)).isoformat()
    ids: set[str] = set()
    for r in c.execute("SELECT urunler FROM gonderiler WHERE planlanan>=? AND durum IN ('planlandi','yayinlandi','deneme')",
                       (sinir,)):
        ids.update(json.loads(r["urunler"]))
    return ids


def _urun_adlari(c, ids: set[str]) -> list[str]:
    return [r["ad"] for r in c.execute("SELECT id, ad FROM urunler") if r["id"] in ids]


def aktif_firsatlar(c: sqlite3.Connection, tur: str | None = None, haric: set[str] | None = None) -> list[dict]:
    q = """SELECT f.*, u.ad, u.kaynak, u.tur, u.gorsel, u.url, u.gecerlilik, u.bitis, u.kategori
           FROM firsatlar f JOIN urunler u ON u.id=f.urun_id WHERE f.aktif=1"""
    sonuc = [dict(r) for r in c.execute(q + " ORDER BY f.puan DESC")]
    if tur:
        sonuc = [f for f in sonuc if f["tur"] == tur]
    if haric:
        # Aynı ürün başka firmada ya da yeni katalogda başka kodla gelebilir: ada da bakılır.
        adlar = {_sade(a) for a in _urun_adlari(c, haric)}
        sonuc = [f for f in sonuc if f["urun_id"] not in haric and _sade(f["ad"]) not in adlar]
    return sonuc


def _kayit(c, tur, firsatlar, gorseller, aciklama, s) -> int:
    cur = c.execute("""INSERT INTO gonderiler(tur,kodlar,urunler,gorseller,aciklama,durum,planlanan)
                       VALUES(?,?,?,?,?,'planlandi',?)""",
                    (tur, json.dumps([f["kod"] for f in firsatlar]), json.dumps([f["urun_id"] for f in firsatlar]),
                     json.dumps(gorseller), aciklama, s.isoformat(timespec="seconds")))
    return cur.lastrowid


def _dosya(ad: str):
    return config.GORSEL / ad


def _sade(ad: str) -> str:
    return " ".join(ad.replace("İ", "i").replace("I", "ı").lower().split())


def _urun_ailesi(ad: str) -> str:
    """'Signal White Now 3In1 Shine 75 Ml' ile '... Original 75 Ml' aynı aile: ilk iki kelime."""
    return " ".join(_sade(ad).split()[:2])


def _marka(ad: str) -> str:
    return (_sade(ad).split() or [""])[0]


def _urun_tipi(ad: str) -> str | None:
    """Farklı markalardan da olsa aynı şey sayılanlar: 'Omo ... Deterjan' ile 'Persil ... Deterjanı'."""
    sade = _sade(ad)
    return next((tip for tip, kelimeler in URUN_TIPLERI.items()
                 if any(re.search(r"\b" + k, sade) for k in kelimeler)), None)


def _tazelik(ad: str, son_adlar: list[str]) -> tuple[bool, bool, bool]:
    """Sıralama anahtarı: yakında paylaşılmış aile, marka ve ürün tipi geriye düşer (False önce gelir)."""
    tip = _urun_tipi(ad)
    return (_urun_ailesi(ad) in {_urun_ailesi(a) for a in son_adlar},
            _marka(ad) in {_marka(a) for a in son_adlar},
            tip is not None and tip in {_urun_tipi(a) for a in son_adlar})


def _cesitli_sec(adaylar: list[dict], n: int, haric: list[dict] | None = None,
                 kaynak_siniri: int | None = None, aile_kontrol: bool = True) -> list[dict]:
    """Aynı mağazadan/aynı ürünün renk-koku çeşitlerinden/aynı marka ya da tipten yığılmasın; en iyi n ürünü seç.
    Elle seçilen linklerde aile_kontrol=False (her ürünü sen seçtin)."""
    secilen, kaynak_sayisi = [], {}
    aileler = {_urun_ailesi(f["ad"]) for f in haric or []}
    marka_sayisi, tip_sayisi = {}, {}
    sinir = kaynak_siniri or max(2, n // 2)
    for f in adaylar:
        aile, marka, tip = _urun_ailesi(f["ad"]), _marka(f["ad"]), _urun_tipi(f["ad"])
        if aile_kontrol and (aile in aileler or marka_sayisi.get(marka, 0) >= MARKA_TIP_SINIRI
                             or (tip and tip_sayisi.get(tip, 0) >= MARKA_TIP_SINIRI)):
            continue
        if kaynak_sayisi.get(f["kaynak"], 0) < sinir:
            secilen.append(f)
            aileler.add(aile)
            marka_sayisi[marka] = marka_sayisi.get(marka, 0) + 1
            tip_sayisi[tip] = tip_sayisi.get(tip, 0) + 1
            kaynak_sayisi[f["kaynak"]] = kaynak_sayisi.get(f["kaynak"], 0) + 1
        if len(secilen) == n:
            break
    return secilen


def _yer_eki(ad: str) -> str:
    """'BİM' -> "BİM'de", 'Migros' -> "Migros'ta", 'Gratis' -> "Gratis'te", 'n11' -> "n11'de"."""
    kucuk = ad.replace("I", "ı").replace("İ", "i").lower()
    unlu = next((h for h in reversed(kucuk) if h in "aıoueiöü"), "e")
    # Sayıyla bitenler "bir" okunur (n11, A101).
    if kucuk[-1].isdigit():
        unlu = "e"
    a = "a" if unlu in "aıou" else "e"
    return f"{ad}'{'t' if kucuk[-1] in 'fstkçşhp' else 'd'}{a}"


def _firma_son_tarihleri(c) -> dict[str, str]:
    """Her firmanın en son ne zaman gönderisi çıktığı."""
    son: dict[str, str] = {}
    for r in c.execute("""SELECT urunler, planlanan FROM gonderiler WHERE durum IN ('planlandi','yayinlandi','deneme')
                          ORDER BY planlanan"""):
        for u in json.loads(r["urunler"]):
            son[u.split(":")[0]] = r["planlanan"]
    return son


def _firma_sec(gruplar: dict[str, list[dict]], son: str | None, son_tarihler: dict[str, str] | None = None,
               acil_tarih: str = "") -> str | None:
    """En az 3 adayı olan firmalardan bir önceki gönderininki hariç seçer: süresi bitmek üzere olan önce,
    sonra en uzun süredir paylaşılmayan, eşitlikte bitişi en yakın olan."""
    uygun = {k: v for k, v in gruplar.items() if len(v) >= 3}
    adaylar = [k for k in uygun if k != son] or list(uygun)
    if not adaylar:
        return None

    def anahtar(k):
        bitis = min(f.get("bitis") or "9" for f in uygun[k])
        return (bitis > acil_tarih, (son_tarihler or {}).get(k, ""), bitis, -uygun[k][0]["puan"])
    return min(adaylar, key=anahtar)


def planla(c: sqlite3.Connection, zorla: bool = False, bim_katalog: list[dict] | None = None) -> list[int]:
    """Bu çalıştırmada paylaşılacak gönderileri oluşturur (görselleriyle). Gönderi id'lerini döner."""
    y = config.ayarlar()["yayin"]
    s = config.simdi()
    uygun, neden = zaman_uygun_mu(c, s, zorla)
    if not uygun:
        log.info("Bu turda paylaşım yok: %s", neden)
        return []

    gun = s.date().isoformat()
    damga = s.strftime("%Y%m%d%H%M")
    yasak = _son_paylasilan_urunler(c, y["tekrar_engel_gun"])
    yeni: list[int] = []

    # 1) Pazartesi: haftalık indirim takvimi
    hafta = s.date().isocalendar()
    if (y["haftalik_takvim_gonderisi"] and s.weekday() == 0
            and kv_al(c, "son_takvim_haftasi") != f"{hafta[0]}-{hafta[1]}"):
        market = bu_hafta_market(s.date(), bim_katalog)
        ozel = yaklasan_ozel_gunler(s.date(), 30)
        ad = f"takvim_{damga}.jpg"
        render.takvim_gorseli(market, ozel, _dosya(ad))
        yeni.append(_kayit(c, "takvim", [], [ad], captions.takvim(market, ozel), s))
        kv_yaz(c, "son_takvim_haftasi", f"{hafta[0]}-{hafta[1]}")
    else:
        market = aktif_firsatlar(c, "market", yasak)
        indirimli_market = [f for f in market if f["guven"] != "aktuel"]
        aktuel = [f for f in market if f["guven"] == "aktuel"
                  and (f.get("bitis") or "9") >= gun]
        eticaret = aktif_firsatlar(c, "eticaret", yasak)
        if y.get("eticaret_sadece_dogrulanmis", True):
            eticaret = [f for f in eticaret if f["guven"] in ("dogrulandi", "editor")]
        n = y["carousel_urun_sayisi"]
        # Yakında paylaşılan aile/marka/tip geriye düşer; puan sırası her grubun içinde korunur.
        son_adlar = _urun_adlari(c, _son_paylasilan_urunler(c, y["cesit_gun"]))
        tazelik = lambda f: _tazelik(f["ad"], son_adlar)
        eticaret = sorted(eticaret, key=tazelik)
        indirimli_market = sorted(indirimli_market, key=tazelik)
        aktuel = sorted(aktuel, key=lambda f: (tazelik(f), f.get("bitis") or ""))

        # 2) Çok fırsatlı carousel: her gönderi tek firmadan. Yeterli aday yoksa tekli.
        gruplar: dict[str, list[dict]] = {}
        for f in eticaret + indirimli_market + aktuel:
            gruplar.setdefault(f["kaynak"], []).append(f)
        # Elle seçilen ürünlerde çeşit elemesi yok.
        secimler = {k: _cesitli_sec(v, n, kaynak_siniri=n, aile_kontrol=v[0]["guven"] != "editor")
                    for k, v in gruplar.items()}
        firma = _firma_sec(secimler, kv_al(c, "son_firma"), _firma_son_tarihleri(c),
                           (s.date() + timedelta(days=1)).isoformat())
        secim = secimler.get(firma, [])
        if firma == "migroskop":
            kapak_satirlari = ("MİGROSKOP'TA", "MONEY'Lİ", "FIRSATLAR")
            baslik = f"Migroskop'ta Money'li fırsatlar ({secim[0]['gecerlilik']})"
        elif firma:
            yer_ek = _yer_eki(KAYNAK_ADLARI.get(firma, firma))
            kapak_satirlari = ("BUGÜN", yer_ek.replace("i", "İ").upper(), "NE DÜŞTÜ?")
            baslik = f"Bugün {yer_ek} ne düştü?"
        if y["market_carousel"] and len(secim) >= 3:
            kv_yaz(c, "son_firma", firma)
            aff = _affiliate_mi(secim)
            gorseller = [f"car_{damga}_0.jpg"]
            renk = int(kv_al(c, "kapak_renk", "0")) + 1  # her kapak bir sonraki renkte (0=sarı, ilk kapakta kullanıldı)
            kv_yaz(c, "kapak_renk", str(renk))
            reel_id = None
            if y["reel_paylas"] and y["instagram_aktif"] and kv_al(c, "son_format") != "reel":
                reel_secim = secim[:y["reel_urun_sayisi"]]
                ad = f"reel_{damga}.mp4"
                try:
                    reel.uret(reel_secim, f"{tr_tarih(s.date())} · {len(reel_secim)} fırsat", kapak_satirlari, renk,
                              _dosya(ad), reklam_degil=not aff)
                    aciklama = captions.carousel(reel_secim, f"{tr_tarih(s.date())} — {baslik}", aff,
                                                 "🔔 Takip et, düşen fiyatları kaçırma 👇")
                    reel_id = _kayit(c, "reel", reel_secim, [ad], aciklama, s)
                    secim = reel_secim
                except Exception as e:  # video üretilemezse o tur carousel paylaşılır
                    log.warning("Reel üretilemedi, carousel paylaşılacak: %s", e)
            if reel_id:
                yeni.append(reel_id)
                kv_yaz(c, "son_format", "reel")
            else:
                render.carousel_kapak(secim, f"{tr_tarih(s.date())} · {len(secim)} fırsat", _dosya(gorseller[0]), renk,
                                      kapak_satirlari)
                for i, f in enumerate(secim, 1):
                    ad = f"car_{damga}_{i}_{f['kod']}.jpg"
                    render.firsat_gorseli(f, _dosya(ad), reklam_degil=not aff)
                    gorseller.append(ad)
                aciklama = captions.carousel(secim, f"{tr_tarih(s.date())} — {baslik}", aff)
                yeni.append(_kayit(c, "carousel", secim, gorseller, aciklama, s))
                kv_yaz(c, "son_format", "carousel")
            if y["hikaye_paylas"] and _bugun_sayisi(c, gun, ("hikaye",)) < y["gunluk_max_hikaye"]:
                had = f"hik_{damga}_{secim[0]['kod']}.jpg"
                render.firsat_gorseli(secim[0], _dosya(had), hikaye=True, reklam_degil=not aff)
                yeni.append(_kayit(c, "hikaye", [secim[0]], [had], "", s))
        else:
            # 3) Tekli fırsat: e-ticaret ve market dönüşümlü, en yüksek puanlı
            son_tur = kv_al(c, "son_tekli_tur", "market")
            sira = [eticaret, indirimli_market] if son_tur == "market" else [indirimli_market, eticaret]
            aday = next((l[0] for l in sira if l), None)
            if not aday:
                log.info("Paylaşılacak uygun fırsat yok.")
                return []
            kv_yaz(c, "son_tekli_tur", aday["tur"])
            ad = f"tek_{damga}_{aday['kod']}.jpg"
            render.firsat_gorseli(aday, _dosya(ad), reklam_degil=not _affiliate_mi([aday]))
            yeni.append(_kayit(c, "tekli", [aday], [ad], captions.tekli(aday, _affiliate_mi([aday])), s))
            if y["hikaye_paylas"] and _bugun_sayisi(c, gun, ("hikaye",)) < y["gunluk_max_hikaye"]:
                had = f"hik_{damga}_{aday['kod']}.jpg"
                render.firsat_gorseli(aday, _dosya(had), hikaye=True, reklam_degil=not _affiliate_mi([aday]))
                yeni.append(_kayit(c, "hikaye", [aday], [had], "", s))

    bekle = y["min_aralik_dk"] + random.randint(-y["rastgele_sapma_dk"], y["rastgele_sapma_dk"])
    kv_yaz(c, "sonraki_uygun", (s + timedelta(minutes=bekle)).isoformat(timespec="seconds"))
    log.info("%d gönderi planlandı, sonraki en erken: +%d dk", len(yeni), bekle)
    return yeni


def tekli_hazirla(c: sqlite3.Connection, kod: int, hikaye: bool = True) -> list[int]:
    """Panelden seçilen fırsat için, zamanlamaya bakmadan gönderi hazırlar."""
    f = next((x for x in aktif_firsatlar(c) if x["kod"] == kod), None)
    if not f:
        return []
    s = config.simdi()
    damga = s.strftime("%Y%m%d%H%M%S")
    ad = f"tek_{damga}_{kod}.jpg"
    render.firsat_gorseli(f, _dosya(ad), reklam_degil=not _affiliate_mi([f]))
    ids = [_kayit(c, "tekli", [f], [ad], captions.tekli(f, _affiliate_mi([f])), s)]
    if hikaye and config.ayarlar()["yayin"]["hikaye_paylas"]:
        had = f"hik_{damga}_{kod}.jpg"
        render.firsat_gorseli(f, _dosya(had), hikaye=True, reklam_degil=not _affiliate_mi([f]))
        ids.append(_kayit(c, "hikaye", [f], [had], "", s))
    return ids


def _affiliate_mi(firsatlar: list[dict]) -> bool:
    a = config.ayarlar()["affiliate"]
    if any(a.get(f["kaynak"]) for f in firsatlar):
        return True
    from .sources import manuel
    aff = {k["url"] for k in manuel.oku() if k.get("affiliate")}
    return any(f.get("url") in aff for f in firsatlar)
