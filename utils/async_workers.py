# -*- coding: utf-8 -*-
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
import traceback, sys

class IsParcacigi(QRunnable):
    """Basit QRunnable sarmalayıcı: bir fonksiyonu arka planda koşturur."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = Isaretler()

    def run(self):
        try:
            sonuc = self.fn(*self.args, **self.kwargs, progress=self.signals.progress)
            self.signals.sonuc.emit(sonuc)
        except Exception as e:
            tb = traceback.format_exc()
            self.signals.hata.emit(f"{e}\n{tb}")
        finally:
            self.signals.bitti.emit()

class Isaretler(QObject):
    progress = pyqtSignal(int)       # yüzde
    sonuc = pyqtSignal(object)
    hata = pyqtSignal(str)
    bitti = pyqtSignal()

def arka_planda_calistir(fn, callback=None, hata_cb=None, ilerleme_cb=None, *args, **kwargs):
    """Kolay kullanım: işi havuza atar."""
    ip = IsParcacigi(fn, *args, **kwargs)
    if callback:
        ip.signals.sonuc.connect(callback)
    if hata_cb:
        ip.signals.hata.connect(hata_cb)
    if ilerleme_cb:
        ip.signals.progress.connect(ilerleme_cb)
    havuz = QThreadPool.globalInstance()
    havuz.start(ip)
