#!/usr/bin/env bash
# Veritabanı + üretilen siteyi "veri" dalına tek commit olarak kaydeder.
# Geçmiş tutulmaz (force push): depo boyutu büyümez.
set -euo pipefail
cd durum
rm -rf .git
git init -q -b veri
git add -A
git -c user.name="dustumu-bot" -c user.email="bot@users.noreply.github.com" commit -qm "durum $(date '+%F %R')"
git push -q -f "$DEPO_URL" veri
