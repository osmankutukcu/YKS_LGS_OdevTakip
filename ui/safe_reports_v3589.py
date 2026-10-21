# -*- coding: utf-8 -*-
"""Gelişmiş Raporlar için isteğe bağlı, salt-sunum odaklı açıklama katmanı.

Korunan ui/reports.py byte-byte orijinal bırakılır. Tüm SQL, çizimler,
filtreler ve PDF/Excel dışa aktarımı aynı üst sınıf üzerinden çalışır.
"""
from PyQt6.QtWidgets import QMessageBox
from ui.reports import RaporlarFormu
from services.report_interpretation_v3589 import interpret_chart


class AciklanabilirRaporlarFormu(RaporlarFormu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lblInsightHeader.setText("💡 Veriye Dayalı Açıklama ve Kontrol Önerisi")

    def _generate_smart_insights(self, chart_type, data):
        self.txtInsight.setHtml(interpret_chart(chart_type, data))

    def _goster(self):
        if self.dtpBas.date() > self.dtpBit.date():
            QMessageBox.warning(
                self, "Tarih Aralığı", "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
            return
        return super()._goster()
