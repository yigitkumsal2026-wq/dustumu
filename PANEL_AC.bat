@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerekli paketler kontrol ediliyor...
python -m pip install -q -r requirements.txt
python main.py panel
pause
