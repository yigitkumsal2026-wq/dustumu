"""Doğru indirim motoru.

Kural: Bir indirimin gerçek olup olmadığını satıcının üstü çizili fiyatına göre değil,
bizim kaydettiğimiz SON 30 GÜNÜN EN DÜŞÜK fiyatına göre ölçeriz (Ticaret Bakanlığı'nın
indirimli satış yönetmeliğiyle aynı mantık). Böylece "önce zam, sonra indirim" yapan
sahte kampanyalar elenir.

Güven seviyeleri:
  dogrulandi : fiyat geçmişimizle teyit edildi (en değerli)
  beyan      : geçmiş yetersiz, satıcının indirimi inandırıcı eşikleri geçti
  editor     : elle eklenen fırsat (sen eklediğin için güvenilir sayılır)
  aktuel     : BİM aktüel gibi indirim değil "dönemsel ürün" (market carousel'inde kullanılır)
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import date, timedelta

import yaml

from . import config
from .sources import Urun

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ kayıt
def kaydet(c: sqlite3.Connection, urunler: list[Urun], bugun: date) -> None:
    g = bugun.isoformat()
    for u in urunler:
        c.execute("""
            INSERT INTO urunler(id,kaynak,tur,ad,marka,kategori,url,gorsel,ilk_gorulme,son_gorulme,gecerlilik,bitis)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET ad=excluded.ad, url=excluded.url,
                gorsel=COALESCE(excluded.gorsel, urunler.gorsel), son_gorulme=excluded.son_gorulme,
                gecerlilik=excluded.gecerlilik, bitis=excluded.bitis,
                marka=COALESCE(excluded.marka, urunler.marka), kategori=COALESCE(excluded.kategori, urunler.kategori)
        """, (u.id, u.kaynak, u.tur, u.ad, u.marka, u.kategori, u.url, u.gorsel, g, g, u.gecerlilik, u.bitis))
        c.execute("""
            INSERT INTO fiyatlar(urun_id,tarih,fiyat,liste_fiyat) VALUES(?,?,?,?)
            ON CONFLICT(urun_id,tarih) DO UPDATE SET fiyat=MIN(fiyat, excluded.fiyat),
                liste_fiyat=COALESCE(excluded.liste_fiyat, fiyatlar.liste_fiyat)
        """, (u.id, g, u.fiyat, u.liste_fiyat))


# ------------------------------------------------------------------ değerlendirme
def _kara_liste() -> tuple[set[str], list[str]]:
    kelimeler = [k.lower() for k in config.ayarlar().get("kara_liste_kelimeler", [])]
    idler: set[str] = set()
    if config.KARA_LISTE_DOSYA.exists():
        with open(config.KARA_LISTE_DOSYA, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        idler = set(d.get("urunler") or [])
        kelimeler += [k.lower() for k in d.get("kelimeler") or []]
    return idler, kelimeler


def degerlendir(gecmis: list[float], bugun_fiyat: float, liste: float | None,
                tur: str, manuel: bool = False) -> dict:
    """Bir ürünün bugünkü fiyatını değerlendirir.

    gecmis: bugünden önceki günlük fiyatlar (eskiden yeniye).
    Sonuç: {'karar': 'firsat'|'red', ...}
    """
    a = config.ayarlar()["dogrulama"]
    beyan = (liste - bugun_fiyat) / liste * 100 if liste and liste > bugun_fiyat else 0.0

    if manuel:
        if not liste:
            return {"karar": "red", "neden": "elle eklenende eski fiyat yok"}
        return {"karar": "firsat", "guven": "editor", "eski": liste, "indirim": beyan,
                "aciklama": "Editör seçimi"}

    if bugun_fiyat < a["min_fiyat"]:
        return {"karar": "red", "neden": "fiyat çok düşük"}

    # Süren kampanyanın günlerini (bugünkü fiyata eşit/altı ardışık son günler) ayır:
    # referans, kampanya BAŞLAMADAN ÖNCEKİ fiyatlardır.
    i = len(gecmis)
    while i > 0 and gecmis[i - 1] <= bugun_fiyat * 1.02:
        i -= 1
    gunler = gecmis[:i]
    esik = a["min_beyan_indirim_market" if tur == "market" else "min_beyan_indirim"]
    if not gunler and len(gecmis) >= a["min_gecmis_gun"]:
        # Bildiğimiz tüm günlerde fiyat zaten bu seviyedeydi: indirim iddiası geçersiz.
        if beyan >= esik:
            return {"karar": "red", "neden": "sahte", "beyan": beyan, "min30": min(gecmis)}
        return {"karar": "red", "neden": "fiyat değişmedi"}
    if len(gunler) >= a["min_gecmis_gun"]:
        min30 = min(gunler)
        gercek = (min30 - bugun_fiyat) / min30 * 100
        if gercek >= a["min_gercek_indirim"]:
            return {"karar": "firsat", "guven": "dogrulandi", "eski": min30, "indirim": gercek,
                    "aciklama": f"Son {a['referans_gun']} günün en düşük fiyatından da ucuz"}
        if beyan >= esik:
            # Satıcı büyük indirim diyor ama son 30 günde fiyat zaten buradaydı -> sahte
            return {"karar": "red", "neden": "sahte", "beyan": beyan, "gercek": gercek, "min30": min30}
        return {"karar": "red", "neden": "gerçek düşüş yetersiz"}

    # Geçmiş yetersiz: satıcı beyanına dikkatli güven.
    if not liste or beyan < esik:
        return {"karar": "red", "neden": "beyan indirim yetersiz"}
    eski, indirim, aciklama = liste, beyan, "Satıcı indirimi"
    if gunler and liste > max(gunler) * 1.15:
        # Liste fiyatı gördüğümüz en yüksek fiyattan çok yüksek: şişirilmiş. Gerçek eski fiyatı kullan.
        eski = max(gunler)
        indirim = (eski - bugun_fiyat) / eski * 100
        aciklama = "Şişirilmiş liste fiyatı düzeltildi"
        if indirim < esik:
            return {"karar": "red", "neden": "sahte", "beyan": beyan, "gercek": indirim, "min30": min(gunler)}
    if gunler and min(gunler) <= bugun_fiyat * 1.02:
        return {"karar": "red", "neden": "sahte", "beyan": beyan, "min30": min(gunler)}
    if indirim > a["max_inandirici_indirim_eticaret" if tur == "eticaret" else "max_inandirici_indirim"]:
        return {"karar": "red", "neden": "inandırıcı değil"}
    return {"karar": "firsat", "guven": "beyan", "eski": eski, "indirim": indirim, "aciklama": aciklama}


def _tr_kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def populerlik(ad: str, kategori: str | None = None) -> int:
    """Çok alınan ürün/marka artı, niş ürün eksi puan (config: populerlik)."""
    a = config.ayarlar().get("populerlik") or {}
    metin = _tr_kucuk(f" {ad} {kategori or ''} ")
    p = 0
    if any(_tr_kucuk(k) in metin for k in a.get("cok_alinan", [])):
        p += a.get("cok_alinan_puan", 30)
    if any(_tr_kucuk(k) in metin for k in a.get("bilinen_markalar", [])):
        p += a.get("marka_puan", 15)
    if any(_tr_kucuk(k) in metin for k in a.get("nis", [])):
        p -= a.get("nis_ceza", 40)
    return p


def puanla(indirim: float, tasarruf: float, guven: str, tur: str, ad: str = "", kategori: str | None = None) -> float:
    p = indirim + 12 * math.log10(max(tasarruf, 1))
    p += {"dogrulandi": 25, "editor": 30, "beyan": 0, "aktuel": 0}.get(guven, 0)
    if tur == "eticaret":
        p += 5  # e-ticaret fırsatları daha çok kaydediliyor/paylaşılıyor
    p += populerlik(ad, kategori)
    return round(p, 2)


def firsatlari_guncelle(c: sqlite3.Connection, bugun: date) -> dict:
    a = config.ayarlar()["dogrulama"]
    g = bugun.isoformat()
    bas = (bugun - timedelta(days=a["referans_gun"])).isoformat()
    kara_id, kara_kelime = _kara_liste()
    istatistik = {"incelenen": 0, "firsat": 0, "sahte": 0, "aktuel": 0}
    sahteler = []

    satirlar = c.execute("""
        SELECT u.*, f.fiyat, f.liste_fiyat FROM urunler u
        JOIN fiyatlar f ON f.urun_id=u.id AND f.tarih=? WHERE u.son_gorulme=?
    """, (g, g)).fetchall()
    aktif_kalanlar = set()
    for u in satirlar:
        istatistik["incelenen"] += 1
        ad_k = u["ad"].lower()
        if u["id"] in kara_id or any(k and k in ad_k for k in kara_kelime):
            continue
        if u["bitis"] and u["bitis"] < g:
            continue
        gecmis = [r["fiyat"] for r in c.execute(
            "SELECT fiyat FROM fiyatlar WHERE urun_id=? AND tarih>=? AND tarih<? ORDER BY tarih",
            (u["id"], bas, g))]
        if u["kaynak"] == "bim":
            sonuc = {"karar": "firsat", "guven": "aktuel", "eski": u["fiyat"], "indirim": 0.0,
                     "aciklama": f"BİM Aktüel • {u['gecerlilik']}"}
            istatistik["aktuel"] += 1
        else:
            manuel = u["kaynak"] not in ("n11", "migros", "migroskop", "sok", "rossmann", "gratis", "bim_indirim")
            sonuc = degerlendir(gecmis, u["fiyat"], u["liste_fiyat"], u["tur"], manuel)
        if sonuc["karar"] != "firsat":
            if sonuc.get("neden") == "sahte":
                istatistik["sahte"] += 1
                sahteler.append({"ad": u["ad"], "kaynak": u["kaynak"], "fiyat": u["fiyat"],
                                 "liste": u["liste_fiyat"], "beyan": round(sonuc.get("beyan", 0)),
                                 "min30": sonuc.get("min30"), "url": u["url"]})
            continue
        tasarruf = sonuc["eski"] - u["fiyat"]
        if sonuc["guven"] != "aktuel" and tasarruf < a["min_tasarruf_tl"]:
            continue
        if not u["gorsel"]:
            continue
        puan = puanla(sonuc["indirim"], tasarruf, sonuc["guven"], u["tur"], u["ad"], u["kategori"])
        mevcut = c.execute("SELECT kod FROM firsatlar WHERE urun_id=? AND aktif=1", (u["id"],)).fetchone()
        if mevcut:
            c.execute("""UPDATE firsatlar SET guncelleme=?, fiyat=?, eski_fiyat=?, indirim=?, guven=?,
                         ref_aciklama=?, puan=? WHERE kod=?""",
                      (g, u["fiyat"], sonuc["eski"], round(sonuc["indirim"]), sonuc["guven"],
                       sonuc["aciklama"], puan, mevcut["kod"]))
        else:
            c.execute("""INSERT INTO firsatlar(urun_id,olusma,guncelleme,fiyat,eski_fiyat,indirim,guven,ref_aciklama,puan)
                         VALUES(?,?,?,?,?,?,?,?,?)""",
                      (u["id"], g, g, u["fiyat"], sonuc["eski"], round(sonuc["indirim"]),
                       sonuc["guven"], sonuc["aciklama"], puan))
        aktif_kalanlar.add(u["id"])
        istatistik["firsat"] += sonuc["guven"] != "aktuel"

    # Bugün görülmeyen ya da artık fırsat olmayanları kapat.
    for r in c.execute("SELECT kod, urun_id FROM firsatlar WHERE aktif=1").fetchall():
        if r["urun_id"] not in aktif_kalanlar:
            c.execute("UPDATE firsatlar SET aktif=0 WHERE kod=?", (r["kod"],))

    from .db import kv_yaz
    kv_yaz(c, "son_sahteler", sorted(sahteler, key=lambda s: -s["beyan"])[:50])
    kv_yaz(c, "son_istatistik", {**istatistik, "tarih": g})
    log.info("Değerlendirme: %s", istatistik)
    return istatistik


def eski_kayitlari_temizle(c: sqlite3.Connection, bugun: date, gun: int = 120) -> None:
    sinir = (bugun - timedelta(days=gun)).isoformat()
    c.execute("DELETE FROM fiyatlar WHERE tarih<?", (sinir,))
    c.execute("DELETE FROM urunler WHERE son_gorulme<?", (sinir,))
