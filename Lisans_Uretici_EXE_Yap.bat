@echo off
chcp 65001 > nul
title YKS-LGS Lisans Anahtari Uretici - EXE Derleyici
cd /d "%~dp0"

echo ======================================================================
echo    YKS-LGS LISANS ANAHTARI URETICI - STANDALONE EXE DERLEYICI
echo ======================================================================
echo.

set "PY_CMD="
if exist ".venv\Scripts\python.exe" set "PY_CMD=%~dp0.venv\Scripts\python.exe"

if not defined PY_CMD (
    py -3 -c "import sys" >nul 2>nul && set "PY_CMD=py -3"
)
if not defined PY_CMD (
    python -c "import sys" >nul 2>nul && set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [HATA] Python bulunamadi! Lutfen once Baslat_Windows.bat calistirin.
    pause
    exit /b 1
)

echo [1/2] PyInstaller ve PyQt6 bilesenleri kontrol ediliyor...
"%PY_CMD%" -c "import PyInstaller" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [BILGI] PyInstaller yukleniyor...
    "%PY_CMD%" -m pip install pyinstaller
)

echo [2/2] YKS_LGS_Lisans_Uretici.exe derleniyor (Lutfen bekleyin)...
echo.

set "ICON_ARG="
if exist "assets\app_icon.ico" (
    set "ICON_ARG=--icon=assets\app_icon.ico"
)

"%PY_CMD%" -m PyInstaller --noconfirm --clean --windowed --onefile --name="YKS_LGS_Lisans_Uretici" %ICON_ARG% --hidden-import=PyQt6 --collect-all=PyQt6 admin_keygen.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo  TEBRIKLER! YKS_LGS_Lisans_Uretici.exe BASARIYLA DERLENDI!
    echo ======================================================================
    echo.
    echo Olusturulan EXE Konumu:
    echo   dist\YKS_LGS_Lisans_Uretici.exe
    echo.
    if exist "dist\YKS_LGS_Lisans_Uretici.exe" (
        copy /y "dist\YKS_LGS_Lisans_Uretici.exe" "%~dp0YKS_LGS_Lisans_Uretici.exe" >nul
        echo Kolaylik olsun diye ana klasore de kopyalandi:
        echo   %~dp0YKS_LGS_Lisans_Uretici.exe
    )
    echo.
    echo Artik bu .exe dosyasini cift tiklayarak tek basina calistirabilirsiniz!
    echo ======================================================================
) else (
    echo.
    echo [HATA] Derleme sirasinda bir hata olustu.
)
echo.
pause
