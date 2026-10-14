#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo "      YKS LGS Odev Takip Yoneticisi v2 Baslatiliyor"
echo "========================================================"
echo ""

if [ ! -d ".venv" ]; then
    echo "[BILGI] Ilk calistirma tespit edildi."
    echo "[BILGI] Python sanal ortami olusturuluyor (.venv)..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[HATA] Python sanal ortami olusturulamadi!"
        echo "Lutfen Mac'inizde Python 3 kurulu oldugundan emin olun."
        read -p "Cikis icin Enter'a basin..."
        exit 1
    fi
    source .venv/bin/activate
    echo "[BILGI] Gerekli paketler yukleniyor..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "[BILGI] Uygulama baslatiliyor..."
python3 app.py
if [ $? -ne 0 ]; then
    echo ""
    echo "[BILGI] Uygulama kapandi veya bir hata olustu."
    read -p "Cikis icin Enter'a basin..."
fi
