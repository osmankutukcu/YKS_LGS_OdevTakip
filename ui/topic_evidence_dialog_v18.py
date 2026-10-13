"""Compact, read-only topic evidence dialog shared by Topic Map and Student360."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from urllib.parse import quote
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, QHeaderView,
    QScrollArea, QWidget, QFrame)
from services.topic_evidence_v18 import read_topic_evidence


class TopicEvidenceGuideDialog(QDialog):
    """Koçlar ve öğretmenler için Birleşik Kanıt Görünümü kullanım rehberi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧭 Birleşik Kanıt Görünümü | Koçluk ve Teşhis Rehberi")
        self.resize(720, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QLabel {
                color: #1e293b;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # Başlık Kartı
        title_box = QFrame()
        title_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e40af, stop:1 #3b82f6);
                border-radius: 10px;
                padding: 14px;
            }
        """)
        t_lay = QVBoxLayout(title_box)
        t_lay.setSpacing(4)
        t_title = QLabel("🧭 Birleşik Kanıt Görünümü Nedir & Koçlar Nasıl Kullanmalı?")
        t_title.setStyleSheet("color: white; font-size: 16px; font-weight: bold; background: transparent;")
        t_sub = QLabel("Pedagojik İlke: Ödev kutusunu işaretlemek konunun tam öğrenildiğini kanıtlamaz.")
        t_sub.setStyleSheet("color: #dbeafe; font-size: 13px; font-weight: 500; background: transparent;")
        t_lay.addWidget(t_title)
        t_lay.addWidget(t_sub)
        lay.addWidget(title_box)

        # İçerik Alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #cbd5e1; border-radius: 8px; background: white; }")
        
        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(16, 16, 16, 16)
        c_lay.setSpacing(16)

        info_html = """
        <div style="font-size: 13px; line-height: 1.6; color: #1e293b;">
            <h3 style="color: #0f172a; margin-top: 0; font-size: 15px;">🎯 1. Bu Ekranın Temel Felsefesi</h3>
            <p>Klasik ödev takibinde bir konuya sadece <b>"Yapıldı / Yapılmadı"</b> gözüyle bakılır. Ancak öğrenci ödevi baştan savma yapmış, cevap anahtarından geçirmiş veya çok zorlanmış olabilir.</p>
            <p>Bu ekran, öğrencinin gerçek öğrenme durumunu <b>5 farklı kanıt kaynağını</b> (Çapraz Kanıt Matrisi) yan yana getirerek doğrular:</p>
            <ol>
                <li><b>Ana Ödev Takibi:</b> Haftalık ödev formunda verilen görevlerin tamamlanma oranı.</li>
                <li><b>Konu Hakimiyet Haritası:</b> Öğrencinin akıllı müfredat kartlarındaki durumu.</li>
                <li><b>Öğretmen / Koçluk Gözlemi:</b> Ödev kontrolünde sağ tıklayarak verdiğiniz hızlı teşhis notları.</li>
                <li><b>Soru Çözüm Kanıtı:</b> Öğrencinin soru bankasındaki doğrulanmış Doğru / Yanlış / Boş sayıları.</li>
                <li><b>Ders Düzeyi Denemeler:</b> Sınavlarda o dersten elde edilen net sonuçları.</li>
            </ol>

            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 14px 0;" />

            <h3 style="color: #0f172a; font-size: 15px;">👨‍🏫 2. Koçlar Bu Ekrana Hangi Durumlarda Bakmalı?</h3>
            <ul>
                <li><b>🚨 Deneme Netleri Beklenenden Düşük Geldiğinde:</b> Öğrenci "tüm ödevlerimi yaptım" dediği halde denemede yanlışlar çıkıyorsa, buraya bakarak ödevin yüzeysel mi geçildiğini yoksa soru eksiği mi olduğunu anında tespit edebilirsiniz.</li>
                <li><b>🗓️ Haftalık Koçluk Seansı Öncesinde:</b> Öğrenciyle birebir görüşmeye oturmadan önce 1-2 dakika içinde hangi konularda çelişki veya açık çalışma olduğunu somut verilerle görürsünüz.</li>
                <li><b>🔍 Çelişkileri Yakalamak İçin:</b> Ödev formunda konu "bitti" göründüğü halde, konu haritasında eksik kalmışsa bu durum masaya yatırılır.</li>
                <li><b>📈 Takviye ve Hedef Belirlerken:</b> "Kontrol Önerisi" sütunundaki pedagojik tavsiyelere göre sonraki haftanın ödevlerini nokta atışı belirlersiniz.</li>
            </ul>

            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 14px 0;" />

            <h3 style="color: #0f172a; font-size: 15px;">📊 3. Tablo Sütunları Nasıl Yorumlanır?</h3>
            <table border="0" cellpadding="6" cellspacing="0" width="100%" style="border-collapse: collapse; font-size: 12.5px;">
                <tr style="background-color: #f1f5f9; text-align: left;">
                    <th style="border: 1px solid #cbd5e1; padding: 6px;">Sütun</th>
                    <th style="border: 1px solid #cbd5e1; padding: 6px;">Anlamı ve Koçluk Yorumu</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #e2e8f0; font-weight: bold; color: #1e40af;">Ana ödev açık/biten</td>
                    <td style="border: 1px solid #e2e8f0;">Ödev formundan verilen toplam ödev ve biten sayısı (Örn: 0 / 2 = 2 ödev de bitmiş).</td>
                </tr>
                <tr style="background-color: #f8fafc;">
                    <td style="border: 1px solid #e2e8f0; font-weight: bold; color: #1e40af;">Harita açık/biten</td>
                    <td style="border: 1px solid #e2e8f0;">Akıllı Konu Haritasında öğrencinin kendi kartlarında işaretlediği açık ve biten sayısı.</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #e2e8f0; font-weight: bold; color: #b45309;">Koçluk</td>
                    <td style="border: 1px solid #e2e8f0;">Ödev kontrolünde sağ tıklayarak girdiğiniz hızlı notlar (Örn: <i>Zaman yetmedi, Anlaşılmadı, Zorlandı</i>).</td>
                </tr>
                <tr style="background-color: #f8fafc;">
                    <td style="border: 1px solid #e2e8f0; font-weight: bold; color: #047857;">Soru kanıtı</td>
                    <td style="border: 1px solid #e2e8f0;">Konu bazında çözülen soruların Doğru (D) / Yanlış (Y) / Boş (B) dağılımı.</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #e2e8f0; font-weight: bold; color: #6b21a8;">Kontrol önerisi</td>
                    <td style="border: 1px solid #e2e8f0;">Algoritmanın koç için ürettiği pedagojik durum özeti (Örn: <i>"Çalışma tamamlanmış; denemeyle pekiştirin"</i>).</td>
                </tr>
            </table>

            <p style="margin-top: 12px; font-size: 12px; color: #64748b; background-color: #f1f5f9; padding: 8px 12px; border-radius: 6px;">
                💡 <b>Alt Kısım Uyarısı:</b> Tablonun altındaki deneme netleri ders düzeyindeki genel sınav performansıdır; tek bir konuya otomatik bağlanmaz, tablodaki konu verileriyle beraber yorumlanır.
            </p>
        </div>
        """
        lbl_content = QLabel(info_html)
        lbl_content.setWordWrap(True)
        lbl_content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        c_lay.addWidget(lbl_content)
        scroll.setWidget(content)
        lay.addWidget(scroll)

        # Kapat Butonu
        btn_close = QPushButton("Anladım, Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 9px 24px;
                border: none;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
        """)
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


