# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, 
    QFrame, QFileDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QAction

class SmartReportDialog(QDialog):
    def __init__(self, student_name, student_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Akıllı Koçluk Raporu - {student_name}")
        self.resize(700, 700)
        self.setStyleSheet("background-color: #f8fafc;")
        
        self.student_name = student_name
        self.student_data = student_data # Dict: progress, topics, goals etc.
        
        self._setup_ui()
        self._generate_txt_report()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl = QLabel(f"📊 {self.student_name} İçin Akıllı Rapor")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e3a8a;")
        layout.addWidget(lbl)
        
        # Options Row
        opt_lay = QHBoxLayout()
        opt_lay.addWidget(QLabel("Rapor Türü:"))
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Haftalık Özet", "Konu Bazlı İlerleme", "Koç Tavsiyeli Detay"])
        self.cmb_type.currentTextChanged.connect(self._generate_txt_report)
        opt_lay.addWidget(self.cmb_type)
        opt_lay.addStretch()
        layout.addLayout(opt_lay)
        
        # Preview
        self.txt_preview = QTextEdit()
        self.txt_preview.setStyleSheet("""
            QTextEdit {
                background: white; border: 1px solid #cbd5e1; 
                border-radius: 6px; padding: 10px; font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.txt_preview)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Style helper
        def get_btn_style(bg_color):
            return f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 8px 16px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: {bg_color}dd; }}
            """

        btn_copy = QPushButton("📋 Kopyala")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(get_btn_style("#3b82f6")) # Blue
        btn_copy.clicked.connect(self.txt_preview.selectAll)
        btn_copy.clicked.connect(self.txt_preview.copy)
        
        btn_save = QPushButton("💾 Dosyaya Kaydet")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(get_btn_style("#10b981")) # Green
        btn_save.clicked.connect(self._save_to_file)
        
        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(get_btn_style("#ef4444")) # Red
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_copy)
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def _generate_txt_report(self):
        rtype = self.cmb_type.currentText()
        today = QDate.currentDate().toString("dd.MM.yyyy")
        
        txt = f"🎓 YKS/LGS KOÇLUK RAPORU\n"
        txt += f"Öğrenci: {self.student_name}\n"
        txt += f"Tarih: {today}\n"
        txt += f"Rapor Türü: {rtype}\n"
        txt += "-"*40 + "\n\n"
        
        if rtype == "Haftalık Özet":
            txt += self._part_weekly_summary()
        elif rtype == "Konu Bazlı İlerleme":
            txt += self._part_topic_progress()
        else:
            txt += self._part_weekly_summary()
            txt += "\n" + "-"*20 + "\n\n"
            txt += self._part_topic_progress()
            txt += "\n" + "-"*20 + "\n\n"
            txt += self._part_coach_tips()
            
        txt += "\n" + "-"*40 + "\n"
        txt += f"Otomatik oluşturulmuştur."
        
        self.txt_preview.setPlainText(txt)

    def _part_weekly_summary(self):
        s = self.student_data.get("stats", {})
        rate = s.get("rate", 0)
        solved = s.get("total_solved", 0)
        target = s.get("total_target", 0)
        
        t = "1. HAFTALIK PERFORMANS\n"
        t += f"• Başarı Oranı: %{rate}\n"
        t += f"• Çözülen Soru: {solved} / {target}\n"
        
        if rate >= 80:
            t += "✅ Harika bir hafta! Hedeflerini büyük ölçüde tutturdun.\n"
        elif rate >= 50:
            t += "⚠️ İdare eder, ancak gelecek hafta tempoyu artırmalıyız.\n"
        else:
            t += "⭕ Hedeflerin çok gerisindeyiz. Planı gözden geçirmeliyiz.\n"
        return t

    def _part_topic_progress(self):
        topics = self.student_data.get("topics", [])
        if not topics:
            return "2. KONU İLERLEMESİ\n• Veri yok.\n"
            
        t = "2. KONU İLERLEMESİ\n"
        # Group by status
        started = [x for x in topics if x['status'] == 1]
        completed = [x for x in topics if x['status'] == 2]
        
        if completed:
            t += f"\n[TAMAMLANANLAR - {len(completed)}]\n"
            for x in completed:
                t += f"✓ {x['subject']} > {x['name']}\n"
                
        if started:
            t += f"\n[ÇALIŞILANLAR - {len(started)}]\n"
            for x in started:
                t += f"• {x['subject']} > {x['name']}\n"
        
        if not started and not completed:
            t += "• Henüz konu girişi yapılmamış.\n"
            
        return t

    def _part_coach_tips(self):
        # Akıllı koç yorumları (Curriculum'dan çekilen verilerle)
        # student_data içindeki topics listesinde 'coach_data' olabilir
        topics = self.student_data.get("topics", [])
        active_topics = [x for x in topics if x['status'] == 1]
        
        t = "3. KOÇ TAVSİYELERİ VE UYARILAR\n"
        
        if not active_topics:
            t += "• Aktif çalışılan konu bulunamadı. Lütfen 'Konu Takibi' sekmesinden konuları işaretleyin.\n"
            return t
            
        count = 0
        for top in active_topics:
            cdata = top.get('coach_data')
            if cdata:
                # Önemli ise uyar
                imp = cdata.get('importance', '')
                if "KRİTİK" in imp or "Yüksek" in imp:
                    t += f"\n📌 {top['name']} ({top['subject']}):\n"
                    # Tip
                    if cdata.get('tip'):
                        t += f"   💡 {cdata['tip']}\n"
                    # Common Mistakes
                    mistakes = cdata.get('common_mistakes', [])
                    if mistakes:
                        t += f"   ⚠️ Dikkat: {mistakes[0]}\n"
                    count += 1
                    if count >= 3: break # Çok uzatmamak için
        
        if count == 0:
            t += "• Seçili konular için özel uyarı bulunmuyor.\n"
            
        return t

    def _save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Rapor Kaydet", f"Rapor_{self.student_name}.txt", "Text Files (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.txt_preview.toPlainText())
                QMessageBox.information(self, "Başarılı", "Rapor kaydedildi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))
