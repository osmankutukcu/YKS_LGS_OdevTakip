@echo off
chcp 65001 > nul
title YKS-LGS Odev Takip v2 - Windows EXE ve Kurulum Uretici

echo ======================================================================
echo       YKS-LGS ODEV TAKIP v2 - WINDOWS EXE VE KURULUM DERLEYICI
echo ======================================================================
echo.

cd /d "%~dp0"

REM -----------------------------------------------------------------------
REM 1. PYTHON VE SANAL ORTAM (.venv) KONTROLU
REM -----------------------------------------------------------------------
echo [1/3] Python ve calisma ortami kontrol ediliyor...

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    goto py_ready
)

REM Sanal ortam henüz yoksa sistemdeki Python'u ara
set "SYS_PY="
py -3 -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "SYS_PY=py -3"
    goto make_venv
)

python -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "SYS_PY=python"
    goto make_venv
)

REM 1.3 Yaygin Python konumlari (calisabilirlik testi ile)
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python312\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys" >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            set "SYS_PY=%%~P"
            goto make_venv
        )
    )
)

REM Eger Python bulundu ama calismiyorsa (VCRUNTIME / Bad Image hatasi)
echo.
echo [UYARI] Sistemde Python tespit edildi ancak VCRUNTIME140 eksik oldugu icin calisamadi.
echo Microsoft Visual C++ Calisma Zamani (vc_redist) otomatik indiriliyor ve kuruluyor...
curl.exe -L -o "%TEMP%c_redist.x64.exe" https://aka.ms/vs/17/release/vc_redist.x64.exe
if exist "%TEMP%c_redist.x64.exe" (
    "%TEMP%c_redist.x64.exe" /passive /norestart
    timeout /t 3 /nobreak >nul
)

REM Hiçbir Python bulunamadıysa uyarı ve indirme
echo.
echo ======================================================================
echo  [DIKKAT] Bilgisayarinizda Python bulunamadi!
echo ======================================================================
echo Python yukleyicisi indiriliyor, lutfen bekleyin...
set "INSTALLER=%TEMP%\python_setup.exe"
curl.exe -L -o "%INSTALLER%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if not exist "%INSTALLER%" (
    echo [HATA] Python otomatik indirilemedi.
    echo Lutfen https://www.python.org/downloads/ adresinden Python kurun.
    echo Kurulum ekraninda "Add python.exe to PATH" kutucugunu MUTLAKA isaretleyin!
    pause
    exit /b 1
)
"%INSTALLER%" PrependPath=1 Include_pip=1
py -3 -c "import sys" >nul 2>nul && set "SYS_PY=py -3" && goto make_venv
python -c "import sys" >nul 2>nul && set "SYS_PY=python" && goto make_venv
echo [HATA] Python kurulumu tamamlanamadi. Lutfen manuel kurup tekrar deneyin.
pause
exit /b 1

:make_venv
echo [BILGI] Derleme icin temiz sanal ortam (.venv) olusturuluyor...
%SYS_PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo [HATA] .venv olusturulamadi!
    pause
    exit /b 1
)
set "PY_CMD=%~dp0.venv\Scripts\python.exe"

:py_ready
echo [OK] Python ortami hazir: %PY_CMD%
echo.

REM -----------------------------------------------------------------------
REM 2. GEREKLI KUTUPHANELERIN KONTROLU VE KURULUMU (PyQt6, PyInstaller vb.)
REM -----------------------------------------------------------------------
echo [2/3] Derleme kutuphaneleri (PyQt6, PyInstaller, Raporlama vb.) kontrol ediliyor...
"%PY_CMD%" -c "import PyQt6, PyInstaller" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo.
    echo [BILGI] Gerekli kutuphaneler tespit edilemedi veya eksik.
    echo [BILGI] PyQt6 ve tum derleme bilesenleri kuruluyor...
    echo       (Internet baglantiniza bagli olarak 1-2 dakika surebilir)
    echo.
    "%PY_CMD%" -m pip install --upgrade pip
    if exist "requirements_win.txt" (
        "%PY_CMD%" -m pip install -r requirements_win.txt pyinstaller
    ) else (
        "%PY_CMD%" -m pip install PyQt6 pandas openpyxl reportlab pillow matplotlib pyinstaller
    )
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [HATA] Kutuphaneler yuklenirken bir sorun olustu!
        echo Lutfen internet baglantinizi kontrol edip tekrar deneyin.
        pause
        exit /b 1
    )
)
echo [OK] Tum kutuphaneler (PyQt6 dahil) ve PyInstaller hazir!
echo.

REM -----------------------------------------------------------------------
REM 3. EXE VE INSTALLER DERLEME SURECI
REM -----------------------------------------------------------------------
echo [3/3] Derleme islemi baslatiliyor (PyInstaller ve Inno Setup)...
echo.

REM 3.1 Lisans Anahtarı Üretici (Keygen EXE) Derle
echo [3.1] Lisans Anahtari Uretici (YKS_LGS_Lisans_Uretici.exe) derleniyor...
"%PY_CMD%" -m PyInstaller --noconfirm --clean --windowed --onefile --name="YKS_LGS_Lisans_Uretici" --icon="assets\app_icon.ico" --hidden-import=PyQt6 --collect-all=PyQt6 admin_keygen.py >nul 2>nul
if exist "dist\YKS_LGS_Lisans_Uretici.exe" (
    copy /y "dist\YKS_LGS_Lisans_Uretici.exe" "%~dp0YKS_LGS_Lisans_Uretici.exe" >nul
)

REM 3.2 Ana Uygulama ve Installer Derle
echo [3.2] Ana program ve kurulum paketi derleniyor...
"%PY_CMD%" build_installer.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ======================================================================
    echo [HATA] Derleme sirasinda bir hata olustu (Hata Kodu: %ERRORLEVEL%).
    echo ======================================================================
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ======================================================================
echo           TEBRIKLER! DERLEME BASARIYLA TAMAMLANDI!
echo ======================================================================
echo.
echo Olusturulan Dosyalar:
echo   1. Ana Program (EXE):
echo      dist\OdevTakip_v2\OdevTakip_v2.exe
echo.
echo   2. Bagimsiz Lisans Uretici (EXE):
echo      dist\YKS_LGS_Lisans_Uretici.exe (ve ana dizinde: YKS_LGS_Lisans_Uretici.exe)
echo.
if exist "dist\OdevTakip_v2_Kurulum.exe" (
    echo   3. Windows Kurulum Setup Paketi:
    echo      dist\OdevTakip_v2_Kurulum.exe
    echo.
)
echo Bu exe dosyalarini istediginiz Windows bilgisayara tasiyabilir,
echo baska bilgisayarlarda hicbir kurulum yapmadan dogrudan calistirabilirsiniz.
echo ======================================================================
echo.
pause
