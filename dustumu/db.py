"""SQLite veritabanı: ürünler, günlük fiyat geçmişi, fırsatlar, gönderiler."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from . import config

SEMA = """
CREATE TABLE IF NOT EXISTS urunler (
    id TEXT PRIMARY KEY,          -- kaynak:kod
    kaynak TEXT NOT NULL,
    tur TEXT NOT NULL,            -- market | eticaret
    ad TEXT NOT NULL,
    marka TEXT,
    kategori TEXT,
    url TEXT NOT NULL,
    gorsel TEXT,
    ilk_gorulme TEXT NOT NULL,
    son_gorulme TEXT NOT NULL,
    gecerlilik TEXT,              -- örn. BİM aktüel: "30 Ekim Cuma"
    bitis TEXT                    -- kampanyanın bittiği tarih (biliniyorsa)
);
CREATE TABLE IF NOT EXISTS fiyatlar (
    urun_id TEXT NOT NULL,
    tarih TEXT NOT NULL,          -- YYYY-MM-DD; günde bir satır (günün en düşüğü)
    fiyat REAL NOT NULL,
    liste_fiyat REAL,             -- satıcının üstü çizili fiyatı
    PRIMARY KEY (urun_id, tarih)
);
CREATE TABLE IF NOT EXISTS firsatlar (
    kod INTEGER PRIMARY KEY AUTOINCREMENT,   -- takipçinin göreceği fırsat kodu
    urun_id TEXT NOT NULL,
    olusma TEXT NOT NULL,
    guncelleme TEXT NOT NULL,
    fiyat REAL NOT NULL,
    eski_fiyat REAL NOT NULL,     -- görselde üstü çizili gösterilecek fiyat
    indirim INTEGER NOT NULL,     -- %
    guven TEXT NOT NULL,          -- dogrulandi | beyan | aktuel
    ref_aciklama TEXT,
    puan REAL NOT NULL,
    aktif INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_firsat_urun ON firsatlar(urun_id, aktif);
CREATE TABLE IF NOT EXISTS gonderiler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tur TEXT NOT NULL,            -- tekli | carousel | takvim | hikaye
    kodlar TEXT NOT NULL,         -- JSON fırsat kodları
    urunler TEXT NOT NULL DEFAULT '[]',  -- JSON ürün id'leri (tekrar engeli için)
    gorseller TEXT NOT NULL,      -- JSON dosya adları (site/g/ altında)
    aciklama TEXT NOT NULL,
    durum TEXT NOT NULL,          -- planlandi | yayinlandi | hata | iptal
    planlanan TEXT NOT NULL,
    yayin_zamani TEXT,
    ig_id TEXT,
    hata TEXT
);
CREATE TABLE IF NOT EXISTS yanitlanan_yorumlar (
    yorum_id TEXT PRIMARY KEY,
    zaman TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def baglan() -> sqlite3.Connection:
    config.klasorleri_hazirla()
    c = sqlite3.connect(config.DB_YOLU)
    c.row_factory = sqlite3.Row
    c.executescript(SEMA)
    return c


@contextmanager
def oturum():
    c = baglan()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def kv_al(c: sqlite3.Connection, k: str, varsayilan=None):
    r = c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else varsayilan


def kv_yaz(c: sqlite3.Connection, k: str, v) -> None:
    c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
              (k, json.dumps(v, ensure_ascii=False)))