class TopicEvidenceDialog(QDialog):
    def __init__(self, student_id, parent=None):
        super().__init__(parent)
        self.student_id = int(student_id) if student_id is not None else None
        self._report = None
        self.setWindowTitle('Konu Haritası | Birleşik Kanıt Görünümü')
        self.resize(1080, 750)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QLabel {
                color: #1e293b;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                font-size: 12.5px;
                color: #1e293b;
                selection-background-color: #dbeafe;
                selection-color: #1e3a8a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 10px;
                border: none;
                border-right: 1px solid #e2e8f0;
                border-bottom: 2px solid #cbd5e1;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                font-size: 12.5px;
                color: #1e293b;
                line-height: 1.5;
            }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        self.head = QLabel('Konu bazlı ödev/koçluk kayıtları ve ders düzeyindeki denemeler')
        self.head.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a; padding: 2px 0;")
        self.head.setWordWrap(True)
        root.addWidget(self.head)

        self.notice = QLabel('Ödev tamamlamak = konu öğrenildi demek değildir. Deneme netleri konuya otomatik atanmaz.')
        self.notice.setStyleSheet("font-size: 12.5px; font-weight: 500; color: #1e40af; background-color: #eff6ff; "
                                  "border: 1px solid #bfdbfe; border-radius: 6px; padding: 7px 12px;")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        refresh = QPushButton('↻  Verileri Yenile')
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0f766e;
                font-weight: 600;
                font-size: 12.5px;
                border: 1.5px solid #2dd4bf;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f0fdfa;
                border-color: #0d9488;
                color: #115e59;
            }
            QPushButton:pressed {
                background-color: #ccfbf1;
            }
        """)
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)

        copy = QPushButton('📋  Raporu Kopyala')
        copy.setCursor(Qt.CursorShape.PointingHandCursor)
        copy.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #4338ca;
                font-weight: 600;
                font-size: 12.5px;
                border: 1.5px solid #a5b4fc;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #eef2ff;
                border-color: #6366f1;
                color: #3730a3;
            }
            QPushButton:pressed {
                background-color: #e0e7ff;
            }
        """)
        copy.clicked.connect(self.copy_report)
        buttons.addWidget(copy)

        import_questions = QPushButton('📥  Soru–Konu Dosyası')
        import_questions.setCursor(Qt.CursorShape.PointingHandCursor)
        import_questions.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #1d4ed8;
                font-weight: 600;
                font-size: 12.5px;
                border: 1.5px solid #93c5fd;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #3b82f6;
                color: #1e40af;
            }
            QPushButton:pressed {
                background-color: #dbeafe;
            }
        """)
        import_questions.clicked.connect(self.import_question_evidence)
        buttons.addWidget(import_questions)

        # ℹ️ Bilgi & Koçluk Rehberi Butonu
        help_btn = QPushButton("ℹ️  Nasıl Kullanılır? (Koçluk Rehberi)")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setToolTip("Birleşik kanıt tablosunun amacı, koçluk yorumu ve kullanım senaryoları")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                color: #15803d;
                font-weight: 600;
                font-size: 12.5px;
                border: 1.5px solid #86efac;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #dcfce7;
                border-color: #22c55e;
                color: #166534;
            }
            QPushButton:pressed {
                background-color: #bbf7d0;
            }
        """)
        help_btn.clicked.connect(self.show_help_dialog)
        buttons.addWidget(help_btn)

        buttons.addStretch()
        root.addLayout(buttons)

        self.grid = QTableWidget(0, 7)
        self.grid.setHorizontalHeaderLabels(['Ders', 'Konu', 'Ana ödev açık/biten', 'Harita açık/biten', 'Koçluk', 'Soru kanıtı', 'Kontrol önerisi'])
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setAlternatingRowColors(True)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.grid.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.grid.itemSelectionChanged.connect(self.show_details)
        root.addWidget(self.grid, stretch=3)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        root.addWidget(self.details, stretch=1)

        close_btn = QPushButton('Kapat')
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                font-weight: 600;
                font-size: 13px;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
        """)
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def show_help_dialog(self):
        """Koçlar için bilgilendirme rehberini açar."""
        dlg = TopicEvidenceGuideDialog(self)
        dlg.exec()

    def refresh(self):
        self.grid.setRowCount(0)
        self._report = None
        if not self.student_id:
            self.details.setPlainText('Önce bir öğrenci seçin.')
            return
        from db import DB_PATH
        try:
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri,uri=True,timeout=8)) as con:
                con.execute('PRAGMA query_only=ON')
                report = read_topic_evidence(con,self.student_id)
        except (sqlite3.Error,ValueError,OSError) as exc:
            self.details.setPlainText('Veriler okunamadı: ' + str(exc) + '\nHiçbir kayıt değiştirilmedi.')
            return
        self._report = report
        self.head.setText(f'{report.student_name} | Birleşik Konu Kanıtları ({len(report.topics)} kayıtlı konu)')
        self.grid.setRowCount(len(report.topics))
        for row,topic in enumerate(report.topics):
            columns = (topic.lesson,topic.topic,f'{topic.main_open} / {topic.main_done}',
                       f'{topic.map_open} / {topic.map_done}',
                       ('Belirsiz' if topic.duplicate_teacher_records else
                        ('Yok' if topic.teacher_state is None else f'İşaret: {topic.teacher_state}')),
                       f'{topic.question_correct}D / {topic.question_wrong}Y / {topic.question_blank}B',
                       topic.recommendation)
            for col,label in enumerate(columns):
                item=QTableWidgetItem(str(label))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(row,col,item)
        exam_lines=['Ders düzeyinde deneme sonuçları (konu kanıtı değildir):']
        exam_lines += [f'• {e.lesson}: {e.latest} ({e.count} kayıt)' for e in report.exam_context]
        if not report.exam_context: exam_lines.append('• Kayıtlı, doğrulanmış deneme sonucu yok.')
        if report.warnings: exam_lines += ['', 'Uyarılar:', *('• ' + s for s in report.warnings)]
        self._course_text='\n'.join(exam_lines)
        self.show_details()

    def show_details(self):
        if self._report is None: return
        items=self.grid.selectedItems()
        row=items[0].row() if items else -1
        if row >= 0 and row < len(self._report.topics):
            t=self._report.topics[row]
            text=f'{t.lesson} / {t.topic}\n{t.recommendation}'
            if t.question_correct+t.question_wrong+t.question_blank:
                text+=f'\nÖğretmen onaylı soru kayıtları: {t.question_correct} doğru, {t.question_wrong} yanlış, {t.question_blank} boş.'
            if t.outcome_codes: text+='\nDosyada beyan edilen kazanım kodları (resmî doğrulama yok): '+', '.join(t.outcome_codes)
            if t.teacher_note: text+='\nÖğretmen notu: '+t.teacher_note
            if t.source_warning: text+='\nUyarı: '+t.source_warning
            text+='\n\n'+self._course_text
        else:
            text=self._course_text
        self.details.setPlainText(text)

    def copy_report(self):
        if self._report is None:
            QMessageBox.information(self,'Rapor','Kopyalanacak veri yok.')
            return
        QApplication.clipboard().setText(self._report.explain())

    def import_question_evidence(self):
        if not self.student_id:
            QMessageBox.information(self,'Öğrenci','Önce öğrenci seçin.')
            return
        from ui.question_evidence_import_v19 import QuestionEvidenceImportDialog
        dialog=QuestionEvidenceImportDialog(self.student_id,self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
