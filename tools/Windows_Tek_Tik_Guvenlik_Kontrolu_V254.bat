@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
echo.
echo ================================================
echo ODEV TAKIP V25.4 - WINDOWS GUVENLIK KONTROLU
echo ================================================
echo Sahte test verileri kullanilir. WhatsApp acilmaz.
echo Mesaj gonderilmez. Veli ve ogrenci verisi okunmaz.
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        py -3 "tools\windows_readiness_v254.py"
        goto result
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        python "tools\windows_readiness_v254.py"
        goto result
    )
)
echo UYGUN PYTHON 3.10+ BULUNAMADI.
echo Test araci Python 3.10+ gerektirir; kendiliginden kurulum yapmaz.
echo Kaynak ZIP tek basina calisan Windows EXE degildir.
echo.
pause
exit /b 2
:result
if errorlevel 1 (
    echo.
    echo TEST BASARILI OLARAK DOGRULANAMADI. Arka plan motoru KAPALIDIR.
) else (
    echo.
    echo Yalnizca cevrimdisi sentetik test basarili. Arka plan motoru HALA KAPALIDIR.
)
echo.
echo Ayrintili sonucu rapor dosyasinda bulabilirsiniz.
pause
