@echo off
setlocal EnableExtensions
chcp 65001 >nul
echo.
echo ===============================================
echo ODEV TAKIP V25.5 - WINDOWS GUVENLIK ON KONTROL
echo ===============================================
echo Python, Selenium, Node.js veya WhatsApp gerekmez.
echo Sadece Windows ve yerlesik PowerShell kullanilir.
echo Gercek veli/ogrenci verileri okunmaz.
echo.
if not exist "%~dp0windows_security_offline_v255.ps1" (
  echo Test dosyasi eksik. Hicbir islem yapilmadi.
  pause
  exit /b 2
)
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo Windows PowerShell bulunamadi. Arka plan WhatsApp KAPALI.
  pause
  exit /b 2
)
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0windows_security_offline_v255.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo TEST BASARILI DEGIL. WhatsApp arka plan motoru KAPALI.
) else (
  echo Yalnizca sahte veri DPAPI testi gecti; WhatsApp arka plan motoru HALA KAPALI.
)
echo.
echo Raporlar: %%LOCALAPPDATA%%\OdevTakip\Guvenlik_Raporlari_V255
pause
exit /b %RESULT%
