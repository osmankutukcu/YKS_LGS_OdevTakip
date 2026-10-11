#!/bin/bash

# Pencere Başlığı
echo -n -e "\033]0;YKS-LGS Ödev Takip\007"

echo "========================================="
echo "   🚀 YKS-LGS Ödev Takip Başlatılıyor   "
echo "========================================="
echo ""

# Script'in bulunduğu klasöre git
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || {
    echo "❌ Proje klasörüne erişilemedi!"
    read -p "Çıkmak için Enter tuşuna basın..."
    exit 1
}

# Uygulamayı sanal ortam (venv) Python ile çalıştır
if [ -f "./.venv/bin/python" ]; then
    "./.venv/bin/python" app.py
else
    python3 app.py
fi
