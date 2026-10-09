# ui/quick_meet.py
# -*- coding: utf-8 -*-
"""
Tek kaynak yönlendirme:
Bu dosya, RandevuTakvimi'ni her zaman ui/randevu_takvimi.py içindeki sürümden kullanır.
Projede quick_meet'ten import edilmiş yerler de otomatik olarak yeni sınıfa yönlenir.
"""

from ui.randevu_takvimi import RandevuTakvimi as _RandevuTakvimi

# Dışarıya aynı isimle açalım:
RandevuTakvimi = _RandevuTakvimi
__all__ = ["RandevuTakvimi"]

# (Opsiyonel) Bu dosyayı doğrudan çalıştırırsan test penceresi açar.
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = _RandevuTakvimi()
    w.setWindowTitle("Randevu ve Ödev Takip Takvimi")
    w.show()
    sys.exit(app.exec())
