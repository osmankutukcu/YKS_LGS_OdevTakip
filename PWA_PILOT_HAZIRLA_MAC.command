#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

echo "V12 PWA PILOT - Ana veritabaninin KOPYASINI olusturur, orijinale yazmaz."
DEFAULT_DB="$DIR/YKS_LGS_HomeworkManager.db"
echo "Varsayilan dosya: $DEFAULT_DB"
read -p "SQLite dosyasi (bos birakirsaniz varsayilan secilir): " ORIGINAL_DB
if [ -z "$ORIGINAL_DB" ]; then
    ORIGINAL_DB="$DEFAULT_DB"
fi

"$PYTHON" tools/pwa_v12_pilot.py backup --source "$ORIGINAL_DB"
if [ $? -ne 0 ]; then
    echo "Kurulum gerceklesmedi. Ekrandaki hatayi kontrol edin."
fi
read -p "Devam etmek icin Enter'a basin..."
