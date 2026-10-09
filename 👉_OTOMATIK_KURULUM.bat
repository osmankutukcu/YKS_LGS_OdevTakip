@echo off
chcp 65001 > nul
title YKS-LGS Odev Takip v2 - Otomatik Kurulum Sihirbazi

echo ======================================================================
echo       YKS-LGS ODEV TAKIP v2 - OTOMATIK KURULUM SIHIRBAZI
echo ======================================================================
echo.

set "SOURCE_DIR=%~dp0"
set "TARGET_DIR=%LOCALAPPDATA%\YKS_LGS_OdevTakip"

REM -----------------------------------------------------------------------
REM 1. ZIP ICINDEN CALISTIRILMA KONTROLU
REM -----------------------------------------------------------------------
echo %SOURCE_DIR% | findstr /I "Temp" >nul
if %ERRORLEVEL% equ 0 (
    echo [DIKKAT] Dosya ZIP arsivinden cikarilmadan calistirildi!
    set "VBS_ERR=%TEMP%\zip_err.vbs"
    echo MsgBox "Lutfen once ZIP dosyasina sag tiklayip 'Tumunu Ayikla...' (Extract All) deyiniz." ^& vbCrLf ^& vbCrLf ^& "Cikan klasorun icindeki kurulum dosyasina tiklayiniz.", 48, "Kurulum Uyarisi" > "%VBS_ERR%"
    start "" wscript.exe "%VBS_ERR%"
    exit /b 1
)

REM -----------------------------------------------------------------------
REM 2. DOSYALARI WINDOWS'A GUVENLE KOPYALA
REM -----------------------------------------------------------------------
echo [1/4] Program dosyalari Windows sisteminize yerlestiriliyor...
echo       Hedef: %TARGET_DIR%
echo.

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

REM Eger hedefte onceden veritabani varsa guvenle koru
set "DB_TEMP=%TEMP%\yks_db_backup_%RANDOM%"
if exist "%TARGET_DIR%\YKS_LGS_HomeworkManager.db" (
    mkdir "%DB_TEMP%" >nul 2>&1
    copy /y "%TARGET_DIR%\YKS_LGS_HomeworkManager.db" "%DB_TEMP%\" >nul 2>&1
    if exist "%TARGET_DIR%\license.json" copy /y "%TARGET_DIR%\license.json" "%DB_TEMP%\" >nul 2>&1
)

REM Dosyalari kopyala
xcopy /s /e /y "%SOURCE_DIR%*" "%TARGET_DIR%\" >nul 2>&1

REM Eski veritabanini geri yukle (asla ezme)
if exist "%DB_TEMP%\YKS_LGS_HomeworkManager.db" (
    copy /y "%DB_TEMP%\YKS_LGS_HomeworkManager.db" "%TARGET_DIR%\" >nul 2>&1
    if exist "%DB_TEMP%\license.json" copy /y "%DB_TEMP%\license.json" "%TARGET_DIR%\" >nul 2>&1
    rmdir /s /q "%DB_TEMP%" >nul 2>&1
    echo [BILGI] Mevcut ogrenci veritabani ve lisansiniz guvenle korundu.
)

echo [OK] Program dosyalari basariyla yerlestirildi.
echo.

REM -----------------------------------------------------------------------
REM 3. GEREKLI ORTAMI HAZIRLA (Eger EXE degilse ve .venv yoksa)
REM -----------------------------------------------------------------------
if not exist "%TARGET_DIR%\OdevTakip_v2.exe" (
    if not exist "%TARGET_DIR%\.venv\Scripts\python.exe" (
        echo [2/4] Calisma ortami ve bilesenler hazirlaniyor...
        cd /d "%TARGET_DIR%"
        call "%TARGET_DIR%\Windows_Kurulum_ve_Baslat.bat"
        goto create_shortcuts
    )
)
echo [2/4] Calisma bilesenleri kontrol edildi (Hazir).
echo.

:create_shortcuts
REM -----------------------------------------------------------------------
REM 4. MASAUSTU VE BASLAT MENUSU KISAYOLLARI
REM -----------------------------------------------------------------------
echo [3/4] Masaustu ve Baslat Menusu kisayollari hazirlaniyor...
set "VBS_SC=%TEMP%\create_all_shortcuts.vbs"

(
echo Set oWS = WScript.CreateObject("WScript.Shell")
echo.
echo sDeskLink = oWS.SpecialFolders("Desktop") ^& "\YKS-LGS Odev Takip.lnk"
echo Set oDesk = oWS.CreateShortcut(sDeskLink)
if exist "%TARGET_DIR%\OdevTakip_v2.exe" (
    echo oDesk.TargetPath = "%TARGET_DIR%\OdevTakip_v2.exe"
) else (
    echo oDesk.TargetPath = "%TARGET_DIR%\Baslat_Sessiz.vbs"
)
echo oDesk.WorkingDirectory = "%TARGET_DIR%"
if exist "%TARGET_DIR%\assets\app_icon.ico" (
    echo oDesk.IconLocation = "%TARGET_DIR%\assets\app_icon.ico, 0"
)
echo oDesk.Description = "YKS - LGS Odev ve Takip Yoneticisi"
echo oDesk.Save
echo.
echo sProgLink = oWS.SpecialFolders("Programs") ^& "\YKS-LGS Odev Takip.lnk"
echo Set oProg = oWS.CreateShortcut(sProgLink)
if exist "%TARGET_DIR%\OdevTakip_v2.exe" (
    echo oProg.TargetPath = "%TARGET_DIR%\OdevTakip_v2.exe"
) else (
    echo oProg.TargetPath = "%TARGET_DIR%\Baslat_Sessiz.vbs"
)
echo oProg.WorkingDirectory = "%TARGET_DIR%"
if exist "%TARGET_DIR%\assets\app_icon.ico" (
    echo oProg.IconLocation = "%TARGET_DIR%\assets\app_icon.ico, 0"
)
echo oProg.Description = "YKS - LGS Odev ve Takip Yoneticisi"
echo oProg.Save
) > "%VBS_SC%"

cscript //nologo "%VBS_SC%" >nul 2>&1
del "%VBS_SC%" 2>nul
echo [OK] Masaustune ve Baslat Menusune logolu kisayol olusturuldu!
echo.

REM -----------------------------------------------------------------------
REM 5. BILDIRIM VE PROGRAMI BASLATMA
REM -----------------------------------------------------------------------
echo [4/4] Kurulum basariyla tamamlandi! Uygulama baslatiliyor...
echo.

set "VBS_MSG=%TEMP%\install_msg.vbs"
(
echo MsgBox "YKS-LGS Odev Takip Yoneticisi basariyla kuruldu!" ^& vbCrLf ^& vbCrLf ^& "Masaustunuze 'YKS-LGS Odev Takip' simgesi yerlestirildi. Artik dilediginiz zaman masaustundeki bu simgeye tiklayarak programi acabilirsiniz.", 64, "Kurulum Basarili"
) > "%VBS_MSG%"
start "" wscript.exe "%VBS_MSG%"

cd /d "%TARGET_DIR%"
if exist "%TARGET_DIR%\OdevTakip_v2.exe" (
    start "" "%TARGET_DIR%\OdevTakip_v2.exe"
) else (
    start "" wscript.exe "%TARGET_DIR%\Baslat_Sessiz.vbs"
)

timeout /t 2 /nobreak >nul
exit /b 0
