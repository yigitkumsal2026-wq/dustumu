"""Reels videosu: kapak + ürün kareleri + takip çağrısı, kesmeli 1080x1920 MP4 (H.264/AAC, sessiz ses izi)."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from . import render

KAPAK_SN, URUN_SN, SON_SN = 1.8, 2.2, 2.0


def _birlestir(kareler: list[tuple[Path, float]], hedef: Path) -> None:
    girdiler: list[str] = []
    for yol, sure in kareler:
        girdiler += ["-loop", "1", "-framerate", "30", "-t", str(sure), "-i", str(yol)]
    n = len(kareler)
    zincir = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p[v]"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *girdiler,
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex", zincir,
                    "-map", "[v]", "-map", f"{n}:a", "-shortest", "-r", "30", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "23", "-profile:v", "high", "-g", "60", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(hedef)], check=True, capture_output=True, timeout=240)


def uret(firsatlar: list[dict], kapak_tarih: str, kapak_satirlari: tuple[str, str, str], renk: int,
         hedef: Path, reklam_degil: bool = True) -> Path:
    with tempfile.TemporaryDirectory() as gecici:
        k = Path(gecici)
        kareler = [(render.carousel_kapak(firsatlar, kapak_tarih, k / "kapak.jpg", renk, kapak_satirlari, reel=True), KAPAK_SN)]
        for i, f in enumerate(firsatlar):
            kareler.append((render.firsat_gorseli(f, k / f"u{i}.jpg", reel=True, reklam_degil=reklam_degil), URUN_SN))
        kareler.append((render.reel_son_kare(k / "son.jpg", renk, reklam_degil), SON_SN))
        hedef.parent.mkdir(parents=True, exist_ok=True)
        _birlestir(kareler, hedef)
    return hedef
