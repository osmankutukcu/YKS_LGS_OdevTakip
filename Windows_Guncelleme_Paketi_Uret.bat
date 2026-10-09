@echo off
chcp 65001 > nul
title YKS-LGS Odev Takip v2 - Guncelleme Paketi Uretici

echo ======================================================================
echo    YKS-LGS ODEV TAKIP v2 - GUNCELLEME PAKETI VE RELEASE YAYINLAYICI
echo ======================================================================
echo.

cd /d "%~dp0"

REM 1. Python Kontrolu
set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    goto run_publisher
)

py -3 -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py -3"
    goto run_publisher
)

python -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto run_publisher
)

echo [HATA] Python bulunamadi! Lutfen Python'un yuklu ve PATH'e ekli oldugundan emin olun.
pause
exit /b 1

:run_publisher
"%PY_CMD%" publish_release.py %*
echo.
pause
