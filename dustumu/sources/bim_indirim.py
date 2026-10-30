"""BİM indirim afişi: eski ve yeni fiyat yalnızca afiş görselinde yazar, data/bim_indirim.yaml'a elle işlenir."""
from __future__ import annotations

import yaml

from .. import config
from . import Urun

DOSYA = config.MANUEL_DOSYA.parent / "bim_indirim.yaml"


def topla(ayar: dict) -> list[Urun]:
    if not DOSYA.exists():
        return []
    with open(DOSYA, encoding="utf-8") as f:
        v = yaml.safe_load(f) or {}
    return [Urun(kaynak="bim_indirim", kod=k["kod"], ad=k["ad"], url=v["afis"], fiyat=float(k["fiyat"]),
                 liste_fiyat=float(k["eski_fiyat"]), gorsel=k.get("gorsel"), tur="market",
                 gecerlilik=v["donem"], bitis=str(v["bitis"]))
            for k in v.get("urunler") or []]
