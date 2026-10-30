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
import sqlite3
from datetime import date, datetime, timedelta

from . import captions, config, render
from .calendar_tr import bu_hafta_market, tr_tarih, yaklasan_ozel_gunler
from .db import kv_al, kv_yaz
from .sources import KAYNAK_ADLARI

log = logging.getLogger(__name__)
FEED_TURLERI = ("tekli", "carousel", "takvim")


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


def aktif_firsatlar(c: sqlite3.Connection, tur: str | None = None, haric: set[str] | None = None) -> list[dict]:
    q = """SELECT f.*, u.ad, u.kaynak, u.tur, u.gorsel, u.url, u.gecerlilik, u.bitis, u.kategori
           FROM firsatlar f JOIN urunler u ON u.id=f.urun_id WHERE f.aktif=1"""
    sonuc = [dict(r) for r in c.execute(q + " ORDER BY f.puan DESC")]
    if tur:
        sonuc = [f for f in sonuc if f["tur"] == tur]
    if haric:
        sonuc = [f for f in sonuc if f["urun_id"] not in haric]
    return sonuc


def _kayit(c, tur, firsatlar, gorseller, aciklama, s) -> int:
    cur = c.execute("""INSERT INTO gonderiler(tur,kodlar,urunler,gorseller,aciklama,durum,planlanan)
                       VALUES(?,?,?,?,?,'planlandi',?)""",
                    (tur, json.dumps([f["kod"] for f in firsatlar]), json.dumps([f["urun_id"] for f in firsatlar]),
                     json.dumps(gorseller), aciklama, s.isoformat(timespec="seconds")))
    return cur.lastrowid


def _dosya(ad: str):
    return config.GORSEL / ad


def _urun_ailesi(ad: str) -> str:
    """'Signal White Now 3In1 Shine 75 Ml' ile '... Original 75 Ml' aynı aile: ilk iki kelime."""
    return " ".join(ad.lower().split()[:2])


def _cesitli_sec(adaylar: list[dict], n: int, haric: list[dict] | None = None,
                 kaynak_siniri: int | None = None, aile_kontrol: bool = True) -> list[dict]:
    """Aynı mağazadan/aynı ürünün renk-koku çeşitlerinden yığılmasın; en iyi n ürünü seç.
    Elle seçilen linklerde aile_kontrol=False (her ürünü sen seçtin)."""
    secilen, kaynak_sayisi = [], {}
    aileler = {_urun_ailesi(f["ad"]) for f in haric or []}
    sinir = kaynak_siniri or max(2, n // 2)
    for f in adaylar:
        aile = _urun_ailesi(f["ad"])
        if aile_kontrol and aile in aileler:
            continue
        if kaynak_sayisi.get(f["kaynak"], 0) < sinir:
            secilen.append(f)
            aileler.add(aile)
            kaynak_sayisi[f["kaynak"]] = kaynak_sayisi.get(f["kaynak"], 0) + 1
        if len(secilen) == n:
            break
    return secilen


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

        # 2) Çok fırsatlı carousel. Online (Trendyol linkleri vb.) en az 3 birikince kendi gönderisinde
        #    toplanır; yoksa market indirimleri + yaklaşan aktüeller. Yeterli aday yoksa tekli.
        online = sorted(eticaret, key=lambda f: -f["puan"])
        if len(online) >= 3:
            secim = _cesitli_sec(online, n, kaynak_siniri=n, aile_kontrol=False)
            magazalar = {f["kaynak"] for f in secim}
            if len(magazalar) == 1:
                yer = KAYNAK_ADLARI.get(next(iter(magazalar)), "İnternet")
                ek = "te" if yer.lower().endswith("s") else "de" if yer.lower().endswith(("11", "e", "i")) else "da"
                yer_ek = f"{yer}'{ek}"
            else:
                yer_ek = "İnternette"
            kapak_satirlari = ("BUGÜN", yer_ek.replace("i", "İ").upper(), "NE DÜŞTÜ?")
            baslik = f"Bugün {yer_ek} ne düştü?"
        elif sum(f["kaynak"] == "migroskop" for f in indirimli_market) >= 3:
            # Migroskop kataloğu bitene kadar kendi gönderisinde toplanır.
            katalog = sorted((f for f in indirimli_market if f["kaynak"] == "migroskop"), key=lambda f: -f["puan"])
            secim = _cesitli_sec(katalog, n, kaynak_siniri=n)
            kapak_satirlari = ("MİGROSKOP'TA", "MONEY'Lİ", "FIRSATLAR")
            baslik = f"Migroskop'ta Money'li fırsatlar ({secim[0]['gecerlilik']})"
        else:
            indirimli = sorted(indirimli_market, key=lambda f: -f["puan"])
            secim = _cesitli_sec(indirimli, n - 2)
            secim += _cesitli_sec(sorted(aktuel, key=lambda f: f.get("bitis") or ""), n - len(secim), secim)
            if len(secim) < n:
                secim += _cesitli_sec(indirimli, n - len(secim), secim)
            kapak_satirlari = ("BUGÜN", "MARKETTE", "NE DÜŞTÜ?")
            baslik = "Bugün ne düştü?"
        secim = secim[:n]
        if y["market_carousel"] and len(secim) >= 3:
            aff = _affiliate_mi(secim)
            gorseller = [f"car_{damga}_0.jpg"]
            renk = int(kv_al(c, "kapak_renk", "0")) + 1  # her kapak bir sonraki renkte (0=sarı, ilk kapakta kullanıldı)
            kv_yaz(c, "kapak_renk", str(renk))
            render.carousel_kapak(secim, f"{tr_tarih(s.date())} · {len(secim)} fırsat", _dosya(gorseller[0]), renk,
                                  kapak_satirlari)
            for i, f in enumerate(secim, 1):
                ad = f"car_{damga}_{i}_{f['kod']}.jpg"
                render.firsat_gorseli(f, _dosya(ad), reklam_degil=not aff)
                gorseller.append(ad)
            aciklama = captions.carousel(secim, f"{tr_tarih(s.date())} — {baslik}", aff)
            yeni.append(_kayit(c, "carousel", secim, gorseller, aciklama, s))
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
