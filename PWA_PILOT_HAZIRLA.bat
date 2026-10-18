@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
echo V12 PWA PILOT - Ana veritabaninin KOPYASINI olusturur, orijinale yazmaz.
echo Bilgisayarinizdaki guncel SQLite .db dosyasinin TAM yolunu girin.
set /p "ORIGINAL_DB=SQLite dosyasi: "
if "%ORIGINAL_DB%"=="" (
  echo [HATA] Dosya yolu gerekli.
  pause
  exit /b 1
)
"%PYTHON%" tools\pwa_v12_pilot.py backup --source "%ORIGINAL_DB%"
if errorlevel 1 echo Kurulum gerceklesmedi. Ekrandaki hatayi kontrol edin.
pause
