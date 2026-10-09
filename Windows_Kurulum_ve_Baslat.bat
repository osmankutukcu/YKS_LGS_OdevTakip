@echo off
chcp 65001 > nul
title YKS-LGS Odev Takip v2 - Kurulum ve Baslatici

cd /d "%~dp0"

echo ======================================================================
echo          YKS - LGS ODEV TAKIP YONETICISI v2 - WINDOWS KURULUMU
echo ======================================================================
echo.

REM Log dosyası başlat
echo [Log Baslangici: %DATE% %TIME%] > "%~dp0kurulum_log.txt"

REM -----------------------------------------------------------------------
REM 1. GERÇEK PYTHON TESPİTİ
REM -----------------------------------------------------------------------
echo [1/4] Python kontrol ediliyor...
set "PY_CMD="

REM 1.1 py -3 dene (Official Python Launcher)
py -3 -c "import sys; print(sys.version)" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=py -3"
    goto py_found
)

REM 1.2 python dene (WindowsApps alias olmadığından emin ol)
python -c "import sys; print(sys.version)" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
    goto py_found
)

REM 1.3 Yaygın yükleme dizinleri
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto py_found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto py_found
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python311\python.exe"
    goto py_found
)
if exist "%ProgramFiles%\Python312\python.exe" (
    set "PY_CMD=%ProgramFiles%\Python312\python.exe"
    goto py_found
)

:py_not_found
echo.
echo ======================================================================
echo  [DIKKAT] Bilgisayarinizda Python bulunamadi!
echo ======================================================================
echo.
echo Python yukleyicisi indiriliyor, lutfen bekleyin...
echo.

set "INSTALLER=%TEMP%\python_setup.exe"
curl.exe -L -o "%INSTALLER%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

if not exist "%INSTALLER%" (
    echo [HATA] Otomatik indirme yapilamadi.
    echo Tarayicinizda resmi Python indirme sayfasi aciliyor...
    start https://www.python.org/downloads/
    echo.
    echo Lutfen Python'u kurun ve kurulum penceresinin altindaki
    echo [X] 'Add python.exe to PATH' kutucugunu MUTLAKA isaretleyin!
    echo Kurulum bitince bu pencereyi kapatip tekrar calistirin.
    echo.
    pause
    exit /b 1
)

echo Python kurulum penceresi aciliyor.
echo ONEMLI: Alttaki "Add python.exe to PATH" secenegini isaretlemeyi unutmayin!
"%INSTALLER%" PrependPath=1 Include_pip=1

REM Kurulum sonrası tekrar kontrol et
py -3 -c "import sys" >nul 2>nul && set "PY_CMD=py -3" && goto py_found
python -c "import sys" >nul 2>nul && set "PY_CMD=python" && goto py_found

echo.
echo [BILGI] Python kurulduktan sonra lutfen bu dosyayi tekrar calistirin.
pause
exit /b 0

:py_found
echo [OK] Python bulundu: %PY_CMD%
%PY_CMD% -c "import sys; print('Python Surumu:', sys.version)" >> "%~dp0kurulum_log.txt" 2>&1
echo.

REM -----------------------------------------------------------------------
REM 2. SANAL ORTAM (VENV)
REM -----------------------------------------------------------------------
echo [2/4] Sanal ortam (.venv) kontrol ediliyor...
if not exist ".venv\Scripts\python.exe" (
    echo .venv olusturuluyor, lutfen bekleyin...
    %PY_CMD% -m venv .venv >> "%~dp0kurulum_log.txt" 2>&1
    if not exist ".venv\Scripts\python.exe" (
        echo [HATA] Sanal ortam olusturulamadi! Detaylar 'kurulum_log.txt' dosyasinda.
        pause
        exit /b 1
    )
)
echo [OK] Sanal ortam hazir (.venv).
echo.

REM -----------------------------------------------------------------------
REM 3. KUTUPHANELER
REM -----------------------------------------------------------------------
echo [3/4] Gerekli kutuphaneler kontrol ediliyor ve kuruluyor...
echo (PyQt6, pandas, openpyxl, reportlab vb. internet hizina gore 1-2 dk surebilir)
echo.

".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%~dp0kurulum_log.txt" 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements_win.txt >> "%~dp0kurulum_log.txt" 2>&1

echo [OK] Kutuphane kontrolleri tamamlandi.
echo.

REM -----------------------------------------------------------------------
REM 4. MASAUSTU KISAYOLU
REM -----------------------------------------------------------------------
echo [4/4] Masaustu kisayolu hazirlaniyor...
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\create_sc.vbs"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\YKS-LGS Odev Takip.lnk" >> "%TEMP%\create_sc.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\create_sc.vbs"
echo oLink.TargetPath = "%~dp0Baslat_Windows.bat" >> "%TEMP%\create_sc.vbs"
echo oLink.WorkingDirectory = "%~dp0" >> "%TEMP%\create_sc.vbs"
if exist "%~dp0assets\app_icon.ico" (
    echo oLink.IconLocation = "%~dp0assets\app_icon.ico" >> "%TEMP%\create_sc.vbs"
)
echo oLink.Save >> "%TEMP%\create_sc.vbs"
cscript //nologo "%TEMP%\create_sc.vbs" >nul 2>nul
del "%TEMP%\create_sc.vbs" 2>nul

echo [OK] Masaustune kisayol olusturuldu!
echo.

REM -----------------------------------------------------------------------
REM 5. UYGULAMAYI BASLAT
REM -----------------------------------------------------------------------
echo ======================================================================
echo  Kurulum Basariyla Tamamlandi! Uygulama Baslatiliyor...
echo ======================================================================
echo.

".venv\Scripts\python.exe" app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [BILGI] Uygulama kapandi (Hata Kodu: %ERRORLEVEL%).
    echo Ayrintilar icin kurulum_log.txt dosyasini inceleyebilirsiniz.
    pause
)
