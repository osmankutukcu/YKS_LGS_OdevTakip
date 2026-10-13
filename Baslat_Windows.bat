@echo off
chcp 65001 > nul
title YKS LGS Odev Takip Yoneticisi v2
echo ========================================================
echo       YKS LGS Odev Takip Yoneticisi v2 Baslatiliyor
echo ========================================================
echo.

if not exist ".venv" (
    echo [BILGI] Ilk calistirma tespit edildi.
    echo [BILGI] Python sanal ortami olusturuluyor (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [HATA] Python sanal ortami olusturulamadi!
        echo Lutfen bilgisayarinizda Python 3.10 veya uzerinin kurulu oldugundan
        echo ve "Add Python to PATH" seceneginin isaretli oldugundan emin olun.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate
    echo [BILGI] Gerekli paketler yukleniyor (bu islem internet hizina bagli olarak birkac dakika surebilir)...
    python -m pip install --upgrade pip
    pip install -r requirements_win.txt
    if errorlevel 1 (
        echo [UYARI] Bazi paketler yuklenirken hata olustu, yine de uygulama baslatilmaya calisilacak.
    )
) else (
    call .venv\Scripts\activate
)

echo [BILGI] Uygulama baslatiliyor...
python app.py
if errorlevel 1 (
    echo.
    echo [BILGI] Uygulama kapandi veya bir hata olustu.
    pause
)
