@echo off
chcp 65001 > nul
title YKS-LGS Odev Takip v2

cd /d "%~dp0"

REM 1. Derlenmis OdevTakip_v2.exe varsa direkt oradan calistir
if exist "%~dp0OdevTakip_v2.exe" (
    start "" "%~dp0OdevTakip_v2.exe"
    exit /b 0
)

REM 2. Sanal ortam (.venv) varsa oradan calistir
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [HATA] Uygulama bir hata ile kapandi (Kod: %ERRORLEVEL%).
        pause
    )
    exit /b %ERRORLEVEL%
)

REM 3. Sanal ortam yoksa kurulum sihirbazini baslat
echo [BILGI] Ilk calistirma algilandi. Ortam hazirlaniyor...
call "%~dp0Windows_Kurulum_ve_Baslat.bat"
