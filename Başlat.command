#!/bin/bash
# ===================================================
#  YKS/LGS Ödev & Takip Yöneticisi v2 - macOS Başlatıcı
#  Finder üzerinden çift tıklayarak çalıştırabilirsiniz.
# ===================================================

# Scriptin bulunduğu klasöre geç
cd "$(dirname "$0")"

echo "=========================================="
echo "   YKS/LGS Ödev & Takip Yöneticisi v2     "
echo "=========================================="
echo "Uygulama başlatılıyor, lütfen bekleyin..."

# Sanal ortam python yolunu belirle
if [ -f ".venv/bin/python" ]; then
    PYTHON_EXEC=".venv/bin/python"
elif [ -f ".venv_old_20251029132201/bin/python" ]; then
    PYTHON_EXEC=".venv_old_20251029132201/bin/python"
else
    PYTHON_EXEC="python3"
fi

# Uygulamayı çalıştır
"$PYTHON_EXEC" app.py

exit 0
