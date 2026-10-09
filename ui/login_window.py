# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import hashlib
import math
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QGraphicsDropShadowEffect,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PyQt6.QtGui import QFont, QColor, QPalette, QBrush, QLinearGradient, QRadialGradient, QPainter, QPainterPath

import db
from utils import settings as appset

class ModernLoginWindow(QDialog):
    """
    Yenilenmiş Modern, Premium Giriş Ekranı.
    - Deep Space Gradient Background
    - Glassmorphism Card
    - Smooth Animations
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Giriş - YKS/LGS Asistanı")
        self.resize(1100, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Ana Container
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Arka Plan
        self.bg_widget = BackgroundWidget(self)
        layout.addWidget(self.bg_widget)

        # Kartı ortalamak için layout
        bg_layout = QVBoxLayout(self.bg_widget)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Giriş Kartı
        self.card = LoginCard(self)
        self.card.login_success.connect(self.accept)
        self.card.close_signal.connect(self.reject)
        
        bg_layout.addWidget(self.card)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos'):
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if hasattr(self, 'old_pos'):
            del self.old_pos


class BackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update)
        self.anim_timer.start(50) # Her 50ms de bir yeniden çiz (subtle animation)
        self.offset = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 1. Ana Gradient (Derin, Zengin Renkler)
        # Deep Blue -> Purple -> Slate
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#0f172a")) # Slate 900
        grad.setColorAt(0.4, QColor("#312e81")) # Indigo 900
        grad.setColorAt(1.0, QColor("#4c1d95")) # Violet 900
        
        painter.fillRect(self.rect(), grad)

        # 2. Hareketli "Mesh" Gradient veya Parçacıklar (Hafif Efekt)
        self.offset += 0.5
        if self.offset > 360: self.offset = 0
        
        # Sol üstte ışık hüzmesi
        painter.setPen(Qt.PenStyle.NoPen)
        rad_grad = QRadialGradient(w*0.2, h*0.2, w*0.5)
        rad_grad.setColorAt(0, QColor(99, 102, 241, 40)) # Indigo 500, düşük opaklık
        rad_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(rad_grad))
        painter.drawEllipse(0, 0, w, h)

        # Sağ altta ışık hüzmesi (hareketli)
        move_x = w*0.8 + math.sin(math.radians(self.offset))*20
        rad_grad2 = QRadialGradient(move_x, h*0.8, w*0.4)
        rad_grad2.setColorAt(0, QColor(236, 72, 153, 30)) # Pink 500
        rad_grad2.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(rad_grad2))
        painter.drawEllipse(int(w*0.4), int(h*0.4), int(w), int(h))

        # Grid Deseni (Tech Look)
        painter.setPen(QColor(255, 255, 255, 5))
        step = 40
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)


class LoginCard(QFrame):
    from PyQt6.QtCore import pyqtSignal
    login_success = pyqtSignal()
    close_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(420, 520)
        
        # Style
        # Glassmorphism: Yarı saydam beyaz, blur efekti (blur QGraphicsEffect ile zor performanslı olur, o yüzden opaklığı artırılmış beyaz kullanıyoruz)
        self.setStyleSheet("""
            LoginCard {
                background-color: rgba(255, 255, 255, 0.92);
                border-radius: 24px;
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
            QLabel { color: #1e293b; font-family: 'Segoe UI', sans-serif; }
            
            QLineEdit {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 12px;
                padding: 14px 16px;
                font-size: 14px;
                color: #334155;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 2px solid #6366f1; /* Indigo 500 */
                background: #ffffff;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
            
            QPushButton#btnLogin {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: 700;
                font-size: 15px;
                padding: 14px;
                letter-spacing: 0.5px;
            }
            QPushButton#btnLogin:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #6d28d9);
            }
            QPushButton#btnLogin:pressed {
                padding-top: 16px; 
            }
            
            QPushButton#btnClose {
                background: transparent;
                color: #94a3b8;
                font-size: 24px;
                font-weight: 300;
                border: none;
            }
            QPushButton#btnClose:hover { color: #ef4444; }
        """)

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 80)) # Daha derin gölge
        shadow.setOffset(0, 20)
        self.setGraphicsEffect(shadow)

        # Layout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 40)
        lay.setSpacing(16)

        # Header (Close Button)
        top_h = QHBoxLayout()
        top_h.addStretch()
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.clicked.connect(self.close_signal.emit)
        top_h.addWidget(self.btn_close)
        lay.addLayout(top_h)
        
        # Logo / Title Area
        title_v = QVBoxLayout()
        title_v.setSpacing(8)
        title_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Emoji Icon yerine güzel bir unicode karakter veya metin ikonu
        lbl_icon = QLabel("💡") # Ampul veya Şimşek ⚡
        lbl_icon.setStyleSheet("font-size: 56px;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_h1 = QLabel("HOŞ GELDİNİZ")
        lbl_h1.setStyleSheet("font-size: 26px; font-weight: 800; color: #1e293b; letter-spacing: -0.5px;")
        lbl_h1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_h2 = QLabel("YKS/LGS Asistanı v2")
        lbl_h2.setStyleSheet("font-size: 14px; font-weight: 500; color: #64748b;")
        lbl_h2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_v.addWidget(lbl_icon)
        title_v.addWidget(lbl_h1)
        title_v.addWidget(lbl_h2)
        
        lay.addLayout(title_v)
        lay.addSpacing(20)

        # Login Mode
        self.login_mode = appset.ayar_get("login_mode", "user_pass")
        
        # Inputs
        self.input_container = QVBoxLayout()
        self.input_container.setSpacing(12)
        
        self.txtUser = QLineEdit()
        self.txtUser.setPlaceholderText("Kullanıcı Adı")
        # Basit ikon efekti için placeholder veya label kullanılabilir ama CSS temiz kalsın
        
        if self.login_mode == "pass_only":
            self.txtUser.setVisible(False)
            self.txtUser.setText("system")
        else:
            self.input_container.addWidget(self.txtUser)
            
        self.txtPass = QLineEdit()
        self.txtPass.setPlaceholderText("Şifreniz")
        self.txtPass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_container.addWidget(self.txtPass)
        
        lay.addLayout(self.input_container)
        
        lay.addSpacing(10)
        
        # Button
        self.btnLogin = QPushButton("SİSTEME GİRİŞ YAP")
        self.btnLogin.setObjectName("btnLogin")
        self.btnLogin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnLogin.clicked.connect(self._handle_login)
        
        # Gölge efekti butona da verilebilir ama QFrame shadow'u tüm widget'ı etkiliyor
        
        lay.addWidget(self.btnLogin)
        lay.addStretch()
        
        # Footer / Version
        lbl_ver = QLabel("Build 2025.12.26 • Secure Access")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ver.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        lay.addWidget(lbl_ver)

        # Events
        self.txtPass.returnPressed.connect(self.btnLogin.click)
        if self.login_mode != "pass_only":
            self.txtUser.returnPressed.connect(lambda: self.txtPass.setFocus())
            
        # Basit giriş animasyonu (Scale Up)
        self.anim_timer = QTimer()
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        # Parent dialog opacity kontrolü
        if parent:
            parent.setWindowOpacity(0)
            self.fade = QPropertyAnimation(parent, b"windowOpacity")
            self.fade.setDuration(500)
            self.fade.setStartValue(0)
            self.fade.setEndValue(1)
            self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.fade.start()

    def _handle_login(self):
        user = self.txtUser.text().strip()
        pwd = self.txtPass.text().strip()

        if (self.login_mode != "pass_only" and not user) or not pwd:
            self._shake_animation()
            return

        try:
            con = db.get_conn()
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
            success = False
            
            if self.login_mode == "pass_only":
                sys_hash = appset.ayar_get("system_password_hash")
                if not sys_hash:
                    row = con.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()
                    if row: sys_hash = row[0]
                success = (pwd_hash == sys_hash)
            else:
                row = con.execute("SELECT id, role FROM users WHERE username=? AND password_hash=?", (user, pwd_hash)).fetchone()
                success = (row is not None)
            
            if success:
                self.login_success.emit()
            else:
                self._shake_animation()
                self.txtPass.clear()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"DB Hatası: {e}")

    def _shake_animation(self):
        # Basit bir titreme animasyonu
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(100)
        anim.setLoopCount(3)
        # Mevcut pozisyonu referans alarak sağ sol yapmalı ama layout içinde olduğu için visual feedback tercih ediyoruz
        # Renk değişimi
        self.setStyleSheet(self.styleSheet().replace("#e2e8f0", "#ef4444")) # Border red
        QTimer.singleShot(400, lambda: self._restore_style())

    def _restore_style(self):
        # Reset border color
        self.setStyleSheet(self.styleSheet().replace("#ef4444", "#e2e8f0"))

