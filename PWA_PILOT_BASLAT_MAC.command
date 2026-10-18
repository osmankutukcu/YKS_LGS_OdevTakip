#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" tools/pwa_v12_pilot.py preflight
if [ $? -ne 0 ]; then
    echo "PWA on denetimi basarisiz."
    read -p "Devam etmek icin Enter'a basin..."
    exit 1
fi

echo ""
echo "Mobil web sunucusu sadece BU bilgisayardaki localhost adresinde acilacak."
echo "Telefona erisim icin AYRICA guvenli HTTPS / Tailscale Serve gerekir."
"$PYTHON" tools/pwa_v12_pilot.py serve
