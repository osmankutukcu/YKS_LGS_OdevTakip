@echo off
setlocal
cd /d "%~dp0.."
py -3 tools\windows_security_center_v253.py --selfcheck
if errorlevel 1 (
    echo.
    echo Guvenlik testi tamamlanamadi. WhatsApp arka plan motoru KAPALI kalmalidir.
) else (
    echo.
    echo Yalnizca yerel Windows sentetik guvenlik testi tamamlandi.
    echo WhatsApp arka plan motoru hala KAPALIDIR.
)
echo.
pause
