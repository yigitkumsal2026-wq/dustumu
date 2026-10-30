"""Reels sesi: tamamen burada sentezlenir (telif yok). Enerjik ritim + geçişlerde efekt.
Her Reels'te tempo, ton ve akor dizisi değişir (no)."""
from __future__ import annotations

import array
import math
import random
import wave
from pathlib import Path

ORNEK = 44100
TEMPOLAR = (118, 124, 128, 112, 122, 132, 116)
TONLAR = (110.0, 123.47, 98.0, 130.81, 116.54)     # bas kök frekansları
DIZILER = ((0, 7, 9, 5), (0, 5, 7, 5), (9, 5, 0, 7), (0, 9, 5, 7))  # yarım ton: I-V-vi-IV ve benzerleri


def _kick() -> list[float]:
    n, faz, c = int(0.22 * ORNEK), 0.0, []
    for i in range(n):
        t = i / ORNEK
        faz += 2 * math.pi * (48 + 95 * math.exp(-t * 32)) / ORNEK
        c.append(math.sin(faz) * math.exp(-t * 13))
    return c


def _hat(rnd: random.Random) -> list[float]:
    n, onceki, c = int(0.06 * ORNEK), 0.0, []
    for i in range(n):
        x = rnd.uniform(-1, 1)
        c.append((x - onceki) * 0.5 * math.exp(-i / ORNEK * 70))
        onceki = x
    return c


def _nota(frekans: float, sure: float, parlaklik: float, sonum: float) -> list[float]:
    c = []
    for i in range(int(sure * ORNEK)):
        t = i / ORNEK
        w = 2 * math.pi * frekans * t
        c.append((math.sin(w) + parlaklik * math.sin(2 * w) / 2 + parlaklik * math.sin(3 * w) / 3)
                 * math.exp(-t * sonum) * min(t * 300, 1))
    return c


def _ufleme(rnd: random.Random, sure: float = 0.28) -> list[float]:
    """Geçiş sesi: açılan filtreli gürültü."""
    n, y, c = int(sure * ORNEK), 0.0, []
    for i in range(n):
        u = i / n
        y += (0.03 + 0.5 * u * u) * (rnd.uniform(-1, 1) - y)
        c.append(y * math.sin(math.pi * u) ** 1.5)
    return c


def _pop() -> list[float]:
    n, faz, c = int(0.09 * ORNEK), 0.0, []
    for i in range(n):
        t = i / ORNEK
        faz += 2 * math.pi * (420 + 1500 * t * 8) / ORNEK
        c.append(math.sin(faz) * math.exp(-t * 38))
    return c


def _ding() -> list[float]:
    c = []
    for i in range(int(0.5 * ORNEK)):
        t = i / ORNEK
        c.append((math.sin(2 * math.pi * 1318.5 * t) + 0.7 * math.sin(2 * math.pi * 1760 * t)
                  + 0.25 * math.sin(2 * math.pi * 2637 * t)) * math.exp(-t * 9) / 1.95)
    return c


def _ekle(iz: array.array, ses: list[float], t: float, kazanc: float) -> None:
    b = int(t * ORNEK)
    for i, x in enumerate(ses):
        j = b + i
        if j >= len(iz):
            break
        if j >= 0:
            iz[j] += x * kazanc


def uret(hedef: Path, sure: float, olaylar: list[tuple[str, float]], no: int = 0) -> Path:
    """olaylar: (ufleme|pop|ding, saniye). 16 bit mono WAV yazar."""
    rnd = random.Random(no)
    iz = array.array("f", [0.0]) * int(sure * ORNEK)
    vurus = 60 / TEMPOLAR[no % len(TEMPOLAR)]
    kok, dizi = TONLAR[no % len(TONLAR)], DIZILER[no % len(DIZILER)]
    kick, hat = _kick(), _hat(rnd)
    t, adim = 0.0, 0
    while t < sure:
        akor = dizi[(adim // 16) % 4]
        k = kok * 2 ** (akor / 12)
        if adim % 4 == 0:
            _ekle(iz, kick, t, 0.75)
        if adim % 4 == 2:
            _ekle(iz, hat, t, 0.32)
        if adim % 2 == 1:
            _ekle(iz, hat, t, 0.12)
        if adim % 4 in (0, 3):
            _ekle(iz, _nota(k / 2, vurus * 0.45, 0.6, 7), t, 0.38)
        if adim % 8 in (2, 6):  # kısa akor vuruşu
            for yari in (0, 4, 7):
                _ekle(iz, _nota(k * 2 * 2 ** (yari / 12), vurus * 0.5, 0.35, 11), t, 0.09)
        t += vurus / 4
        adim += 1
    efekt = {"ufleme": (_ufleme(rnd), 0.5), "pop": (_pop(), 0.42), "ding": (_ding(), 0.34)}
    for ad, an in olaylar:
        s, kazanc = efekt[ad]
        _ekle(iz, s, an, kazanc)
    # Yumuşak sınırlama, tepe -3 dB, sonda kısa kısılma.
    tepe = max(max(abs(x) for x in iz), 1e-6)
    kisma = int(0.35 * ORNEK)
    veri = array.array("h", [0]) * len(iz)
    for i, x in enumerate(iz):
        y = math.tanh(1.4 * x / tepe) / math.tanh(1.4) * 0.7
        if i > len(iz) - kisma:
            y *= (len(iz) - i) / kisma
        veri[i] = int(y * 32767)
    with wave.open(str(hedef), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(ORNEK)
        w.writeframes(veri.tobytes())
    return hedef
