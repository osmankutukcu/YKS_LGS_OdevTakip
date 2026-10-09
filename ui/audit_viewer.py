# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QHeaderView, QLabel, QAbstractItemView, QWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from utils import audit_manager

class AuditLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İşlem Geçmişi (Audit Log)")
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Üst Panel: Başlık + Arama
        top = QHBoxLayout()
        
        lbl_title = QLabel("Sistem İşlem Kayıtları")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        top.addWidget(lbl_title)
        
        top.addStretch()
        
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("Ara (Kullanıcı, Detay)...")
        self.txtSearch.setFixedWidth(250)
        self.txtSearch.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: #f8fafc;
            }
        """)
        self.txtSearch.textChanged.connect(self._load_data)
        top.addWidget(self.txtSearch)

        btn_refresh = QPushButton("Yenile")
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(self._load_data)
        top.addWidget(btn_refresh)
        
        layout.addLayout(top)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Zaman", "Kullanıcı", "Kategori", "Detay"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                background-color: white;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 6px;
                border: none;
                font-weight: bold;
                color: #475569;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        
        layout.addWidget(self.table)

    def _load_data(self):
        search = self.txtSearch.text().strip()
        logs = audit_manager.get_logs(limit=300, search=search)
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(logs))
        
        for r, row in enumerate(logs):
            # ID
            self.table.setItem(r, 0, QTableWidgetItem(str(row["id"])))
            
            # Zaman (formatla)
            ts = str(row["timestamp"])
            try:
                # 2023-10-27 10:00:00... -> 27.10 10:00
                dt_part = ts.split(" ")[0]
                tm_part = ts.split(" ")[1][:5]
                year, month, day = dt_part.split("-")
                fmt = f"{day}.{month}.{year} {tm_part}"
            except:
                fmt = ts
            
            self.table.setItem(r, 1, QTableWidgetItem(fmt))
            
            # User
            u = row["username"] or "system"
            it_u = QTableWidgetItem(u)
            it_u.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 2, it_u)
            
            # Category (renkli badge gibi duralım)
            cat = row["category"] or "-"
            it_cat = QTableWidgetItem(cat)
            it_cat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Renklendirme
            fg = QColor("#334155")
            if cat == "DELETE" or "DELETE" in (row["action_type"] or ""):
                fg = QColor("#ef4444")
            elif cat == "BACKUP":
                fg = QColor("#0ea5e9")
            elif cat == "SETTINGS":
                fg = QColor("#8b5cf6")
            
            it_cat.setForeground(fg)
            font = it_cat.font()
            font.setBold(True)
            it_cat.setFont(font)
            
            self.table.setItem(r, 3, it_cat)
            
            # Detay
            det = row["details"] or ""
            # Action type'ı da detaya ekle
            act = row["action_type"] or ""
            full_txt = f"[{act}] {det}"
            
            self.table.setItem(r, 4, QTableWidgetItem(full_txt))
