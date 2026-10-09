# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, 
    QFrame, QGraphicsDropShadowEffect, QWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor, QFont

class ReportPreviewDialog(QDialog):
    def __init__(self, parent=None, report_text="", student_name="", phone=""):
        super().__init__(parent)
        self.setWindowTitle("Rapor Önizleme ve Düzenleme")
        self.resize(500, 600)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel { color: #334155; }
        """)
        
        self.final_text = report_text
        self.student_name = student_name
        self.phone = phone

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Card
        header = QFrame()
        header.setStyleSheet("""
            QFrame { 
                background-color: white; 
                border-radius: 12px; 
                border: 1px solid #e2e8f0;
            }
        """)
        h_layout = QVBoxLayout(header)
        
        lbl_title = QLabel("📝 Rapor Önizleme")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e40af; border: none;")
        
        lbl_info = QLabel(f"<b>Öğrenci:</b> {student_name}<br><b>Alıcı:</b> {phone}")
        lbl_info.setStyleSheet("font-size: 13px; color: #64748b; border: none;")
        
        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_info)
        layout.addWidget(header)

        # Preview Area
        lbl_prev = QLabel("Mesaj İçeriği (Düzenleyebilirsiniz):")
        lbl_prev.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl_prev)

        self.txt_preview = QTextEdit()
        self.txt_preview.setPlainText(report_text)
        self.txt_preview.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                color: #0f172a;
            }
            QTextEdit:focus { border: 2px solid #3b82f6; }
        """)
        layout.addWidget(self.txt_preview)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #64748b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #475569; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_send = QPushButton("✅ WhatsApp ile Gönder")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_send.clicked.connect(self._confirm_send)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_send)
        
        layout.addLayout(btn_layout)

    def _confirm_send(self):
        self.final_text = self.txt_preview.toPlainText()
        self.accept()
