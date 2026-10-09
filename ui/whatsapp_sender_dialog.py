from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QCheckBox, QTextEdit, QLabel, QWidget, QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QTextCursor
try:
    from utils import settings as appset
    from utils import whatsapp
except ImportError:
    import sys
    # utils modülünü bulamazsa diye path ekleme denemesi
    sys.path.append("..") 
from ui.whatsapp_dialog import WhatsAppGonderDialog

class _OldWhatsAppGonderDialog(QDialog):
    """
    - Sol: Alıcı listesi (çoklu seçim, hepsini seç/temizle)
    - Sağ: Üstte kurum/logo/koç/iletişim/web/QR başlık paneli (görsel)
           Altta mesaj editörü
           Alt butonlar: Gönder / İptal
    - Üstteki bilgileri mesaja ekle kutusu: İşaretlenirse ayarlardan gelen
      kurum/koç/iletişim/web/QR bilgileri metnin sonuna blok olarak eklenir/çıkarılır.
    """

    def __init__(self, alicilar: list[tuple[str, str]], mesaj: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhatsAppile Gönder")
        self.resize(920, 600)

        # Footer yönetimi
        self._footer_added = False  # blok şu an metinde mi?
        self._footer_block = self._build_footer_block()  # ayarlardan blok metni

        root = QHBoxLayout(self)

        # -------- Sol panel: Alıcılar --------
        left = QVBoxLayout()
        gb_left = QGroupBox("Alıcılar")
        gb_left.setLayout(left)

        self.lst = QListWidget()
        self.lst.setMinimumWidth(260)
        for ad, num in (alicilar or []):
            it = QListWidgetItem(f"{ad}  ({num})")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked)  # varsayılan: seçili
            it.setData(Qt.ItemDataRole.UserRole, num)
            self.lst.addItem(it)

        btn_all = QPushButton("Hepsini Seç")
        btn_none = QPushButton("Seçimi Temizle")
        btn_all.clicked.connect(lambda: self._select_all(True))
        btn_none.clicked.connect(lambda: self._select_all(False))

        left.addWidget(self.lst, 1)
        row = QHBoxLayout()
        row.addWidget(btn_all)
        row.addWidget(btn_none)
        row.addStretch(1)
        left.addLayout(row)
        root.addWidget(gb_left, 0)

        # -------- Sağ panel: Header + Editor --------
        right = QVBoxLayout()

        # Üst bilgi paneli (görsel)
        header = self._build_header_widget()
        right.addWidget(header)

        # Üstteki bilgileri mesaja ekle
        self.chkAppend = QCheckBox("Üstteki bilgileri mesaja ekle")
        self.chkAppend.toggled.connect(self._toggle_footer_block)
        right.addWidget(self.chkAppend)

        # Mesaj editörü
        self.txt = QTextEdit()
        self.txt.setPlainText(mesaj or "")
        self.txt.setPlaceholderText("WhatsApp mesajı…")
        right.addWidget(self.txt, 1)

        # Alt butonlar
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btnCancel = QPushButton("İptal")
        self.btnSend = QPushButton("Gönder")
        btnCancel.clicked.connect(self.reject)
        self.btnSend.clicked.connect(self._action_send)
        buttons.addWidget(btnCancel)
        buttons.addWidget(self.btnSend)
        right.addLayout(buttons)

        # Durum bilgisi
        self.lblStatus = QLabel("")
        self.lblStatus.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lblStatus.setStyleSheet("color: #64748B; font-size: 11px;")
        right.addWidget(self.lblStatus)

        # Sağ paneli kutuya al
        gb_right = QGroupBox("Mesaj")
        gb_right.setLayout(right)
        root.addWidget(gb_right, 1)

        # Modal olsun, ESC ile kapanabilsin
        self.setModal(True)

        # __init__ sonunda: otomatik ekle (varsa)
        self.chkAppend.setChecked(True)

    # ---------- Public API ----------
    def secili_alicilar(self) -> list[str]:
        nums: list[str] = []
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                n = it.data(Qt.ItemDataRole.UserRole)
                if n:
                    nums.append(str(n))
        return nums

    def mesaj(self) -> str:
        return self.txt.toPlainText().strip()

    # ---------- Helpers ----------
    def _select_all(self, state: bool):
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            it.setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)

    def _build_header_widget(self) -> QWidget:
        """
        Üst görsel panel: logo + kurum + koç + iletişim + web + QR
        Ayarlar boşsa kullanıcıya yönlendirici ipucu gösterir.
        """
        wrap = QGroupBox("Üst Bilgiler (önizleme)")
        grid = QGridLayout(wrap)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        # Ayarlar
        kurum = (appset.ayar_get('kurum_adi') or '').strip()
        eg_kocu = (appset.ayar_get('egitim_kocu') or '').strip()
        ilet = (appset.ayar_get('iletisim_satiri') or '').strip()
        web = (appset.ayar_get('kurum_web') or '').strip()
        qr = (appset.ayar_get('odev_qr_link') or '').strip()
        logo = (appset.ayar_get('logo_path') or '').strip()
        align = (appset.ayar_get('logo_align', 'left') or 'left').strip().lower()

        # Logo
        lblLogo = QLabel()
        lblLogo.setFixedSize(QSize(80, 80))
        lblLogo.setStyleSheet("border:1px solid #ddd; background:#fff;")
        if logo:
            try:
                pm = QPixmap(logo)
                if not pm.isNull():
                    pm = pm.scaled(lblLogo.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                    lblLogo.setPixmap(pm)
                else:
                    lblLogo.setText("Logo\nYok")
                    lblLogo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            except Exception:
                lblLogo.setText("Logo\nHata")
                lblLogo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            lblLogo.setText("Logo\nYok")
            lblLogo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Bilgi etiketleri
        def _lbl(txt: str, bold: bool = False, link: bool = False) -> QLabel:
            lab = QLabel(txt)
            if bold:
                lab.setStyleSheet("font-weight:600;")
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if link and txt:
                lab.setText(f'<a href="{txt}">{txt}</a>')
                lab.setOpenExternalLinks(True)
            return lab

        # Bilgi sütunu
        infoCol = QVBoxLayout()
        if kurum:   infoCol.addWidget(_lbl(kurum, bold=True))
        if eg_kocu: infoCol.addWidget(_lbl(f"Eğitim Koçu: {eg_kocu}"))
        if ilet:    infoCol.addWidget(_lbl(ilet))
        if web:     infoCol.addWidget(_lbl(web, link=True))
        if qr:      infoCol.addWidget(_lbl(f"QR: {qr}", link=True))

        infoWrap = QWidget()
        infoWrap.setLayout(infoCol)

        # Yerleşim: hizaya göre logo solda/sağda
        if align == "right":
            grid.addWidget(infoWrap, 0, 0, 2, 1)
            grid.addWidget(lblLogo, 0, 1, 2, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            grid.addWidget(lblLogo, 0, 0, 2, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            grid.addWidget(infoWrap, 0, 1, 2, 1)

        # Panelin boş görünmesini engelle
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        wrap.setMinimumHeight(110)  # görünür dursun
        wrap.setStyleSheet(
            "QGroupBox{border:1px solid #d0d5dd; border-radius:6px; margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin: margin; left:10px; padding:0 4px;}"
        )

        # Ayarlar tamamen boşsa kullanıcıyı bilgilendir
        if not any([kurum, eg_kocu, ilet, web, qr, logo]):
            hint = QLabel(
                "Ayarlar > PDF Ayarları bölümünden kurum adı, logo, koç, iletişim ve web/QR bilgilerini doldurun.")
            hint.setStyleSheet("color:#6b7280;")
            infoCol.addWidget(hint)

        return wrap

    def _build_footer_block(self) -> str:
        """
        Ayarlardaki bilgileri tek bir 'footer' blok olarak hazırlar.
        Bu blok, 'Üstteki bilgileri mesaja ekle' seçiliyken metne eklenir.
        """
        kurum = (appset.ayar_get('kurum_adi') or '').strip()
        eg_kocu = (appset.ayar_get('egitim_kocu') or '').strip()
        ilet = (appset.ayar_get('iletisim_satiri') or '').strip()
        web = (appset.ayar_get('kurum_web') or '').strip()
        qr = (appset.ayar_get('odev_qr_link') or '').strip()

        lines: list[str] = []
        if kurum:   lines.append(kurum)
        if eg_kocu: lines.append(f"Eğitim Koçu: {eg_kocu}")
        if ilet:    lines.append(ilet)
        if web:     lines.append(web)
        if qr:      lines.append(f"QR: {qr}")

        if not lines:
            return ""  # eklenecek veri yok

        # Metin içinde ayırt edilebilir sınırlar
        block = "\n---\n" + "\n".join(lines) + "\n---"
        return block

    def _toggle_footer_block(self, checked: bool):
        """
        Metin alanında footer bloğunu ekle/çıkar.
        Yinelenmeyi engeller, kaldırırken iz bırakmaz.
        """
        if not self._footer_block:
            return  # eklenecek veri yok

        txt = self.txt.toPlainText()

        if checked and not self._footer_added:
            if self._footer_block not in txt:
                # önce mevcut metnin sonunda tek boş satır bırak
                if not txt.endswith("\n"):
                    txt += "\n"
                txt += ("\n" + self._footer_block.strip() + "\n")
            self._footer_added = True
            self.txt.setPlainText(txt)
            # İmleci sona taşı
            self.txt.moveCursor(QTextCursor.MoveOperation.End)

        elif (not checked) and self._footer_added:
            # bloğu olduğu gibi temizle
            txt = txt.replace(self._footer_block, "")
            # artan fazla boşlukları toparla
            while "\n\n\n" in txt:
                txt = txt.replace("\n\n\n", "\n\n")
            txt = txt.strip() + "\n" if txt.strip() else ""
            self._footer_added = False
            self.txt.setPlainText(txt)
            self.txt.moveCursor(QTextCursor.MoveOperation.End)

    def _action_send(self):
        """
        Gönder butonuna basıldığında çalışır.
        """
        targets = self.secili_alicilar()
        msg = self.mesaj()
        
        if not targets:
            self.lblStatus.setText("⚠️ Lütfen en az bir alıcı seçin.")
            return
        
        if not msg:
            self.lblStatus.setText("⚠️ Mesaj içeriği boş olamaz.")
            return

        self.btnSend.setEnabled(False)
        self.lblStatus.setText("🚀 WhatsApp açılıyor, lütfen bekleyin...")
        self.repaint() # UI güncelle

        try:
            # WhatsApp modülünü kullanarak gönderim yap
            # whatsapp_gonder(numaralar: list, mesaj: str, ogrenci_id=None, time_delay=None)
            res = whatsapp.whatsapp_gonder(
                numaralar=targets,
                mesaj=msg
            )
            
            sent = res.get("gonderilen", 0)
            fail = len(res.get("fail", []))
            
            if sent > 0:
                self.lblStatus.setText(f"✅ {sent} kişiye gönderildi. (Hata: {fail})")
                # Başarılı ise pencereyi kapat (biraz bekleyip)
                # QTimer.singleShot(1500, self.accept) yapabiliriz ama kullanıcı sonucu görsün
                # Biz direkt kapatalım, ana ekran sonucu queue'dan takip edebilir.
                import time
                time.sleep(1)
                self.accept()
            else:
                self.btnSend.setEnabled(True)
                self.lblStatus.setText(f"❌ Gönderim başarısız oldu. (Hata: {fail})")

        except Exception as e:
            self.btnSend.setEnabled(True)
            self.lblStatus.setText(f"Hata: {str(e)}")
