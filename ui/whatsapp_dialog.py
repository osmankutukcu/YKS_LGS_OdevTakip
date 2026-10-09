# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import re
import datetime
import urllib.parse
import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTextEdit, QCheckBox, QFrame, QWidget, QSizePolicy,
    QGraphicsDropShadowEffect, QApplication, QMessageBox, QLineEdit
)
from PyQt6.QtGui import QPixmap, QColor, QFont, QCursor
from PyQt6.QtCore import Qt, QSize, QTimer

try:
    USERROLE = Qt.ItemDataRole.UserRole
except Exception:
    USERROLE = 0x0100


class WhatsAppGonderDialog(QDialog):
    """
    Modern & Profesyonel WhatsApp Gönderim ve Rapor Paneli.
    - Kurumsal WhatsApp arayüzü
    - Gerçekçi WhatsApp sohbet balonu önizlemesi (#d9fdd3)
    - Alıcı kartları, otomatik sayaçlar ve akıllı seçim
    - Hızlı tebrik ve hatırlatma şablon butonları
    - Tek tıkla panoya kopyalama ve web fallback
    """
    def __init__(
        self,
        alicilar,                    # [(etiket, tel), ...]
        mesaj,                       # başlangıç mesaj metni
        parent=None,
        header_text: str = "",       # üst bilgi (kurum/koç/iletişim…)
        header_logo_path: str | None = None,  # logo dosya yolu (opsiyonel)
        header_checked: bool = True  # "Üsttekileri mesaja ekle" varsayılanı
    ):
        super().__init__(parent)
        self.setWindowTitle("WhatsApp Bildirim & Ödev Raporu")
        self.resize(980, 640)
        self.setMinimumSize(850, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
        """)

        self._header_text = (header_text or "").strip()
        self._header_logo_path = (header_logo_path or "").strip()

        if not self._header_text:
            try:
                from utils import settings as appset
                kurum = (appset.ayar_get('kurum_adi') or '').strip()
                eg_kocu = (appset.ayar_get('egitim_kocu') or '').strip()
                ilet = (appset.ayar_get('iletisim_satiri') or '').strip()
                web = (appset.ayar_get('kurum_web') or '').strip()
                qr = (appset.ayar_get('odev_qr_link') or '').strip()
                h_lines = []
                if kurum: h_lines.append(kurum)
                if eg_kocu: h_lines.append(f"Eğitim Koçu: {eg_kocu}")
                if ilet: h_lines.append(ilet)
                if web: h_lines.append(web)
                if qr: h_lines.append(f"QR: {qr}")
                self._header_text = "\n".join(h_lines)
            except Exception:
                pass

        if not self._header_logo_path:
            try:
                from utils import settings as appset
                self._header_logo_path = (appset.ayar_get('logo_path') or '').strip()
            except Exception:
                pass

        self.ust_eklensin = bool(header_checked)
        self._raw_alicilar = alicilar or []

        # Ana layout
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        # 1. Üst Kurumsal WhatsApp Başlık Bandı
        root.addWidget(self._build_header_banner())

        # 2. Ana Gövde (Sol: Alıcılar, Sağ: Mesaj Editörü & Önizleme)
        body = QHBoxLayout()
        body.setSpacing(14)

        left_card = self._build_recipients_panel()
        right_card = self._build_message_panel(mesaj or "")

        body.addWidget(left_card, 2)
        body.addWidget(right_card, 3)
        root.addLayout(body, 1)

        # 3. Alt Eylemler Çubuğu
        root.addLayout(self._build_footer_actions())

        # Başlangıç güncellemeleri
        self._update_selection_count()
        self._update_char_count()

    # ---------------- UI PARÇALARI ----------------

    def _build_header_banner(self) -> QWidget:
        """WhatsApp kurumsal tonlarında şık üst banner."""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #075e54, stop:0.55 #128c7e, stop:1 #25d366);
                border-radius: 10px;
            }
        """)
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(12)

        icon_lbl = QLabel("💬")
        icon_lbl.setStyleSheet("font-size: 26px; background: transparent;")
        lay.addWidget(icon_lbl)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(2)
        title = QLabel("WhatsApp Bildirim & Ödev İletişim Merkezi")
        title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; background: transparent;")
        subtitle = QLabel("Öğrenci ve veli numaralarına ödev durumunu otomatik açıp yapıştırarak iletir.")
        subtitle.setStyleSheet("color: #d1fae5; font-size: 12px; background: transparent;")
        txt_col.addWidget(title)
        txt_col.addWidget(subtitle)
        lay.addLayout(txt_col, 1)

        # Otomasyon durumu rozeti
        chip = QLabel("⚡ Otomatik Gönderim Aktif")
        chip.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.2);
            color: #ffffff;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.35);
        """)
        lay.addWidget(chip)

        return banner

    def _build_recipients_panel(self) -> QFrame:
        """Sol Alıcı Listesi Kartı."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame#RecCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        card.setObjectName("RecCard")

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Başlık & Sayaç
        top = QHBoxLayout()
        lbl_head = QLabel("👥 Alıcı Listesi")
        lbl_head.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        top.addWidget(lbl_head)
        top.addStretch(1)

        self.lbl_count = QLabel("(0 Seçili)")
        self.lbl_count.setStyleSheet("""
            background-color: #eff6ff;
            color: #2563eb;
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 8px;
        """)
        top.addWidget(self.lbl_count)
        lay.addLayout(top)

        # Liste Widget
        self.lst = QListWidget()
        self.lst.setStyleSheet("""
            QListWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #fdfdfd;
                padding: 4px;
                color: #1e293b;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #f1f5f9;
                padding: 6px 4px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
            QListWidget::item:selected {
                background-color: #f0fdf4;
                color: #166534;
            }
        """)
        self.lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        for etiket, tel in self._raw_alicilar:
            # Rol analizi (Öğrenci / Veli)
            et_lower = str(etiket).lower()
            if "öğrenci" in et_lower or "ogrenci" in et_lower:
                icon_tag = "🎓"
                role_txt = "Öğrenci"
            elif "anne" in et_lower:
                icon_tag = "👩"
                role_txt = "Veli (Anne)"
            elif "baba" in et_lower:
                icon_tag = "👨"
                role_txt = "Veli (Baba)"
            else:
                icon_tag = "👨‍👩‍👦"
                role_txt = "Veli"

            tel_fmt = self._format_phone(tel)
            item_text = f"{icon_tag} {etiket}\n    📱 {tel_fmt}"
            it = QListWidgetItem(item_text)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked)
            it.setData(USERROLE, (etiket, tel))
            self.lst.addItem(it)

        self.lst.itemChanged.connect(lambda _: self._update_selection_count())
        lay.addWidget(self.lst, 1)

        # Seçim Butonları
        b_box = QHBoxLayout()
        b_all = QPushButton("✅ Tümünü Seç")
        b_clr = QPushButton("❌ Hiçbiri")
        for b in (b_all, b_clr):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 5px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    border-color: #94a3b8;
                }
            """)
        b_all.clicked.connect(lambda: self._set_all(True))
        b_clr.clicked.connect(lambda: self._set_all(False))
        b_box.addWidget(b_all)
        b_box.addWidget(b_clr)
        lay.addLayout(b_box)

        # Gölge
        self._apply_shadow(card)
        return card

    def _build_message_panel(self, init_msg: str) -> QFrame:
        """Sağ Mesaj Editörü ve WhatsApp Önizleme Kartı."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame#MsgCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        card.setObjectName("MsgCard")

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # 1. Kurumsal Başlık Önizleme (Sadece doluysa göster)
        has_header_content = bool(self._header_text or self._header_logo_path)
        self.header_card = QFrame()
        self.header_card.setStyleSheet("""
            QFrame {
                background-color: #f0fdf4;
                border-radius: 8px;
                border: 1px solid #bbf7d0;
            }
        """)
        h_lay = QHBoxLayout(self.header_card)
        h_lay.setContentsMargins(10, 8, 10, 8)
        h_lay.setSpacing(10)

        self.lblLogo = QLabel()
        self.lblLogo.setFixedSize(48, 48)
        self.lblLogo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo(self._header_logo_path)
        h_lay.addWidget(self.lblLogo)

        self.txtHeaderPreview = QTextEdit()
        self.txtHeaderPreview.setReadOnly(True)
        self.txtHeaderPreview.setFrameShape(QFrame.Shape.NoFrame)
        self.txtHeaderPreview.setStyleSheet("background: transparent; border: none; color: #166534; font-size: 12px;")
        self.txtHeaderPreview.setPlainText(self._header_text)
        self.txtHeaderPreview.setMaximumHeight(55)
        h_lay.addWidget(self.txtHeaderPreview, 1)

        # İçerik yoksa boş kutu göstermemek için gizle
        self.header_card.setVisible(has_header_content)
        lay.addWidget(self.header_card)

        # Checkbox (Kurumsal Başlık)
        self.chkHeader = QCheckBox("Kurumsal üst bilgiyi ve logoyu mesaja ekle")
        self.chkHeader.setChecked(self.ust_eklensin)
        self.chkHeader.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500;")
        self.chkHeader.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chkHeader.toggled.connect(self._on_header_toggled)
        lay.addWidget(self.chkHeader)

        # 2. Hızlı Şablon Araç Çubuğu
        tools = QHBoxLayout()
        tools.setSpacing(6)
        tools_lbl = QLabel("Hızlı Ekle:")
        tools_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        tools.addWidget(tools_lbl)

        btnTebrik = QPushButton("🌟 Tebrik & Takdir")
        btnTebrik.setToolTip("Mesajın sonuna tebrik ve motivasyon notu ekler.")
        btnHatirlatma = QPushButton("⚠️ Telafi Hatırlatması")
        btnHatirlatma.setToolTip("Mesajın sonuna eksik/aktarılan ödevler için nazik takip notu ekler.")
        btnCopyMsg = QPushButton("📋 Panoya Al")
        btnCopyMsg.setToolTip("Mevcut mesaj metnini panoya kopyalar.")

        for b in (btnTebrik, btnHatirlatma, btnCopyMsg):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    color: #0f172a;
                }
            """)

        btnTebrik.clicked.connect(lambda: self._append_template("tebrik"))
        btnHatirlatma.clicked.connect(lambda: self._append_template("hatirlatma"))
        btnCopyMsg.clicked.connect(self._copy_to_clipboard)

        tools.addWidget(btnTebrik)
        tools.addWidget(btnHatirlatma)
        tools.addWidget(btnCopyMsg)
        tools.addStretch(1)
        lay.addLayout(tools)

        # 3. Mesaj Düzenleme Alanı (WhatsApp Sohbet Balonu Estetiğinde)
        msg_wrapper = QFrame()
        msg_wrapper.setStyleSheet("""
            QFrame {
                background-color: #efeae2;
                border: 1px solid #dcd7ce;
                border-radius: 10px;
            }
        """)
        wrap_lay = QVBoxLayout(msg_wrapper)
        wrap_lay.setContentsMargins(10, 10, 10, 8)
        wrap_lay.setSpacing(4)

        self.txtMsg = QTextEdit()
        self.txtMsg.setPlaceholderText("WhatsApp mesajınızı buraya yazın veya düzenleyin...")
        self.txtMsg.setPlainText(init_msg)
        self.txtMsg.setStyleSheet("""
            QTextEdit {
                background-color: #d9fdd3;
                border: 1px solid #bbf7d0;
                border-radius: 10px;
                padding: 10px 12px;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 13px;
                line-height: 1.4;
                color: #111827;
                outline: none;
            }
            QTextEdit:focus {
                border: 1.5px solid #22c55e;
                background-color: #d1fae5;
            }
        """)
        self.txtMsg.textChanged.connect(self._update_char_count)
        wrap_lay.addWidget(self.txtMsg, 1)

        # Balon içi alt bilgi (Zaman simülasyonu + çift mavi tik)
        bubble_footer = QHBoxLayout()
        now_str = datetime.datetime.now().strftime("%H:%M")
        lbl_status = QLabel(f"Bugün {now_str} <span style='color:#53bdeb; font-weight:bold;'>✓✓</span>")
        lbl_status.setTextFormat(Qt.TextFormat.RichText)
        lbl_status.setStyleSheet("font-size: 11px; color: #64748b; background: transparent;")
        bubble_footer.addStretch(1)
        bubble_footer.addWidget(lbl_status)
        wrap_lay.addLayout(bubble_footer)

        lay.addWidget(msg_wrapper, 1)

        # 4. Sayaç Bandı
        self.lbl_char_stat = QLabel("📝 0 karakter • 0 satır")
        self.lbl_char_stat.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        lay.addWidget(self.lbl_char_stat)

        # Gölge
        self._apply_shadow(card)
        return card

    def _build_footer_actions(self) -> QHBoxLayout:
        """Alt Eylemler: Kopyala, Web Fallback, İptal ve Gönder."""
        footer = QHBoxLayout()
        footer.setSpacing(10)

        # Sol Butonlar (Kopyala & Web Fallback)
        self.btnCopy = QPushButton("📋 Metni Kopyala")
        self.btnCopy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnCopy.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """)
        self.btnCopy.clicked.connect(self._copy_to_clipboard)
        footer.addWidget(self.btnCopy)

        self.btnWeb = QPushButton("🌐 Web'de Aç")
        self.btnWeb.setToolTip("İlk seçili numara için web.whatsapp.com üzerinden sohbeti açar.")
        self.btnWeb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnWeb.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0284c7;
                border: 1px solid #bae6fd;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f0f9ff;
                border-color: #7dd3fc;
            }
        """)
        self.btnWeb.clicked.connect(self._open_web_whatsapp)
        footer.addWidget(self.btnWeb)

        footer.addStretch(1)

        # Sağ Butonlar (İptal & Gönder)
        btnCancel = QPushButton("İptal")
        btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btnCancel.setFixedSize(110, 40)
        btnCancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #64748b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                color: #1e293b;
                border-color: #94a3b8;
            }
        """)
        btnCancel.clicked.connect(self.reject)
        footer.addWidget(btnCancel)

        self.btnSend = QPushButton("🚀 WhatsApp ile Gönder")
        self.btnSend.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnSend.setMinimumWidth(210)
        self.btnSend.setFixedHeight(40)
        self.btnSend.setToolTip("WhatsApp uygulamasını otomatik olarak açar, mesajı yapıştırır ve Enter tuşuyla gönderir.")
        self.btnSend.setStyleSheet("""
            QPushButton {
                background-color: #25d366;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #128c7e;
            }
            QPushButton:pressed {
                background-color: #075e54;
            }
        """)
        self.btnSend.clicked.connect(self._on_send_clicked)
        footer.addWidget(self.btnSend)

        return footer

    # ---------------- YARDIMCILAR & AKSİYONLAR ----------------

    def _set_all(self, on: bool):
        st = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if it:
                it.setCheckState(st)
        self._update_selection_count()

    def _update_selection_count(self):
        sel = 0
        total = self.lst.count()
        for i in range(total):
            it = self.lst.item(i)
            if it and it.checkState() == Qt.CheckState.Checked:
                sel += 1
        self.lbl_count.setText(f"({sel} / {total} Seçili)")

    def _update_char_count(self):
        txt = self.txtMsg.toPlainText() or ""
        chars = len(txt)
        lines = len(txt.splitlines()) if txt else 0
        self.lbl_char_stat.setText(f"📝 {chars} karakter • {lines} satır")

    def _on_header_toggled(self, state: bool):
        self.ust_eklensin = bool(state)
        if bool(self._header_text or self._header_logo_path):
            self.header_card.setVisible(self.ust_eklensin)

    def _append_template(self, kind: str):
        current = self.txtMsg.toPlainText().strip()
        if kind == "tebrik":
            note = "🌟 *Tebrikler!* Verilen tüm ödevleri başarıyla ve zamanında tamamladın. Disiplinli çalışmanı takdir ediyor, başarılarının devamını diliyoruz."
        elif kind == "hatirlatma":
            note = "📌 *Önemli Hatırlatma:* Kalan ve aktarılan ödevlerini bir sonraki kontrol randevumuza kadar eksiksiz tamamlamanı rica ederiz."
        else:
            return

        if note in current:
            return
        new_text = f"{current}\n\n{note}" if current else note
        self.txtMsg.setPlainText(new_text)

    def _copy_to_clipboard(self):
        full_msg = self.mesaj()
        if not full_msg:
            return
        cb = QApplication.clipboard()
        if cb:
            cb.setText(full_msg)
        self.btnCopy.setText("✅ Kopyalandı!")
        QTimer.singleShot(1500, lambda: self.btnCopy.setText("📋 Metni Kopyala"))

    def _open_web_whatsapp(self):
        secili = self.secili_alicilar()
        if not secili:
            QMessageBox.warning(self, "Alıcı Seçilmedi", "Lütfen önce en az bir alıcı seçin.")
            return
        num = re.sub(r"\D", "", secili[0])
        if len(num) == 10 and num.startswith("5"):
            num = "90" + num
        elif len(num) == 11 and num.startswith("05"):
            num = "90" + num[1:]
        text_encoded = urllib.parse.quote(self.mesaj())
        url = f"https://web.whatsapp.com/send?phone={num}&text={text_encoded}"
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tarayıcı açılamadı:\n{e}")

    def _on_send_clicked(self):
        if not self.secili_alicilar():
            QMessageBox.warning(self, "Uyarı", "Lütfen mesajın gönderileceği en az bir alıcı işaretleyin.")
            return
        if not self.mesaj().strip():
            QMessageBox.warning(self, "Uyarı", "Mesaj içeriği boş bırakılamaz.")
            return
        self.accept()

    def _format_phone(self, raw_tel: str) -> str:
        s = re.sub(r"\D", "", str(raw_tel or ""))
        if len(s) == 10 and s.startswith("5"):
            return f"0({s[:3]}) {s[3:6]} {s[6:8]} {s[8:]}"
        if len(s) == 11 and s.startswith("05"):
            return f"0({s[1:4]}) {s[4:7]} {s[7:9]} {s[9:]}"
        return raw_tel or ""

    def _load_logo(self, path: str):
        if not path or not os.path.exists(path):
            self.lblLogo.setPixmap(QPixmap())
            self.lblLogo.setVisible(False)
            return
        try:
            pm = QPixmap(path)
            if not pm.isNull():
                self.lblLogo.setVisible(True)
                self.lblLogo.setPixmap(pm.scaled(
                    self.lblLogo.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self.lblLogo.setVisible(False)
        except Exception:
            self.lblLogo.setVisible(False)

    def _apply_shadow(self, widget: QWidget):
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(14)
        sh.setColor(QColor(0, 0, 0, 12))
        sh.setOffset(0, 2)
        widget.setGraphicsEffect(sh)

    # -------- Public API (Mevcut kodla %100 uyumlu) --------

    def secili_alicilar(self) -> list[str]:
        out = []
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if it and it.checkState() == Qt.CheckState.Checked:
                data = it.data(USERROLE)
                if data and isinstance(data, (list, tuple)) and len(data) >= 2:
                    out.append(str(data[1]))
                elif isinstance(data, str):
                    out.append(data)
                elif data:
                    out.append(str(data))
        return out

    def mesaj(self) -> str:
        body = (self.txtMsg.toPlainText() or "").strip()
        if self.ust_eklensin and self._header_text:
            if self._header_text not in body:
                return f"{body}\n\n---\n{self._header_text}\n---" if body else self._header_text
        return body

