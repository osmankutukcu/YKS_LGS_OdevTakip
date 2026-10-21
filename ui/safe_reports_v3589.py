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
        self._is_updating = False

        # Grafik türü seçildiği anda 'Göster' butonuna basmadan anında çiz
        self.cmbTur.currentIndexChanged.connect(self._on_tur_changed)

    def _on_tur_changed(self, index: int):
        if not getattr(self, "_is_updating", False):
            self._goster()

    def _generate_smart_insights(self, chart_type, data):
        self.txtInsight.setHtml(interpret_chart(chart_type, data))

    def _goster(self):
        if self.dtpBas.date() > self.dtpBit.date():
            QMessageBox.warning(
                self, "Tarih Aralığı", "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
            return

        tur_label = self.cmbTur.currentText()
        if tur_label == "Konu Verimi (dk/konu)":
            return self._goster_konu_verimi_yatay()

        self._is_updating = True
        try:
            res = super()._goster()
            # Dikey çubuk grafiklerinde x ekseni etiketlerini sağa hizalayarak çakışmayı önle
            try:
                for tick in self.ax.get_xticklabels():
                    tick.set_ha("right")
                self.fig.tight_layout()
                self.canvas.draw_idle()
            except Exception:
                pass
            return res
        finally:
            self._is_updating = False

    def _goster_konu_verimi_yatay(self):
        """Konu Verimi grafiğini çakışmaları önlemek için profesyonel yatay çubuk (barh) olarak çizer."""
        self._is_updating = True
        try:
            bas = self.dtpBas.date().toString("yyyy-MM-dd")
            bit = self.dtpBit.date().toString("yyyy-MM-dd")
            ogr = self._secili_ogr_idler()
            ders = self._secili_dersler()
            tur_label = self.cmbTur.currentText()

            self.ax.clear()
            self._last_table_rows = []

            subtitle_parts = []
            if ogr:
                subtitle_parts.append(f"{len(ogr)} öğrenci")
            if ders:
                subtitle_parts.append(f"{len(ders)} ders")
            subtitle = " | ".join(subtitle_parts) if subtitle_parts else "Tüm Kayıtlar"

            # Özet güncelle
            self._guncel_ozet(bas, bit, ogr, ders)

            rows = self._konu_verimi(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))

            if not labels:
                self.ax.text(
                    0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                    ha="center", va="center", transform=self.ax.transAxes, alpha=0.7
                )
            else:
                # barh için en yüksek değer üstte olacak şekilde ters çevir
                y_labels = list(reversed(labels))
                x_vals = list(reversed(vals))
                y_pos = list(range(len(y_labels)))

                bars = self.ax.barh(
                    y_pos, x_vals,
                    color="#2563eb", edgecolor="#1d4ed8", height=0.65
                )
                self.ax.set_yticks(y_pos)

                # Uzun konu başlıklarını zarifçe formatla
                formatted_labels = [
                    lbl[:36] + "…" if len(lbl) > 38 else lbl
                    for lbl in y_labels
                ]
                self.ax.set_yticklabels(formatted_labels, fontsize=8.5)

                # Çubukların yanına değerleri yazdır
                max_val = max(x_vals) if x_vals else 1.0
                for bar, val in zip(bars, x_vals):
                    if val > 0:
                        val_str = f"{int(val)}" if abs(val - int(val)) < 0.01 else f"{val:.1f}"
                        self.ax.annotate(
                            f"{val_str} dk",
                            (bar.get_width(), bar.get_y() + bar.get_height() / 2.0),
                            ha="left", va="center", fontsize=8.5, xytext=(4, 0),
                            textcoords="offset points", color="#1e293b", weight="bold"
                        )

                self.ax.set_xlabel("Ortalama Çalışma Süresi (dk/konu)", fontsize=9)
                self.ax.set_xlim(0, max_val * 1.18 if max_val > 0 else 10)
                self.ax.grid(axis="x", linestyle="--", alpha=0.3)
                self.ax.set_title(f"Konu Verimi (dk/konu)\n{bas} → {bit}  •  {subtitle}", fontsize=10.5)

            self.fig.tight_layout()
            self.canvas.draw_idle()

            # Akıllı analiz
            self._generate_smart_insights(tur_label, self._last_table_rows)
        finally:
            self._is_updating = False
