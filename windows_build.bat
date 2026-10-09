@echo off
echo ===================================================
echo     YKS/LGS Asistani v2 - Windows Build Script
echo ===================================================
echo.
echo 1. Eski build klasorleri temizleniyor...
rmdir /s /q build
rmdir /s /q dist

echo.
echo 2. PyInstaller ile EXE olusturuluyor (Spec dosyasi kullanilarak)...
echo    (Bu islem bi kac dakika surebilir, lutfen bekleyin)
echo.

:: PyInstaller'i spec dosyasiyla calistir
pyinstaller OdevTakip_v2.spec --noconfirm --clean

echo.
echo ===================================================
if %errorlevel% neq 0 (
    echo [HATA] Build islemi basarisiz oldu!
    echo Lutfen yukaridaki hata mesajlarini kontrol edin.
    pause
    exit /b %errorlevel%
)

echo [BASARILI] OdevTakip_v2.exe "dist" klasorunde olusturuldu.
echo.
echo Seed (Konu) dosyalari ve Assets EXE icine gomuldu.
echo ===================================================
pause
