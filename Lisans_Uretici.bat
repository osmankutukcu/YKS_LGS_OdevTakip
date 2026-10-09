@echo off
chcp 65001 > nul
title YKS-LGS Lisans Anahtari Uretici
cd /d "%~dp0"

REM 1. Sanal ortam (.venv) varsa direkt oradan pencere modunda calistir
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" admin_keygen.py
    exit /b 0
)
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" admin_keygen.py
    exit /b 0
)

REM 2. Sistem Python kontrolu
py -3 -c "import PyQt6" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pyw -3 admin_keygen.py 2>nul || start "" py -3 admin_keygen.py
    exit /b 0
)

python -c "import PyQt6" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw admin_keygen.py 2>nul || start "" python admin_keygen.py
    exit /b 0
)

echo.
echo ======================================================================
echo  [BILGI] Python ortami henuz hazir degil.
echo  Lutfen once ana klasordeki "Baslat_Windows.bat" dosyasini bir kez calistirin.
echo ======================================================================
echo.
pause
