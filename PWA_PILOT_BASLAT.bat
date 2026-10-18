@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
"%PYTHON%" tools\pwa_v12_pilot.py preflight
if errorlevel 1 (
 echo PWA on denetimi basarisiz.
 pause
 exit /b 1
)
echo.
echo Mobil web sunucusu sadece BU bilgisayardaki localhost adresinde acilacak.
echo Telefona erisim icin AYRICA guvenli HTTPS / Tailscale Serve gerekir.
"%PYTHON%" tools\pwa_v12_pilot.py serve
if errorlevel 1 pause
