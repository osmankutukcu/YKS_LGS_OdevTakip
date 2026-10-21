# -*- coding: utf-8 -*-
"""V3.5.80+ Weekly Calendar Export & Autopilot WhatsApp Dispatch Service.

Allows coaches and teachers to:
1. Save the weekly calendar directly to disk as high-resolution A4 landscape PDF.
2. Send the weekly plan PDF directly to student and parents via WhatsApp in autopilot mode
   (Desktop or Web) without manual message typing or manual clicking.
3. Automatically embeds coach/counselor name from settings ('egitim_kocu').
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QDate, QMarginsF, Qt
from PyQt6.QtGui import QCursor, QFont, QIcon, QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import db
from utils import settings as appset


def _get_coach_name() -> str:
    try:
        return str(appset.ayar_get("egitim_kocu", "") or "").strip()
    except Exception:
        return ""


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", str(name).strip())
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "Ogrenci"


def export_html_to_pdf_file(html_content: str, output_path: str) -> str:
    """Exports the given HTML string to an A4 landscape PDF at output_path."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    printer.setPageMargins(QMarginsF(5, 5, 5, 5), QPageLayout.Unit.Millimeter)
    printer.setOutputFileName(output_path)

    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    doc.setHtml(html_content)
    doc.print(printer)
    return output_path


def save_weekly_calendar_pdf_file(
    html_content: str,
    student_name: str,
    target_path: Optional[str] = None,
    parent: Optional[QWidget] = None,
) -> Optional[str]:
    """Saves the weekly calendar as PDF, prompting with QFileDialog if target_path is omitted."""
    if not target_path:
        default_dir = os.path.expanduser("~/Documents")
        if not os.path.isdir(default_dir):
            default_dir = os.path.expanduser("~/Desktop")
        date_str = datetime.date.today().strftime("%Y_%m_%d")
        safe_name = _sanitize_filename(student_name)
        suggested_name = f"{safe_name}_Haftalik_Calisma_Plani_{date_str}.pdf"
        default_file = os.path.join(default_dir, suggested_name)

        path, _ = QFileDialog.getSaveFileName(
            parent,
            "Haftalık Çalışma Planını PDF Olarak Kaydet",
            default_file,
            "PDF Dosyaları (*.pdf)",
        )
        if not path:
            return None
        target_path = path

    try:
        export_html_to_pdf_file(html_content, target_path)

        box = QMessageBox(parent)
        box.setWindowTitle("PDF Kaydedildi")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"<b>Haftalık Çalışma Planı başarıyla kaydedildi:</b><br/>{target_path}")
        btn_open = box.addButton("Dosyayı Aç", QMessageBox.ButtonRole.ActionRole)
        btn_folder = box.addButton("Klasörü Göster", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_open:
            if sys.platform == "darwin":
                subprocess.run(["open", target_path], check=False)
            elif sys.platform == "win32":
                os.startfile(target_path)
            else:
                subprocess.run(["xdg-open", target_path], check=False)
        elif clicked == btn_folder:
            folder = os.path.dirname(os.path.abspath(target_path))
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", target_path], check=False)
            elif sys.platform == "win32":
                subprocess.run(f'explorer /select,"{os.path.abspath(target_path)}"', shell=True)
            else:
                subprocess.run(["xdg-open", folder], check=False)

        return target_path
    except Exception as e:
        if parent:
            QMessageBox.critical(parent, "PDF Kayıt Hatası", f"PDF kaydedilirken hata oluştu:\n{e}")
        return None


def get_student_contacts(student_id: Optional[int]) -> List[Tuple[str, str, str]]:
    """Returns list of (label, phone, recipient_name) for the student and parents."""
    contacts = []
    if not student_id:
        return contacts
    try:
        con = db.get_conn()
        row = con.execute(
            "SELECT id, ad, soyad, ogr_tel, veli_ad, veli_yakinlik, veli_tel1, veli_tel2 FROM ogrenci WHERE id=?",
            (int(student_id),),
        ).fetchone()
        if not row:
            return contacts

        s_name = f"{row['ad']} {row['soyad']}".strip()
        v_name = (row["veli_ad"] or "Veli").strip()
        v_yak = (row["veli_yakinlik"] or "").strip()
        v_label_extra = f" ({v_yak})" if v_yak else ""

        if row["ogr_tel"] and str(row["ogr_tel"]).strip():
            contacts.append((f"Öğrenci ({s_name})", str(row["ogr_tel"]).strip(), s_name))
        if row["veli_tel1"] and str(row["veli_tel1"]).strip():
            contacts.append((f"Veli 1 ({v_name}{v_label_extra})", str(row["veli_tel1"]).strip(), v_name))
        if row["veli_tel2"] and str(row["veli_tel2"]).strip():
            contacts.append((f"Veli 2", str(row["veli_tel2"]).strip(), "Veli 2"))
    except Exception:
        pass
    return contacts


def normalize_phone_number(raw: str) -> Optional[str]:
    """Cleans and standardizes phone number for Turkish standard (905xxxxxxxxx)."""
    if not raw:
        return None
    s = "".join(filter(str.isdigit, str(raw)))
    if len(s) == 10 and s.startswith("5"):
        return "90" + s
    if len(s) == 11 and s.startswith("05"):
        return "9" + s
    if len(s) == 12 and s.startswith("905"):
        return s
    if len(s) >= 10:
        return s
    return None


class WeeklyPlanWhatsAppDialog(QDialog):
    """Modern dialog to dispatch weekly plan PDF via WhatsApp Autopilot."""

    def __init__(
        self,
        parent: Optional[QWidget],
        student_id: Optional[int],
        student_name: str,
        pdf_path: str,
    ):
        super().__init__(parent)
        self.student_id = student_id
        self.student_name = student_name
        self.pdf_path = pdf_path
        self.coach_name = _get_coach_name()

        self.setWindowTitle("📱 Haftalık Planı WhatsApp ile Gönder (Otopilot)")
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
        """)

        self.contacts = get_student_contacts(student_id)
        self.contact_checks: List[Tuple[QCheckBox, str, str]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        # Header
        head = QHBoxLayout()
        head.setSpacing(12)
        badge = QLabel("📱")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-size: 22px;
                border-radius: 10px;
            }
        """)
        head.addWidget(badge)

        t_col = QVBoxLayout()
        t_col.setSpacing(2)
        t_lbl = QLabel("Haftalık Çalışma Planı — WhatsApp Gönderimi")
        t_lbl.setStyleSheet("font-size: 14.5px; font-weight: 700; color: #0f172a;")
        d_lbl = QLabel(f"Öğrenci: <b>{self.student_name}</b> için hazırlanan PDF otopilot ile iletilecek.")
        d_lbl.setStyleSheet("font-size: 11.5px; color: #64748b;")
        t_col.addWidget(t_lbl)
        t_col.addWidget(d_lbl)
        head.addLayout(t_col, 1)
        root.addLayout(head)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("border: none; background-color: #f1f5f9; height: 1px;")
        root.addWidget(div)

        # 1. Alıcı Seçimi
        lbl_rec = QLabel("1. Gönderilecek Alıcılar:")
        lbl_rec.setStyleSheet("font-weight: 700; font-size: 12px; color: #1e293b;")
        root.addWidget(lbl_rec)

        rec_box = QFrame()
        rec_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px;")
        rec_lay = QVBoxLayout(rec_box)
        rec_lay.setContentsMargins(8, 6, 8, 6)
        rec_lay.setSpacing(6)

        if not self.contacts:
            lbl_no = QLabel("⚠️ Öğrenci veya veli için kayıtlı telefon numarası bulunamadı.")
            lbl_no.setStyleSheet("color: #b91c1c; font-size: 11.5px; font-weight: 600;")
            rec_lay.addWidget(lbl_no)
        else:
            for label, phone, r_name in self.contacts:
                chk = QCheckBox(f"{label}:  {phone}")
                chk.setChecked(True)
                chk.setStyleSheet("font-size: 12px; font-weight: 600; color: #334155;")
                chk.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                rec_lay.addWidget(chk)
                self.contact_checks.append((chk, phone, r_name))

        root.addWidget(rec_box)

        # 2. Gönderim Yolu
        lbl_mode = QLabel("2. WhatsApp Gönderim Tercihi:")
        lbl_mode.setStyleSheet("font-weight: 700; font-size: 12px; color: #1e293b;")
        root.addWidget(lbl_mode)

        mode_box = QFrame()
        mode_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        m_lay = QHBoxLayout(mode_box)
        m_lay.setContentsMargins(12, 8, 12, 8)
        m_lay.setSpacing(14)

        self.rb_desktop = QRadioButton("Masaüstü WhatsApp (Otopilot)")
        self.rb_desktop.setChecked(True)
        self.rb_desktop.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rb_desktop.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #1e293b;")

        self.rb_web = QRadioButton("WhatsApp Web (Tarayıcı)")
        self.rb_web.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rb_web.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #1e293b;")

        m_group = QButtonGroup(self)
        m_group.addButton(self.rb_desktop)
        m_group.addButton(self.rb_web)

        m_lay.addWidget(self.rb_desktop)
        m_lay.addWidget(self.rb_web)
        root.addWidget(mode_box)

        # 3. Mesaj İçeriği
        lbl_msg = QLabel("3. Mesaj Metni:")
        lbl_msg.setStyleSheet("font-weight: 700; font-size: 12px; color: #1e293b;")
        root.addWidget(lbl_msg)

        today_str = datetime.date.today().strftime("%d.%m.%Y")
        koc_part = f"\n\nEğitim Koçu / Rehberlik: {self.coach_name}" if self.coach_name else ""
        default_msg = (
            f"Sayın Velimiz / Sevgili {self.student_name},\n\n"
            f"{self.student_name} için hazırlanan {today_str} tarihli Haftalık Çalışma Programı ve Akıllı Takvim Planı "
            f"PDF olarak ekte yer almaktadır.\n\n"
            f"Başarılı, verimli ve disiplinli bir hafta dileriz! 🎯{koc_part}"
        )
        self.txt_message = QTextEdit()
        self.txt_message.setPlainText(default_msg)
        self.txt_message.setFixedHeight(95)
        self.txt_message.setStyleSheet("""
            QTextEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11.5px;
                color: #1e293b;
            }
        """)
        root.addWidget(self.txt_message)

        # PDF Dosya Bilgisi Rozeti
        file_pill = QFrame()
        file_pill.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px;")
        f_lay = QHBoxLayout(file_pill)
        f_lay.setContentsMargins(8, 5, 8, 5)
        lbl_pdf_info = QLabel(f"📄 Ekli Belge: {os.path.basename(self.pdf_path)}")
        lbl_pdf_info.setStyleSheet("font-size: 11px; font-weight: 600; color: #1e40af;")
        f_lay.addWidget(lbl_pdf_info)
        f_lay.addStretch(1)
        lbl_ready = QLabel("✓ Hazır")
        lbl_ready.setStyleSheet("font-size: 11px; font-weight: 700; color: #16a34a;")
        f_lay.addWidget(lbl_ready)
        root.addWidget(file_pill)

        # Actions Footer
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 4, 0, 0)
        btn_bar.setSpacing(10)
        btn_bar.addStretch(1)

        self.btn_cancel = QPushButton("Vazgeç")
        self.btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                color: #475569;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_send = QPushButton("🚀 Otopilot ile Gönder")
        self.btn_send.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_send.setStyleSheet("""
            QPushButton {
                padding: 8px 24px;
                background-color: #059669;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_send.clicked.connect(self._do_send)
        btn_bar.addWidget(self.btn_send)

        root.addLayout(btn_bar)

    def _do_send(self):
        selected_numbers = [
            (phone, r_name)
            for chk, phone, r_name in self.contact_checks
            if chk.isChecked()
        ]
        if not selected_numbers:
            QMessageBox.warning(self, "Alıcı Yok", "Lütfen en az bir telefon numarası seçin.")
            return

        msg_text = self.txt_message.toPlainText().strip()
        use_desktop = self.rb_desktop.isChecked()

        # macOS: Otopilot tuş basımı için Erişilebilirlik izni ön kontrolü.
        # İzin yoksa sahte "gönderildi" demek yerine kullanıcıyı doğru yönlendir.
        if use_desktop and sys.platform == "darwin":
            ax_ok, ax_err = _mac_accessibility_ok()
            if not ax_ok:
                self._handle_missing_accessibility(selected_numbers, msg_text, ax_err)
                return

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Gönderiliyor...")

        try:
            import time
            results: List[Dict[str, Any]] = []
            for phone, r_name in selected_numbers:
                clean = normalize_phone_number(phone)
                if not clean:
                    results.append({"name": r_name, "text_sent": False, "pdf_sent": False,
                                    "error": "Geçersiz telefon numarası", "permission": False})
                    continue

                if use_desktop:
                    res = _dispatch_desktop_autopilot(clean, msg_text, self.pdf_path, self.student_id)
                else:
                    res = _dispatch_web_autopilot(clean, msg_text, self.pdf_path, self.student_id)
                res["name"] = r_name
                results.append(res)
                if res.get("permission"):
                    break  # izin yoksa diğer alıcılarda da başarısız olur
                if len(selected_numbers) > 1:
                    time.sleep(2.0)

            self._report_results(results, use_desktop)
        except Exception as exc:
            QMessageBox.critical(self, "Gönderim Hatası", f"WhatsApp otopilotunda hata: {exc}")
        finally:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("🚀 Otopilot ile Gönder")

    # ------------------------------------------------------------------
    def _handle_missing_accessibility(self, selected_numbers, msg_text: str, ax_err: str):
        """macOS Erişilebilirlik izni yoksa: PDF'i panoya koy, sohbeti aç, kullanıcıyı yönlendir.

        Not: Bu pencere yalnızca macOS'ta çıkar. Windows'ta böyle bir izin gerekmez.
        """
        app_name = _mac_host_app_name()
        abs_pdf = _prepare_shareable_pdf(self.pdf_path)
        clip_ok = _copy_file_to_clipboard(abs_pdf) if abs_pdf else False

        dlg = AutopilotNoticeDialog(
            self,
            kind="warning",
            title="Otopilot İzni Gerekli",
            subtitle="macOS, programın WhatsApp'ta sizin yerinize tuşlara basmasına henüz izin vermiyor. "
                     "Bu yüzden mesaj kutuya yazılıyor ama gönderilemiyor.",
            steps_title="Kalıcı çözüm (yalnızca bir kez yapılır)",
            steps=[
                "Sistem Ayarları › Gizlilik ve Güvenlik › Erişilebilirlik bölümünü açın.",
                f"Listede <b>{app_name}</b> anahtarını <b>AÇIK</b> yapın (yoksa + ile ekleyin).",
                f"<b>{app_name}</b> uygulamasını tamamen kapatıp (⌘Q) programı yeniden başlatın.",
            ],
            note=("PDF panoya kopyalandı. Şimdilik WhatsApp sohbetinde ⌘V ile yapıştırıp Enter'a basabilirsiniz."
                  if clip_ok else "Şimdilik PDF dosyasını WhatsApp sohbetine sürükleyip bırakabilirsiniz."),
            details=ax_err,
            buttons=[
                ("close", "Kapat", "secondary"),
                ("manual", "Sohbeti Aç (Elle Gönder)", "secondary"),
                ("settings", "Erişilebilirlik Ayarlarını Aç", "primary"),
            ],
        )
        dlg.exec()

        if dlg.choice == "settings":
            _open_mac_accessibility_settings()
        elif dlg.choice == "manual":
            for phone, _r in selected_numbers[:1]:
                clean = normalize_phone_number(phone)
                if clean:
                    uri = f"whatsapp://send?phone={clean}&text={urllib.parse.quote(msg_text)}"
                    subprocess.run(["open", uri], check=False)

    def _report_results(self, results: List[Dict[str, Any]], use_desktop: bool):
        """Gerçek sonuca göre dürüst bilgi verir (sahte 'gönderildi' yok)."""
        paste_key = "⌘V" if sys.platform == "darwin" else "Ctrl+V"
        pdf_name = os.path.basename(self.pdf_path or "")
        full_ok = [r for r in results if r.get("text_sent") and r.get("pdf_sent")]
        if results and len(full_ok) == len(results):
            AutopilotNoticeDialog(
                self,
                kind="success",
                title="Gönderim Tamamlandı",
                subtitle=f"Mesaj ve haftalık plan PDF'i {len(full_ok)} alıcıya otopilot ile gönderildi.",
                rows=[(r.get("name", ""), "Mesaj + PDF gönderildi", "ok") for r in full_ok],
                note=f"Ekli dosya: {pdf_name}",
                buttons=[("ok", "Tamam", "primary")],
            ).exec()
            self.accept()
            return

        if not use_desktop:
            AutopilotNoticeDialog(
                self,
                kind="info",
                title="WhatsApp Web Açıldı",
                subtitle="Sohbet tarayıcıda açıldı ve mesaj kutuya yazıldı.",
                steps_title="Gönderimi tamamlamak için",
                steps=[
                    "Mesajı göndermek için Enter'a basın.",
                    f"PDF panoya kopyalandı: sohbete tıklayıp <b>{paste_key}</b> ile yapıştırın.",
                    "Belge önizlemesi açılınca Enter'a basın.",
                ],
                note=f"Ekli dosya: {pdf_name}",
                buttons=[("ok", "Tamam", "primary")],
            ).exec()
            self.accept()
            return

        if any(r.get("permission") for r in results):
            err = next((r.get("error", "") for r in results if r.get("permission")), "")
            self._handle_missing_accessibility([], "", err)
            return

        rows = []
        for r in results:
            if r.get("text_sent") and r.get("pdf_sent"):
                rows.append((r.get("name", ""), "Mesaj + PDF gönderildi", "ok"))
            elif r.get("text_sent"):
                rows.append((r.get("name", ""), f"Mesaj gitti, PDF eklenemedi — PDF panoda ({paste_key} + Enter)", "warn"))
            else:
                rows.append((r.get("name", ""), f"Gönderilemedi: {r.get('error') or 'bilinmeyen hata'}", "fail"))
        AutopilotNoticeDialog(
            self,
            kind="warning",
            title="Gönderim Kısmen Tamamlandı",
            subtitle="Bazı adımlar otomatik tamamlanamadı. Alıcı bazında sonuç aşağıdadır.",
            rows=rows,
            note="İpucu: Otopilot çalışırken fareye ve klavyeye dokunmayın; WhatsApp penceresi önde kalmalıdır.",
            buttons=[("ok", "Tamam", "primary")],
        ).exec()


# ----------------------------------------------------------------------
# Profesyonel, temadan bağımsız bilgi penceresi (Windows + macOS aynı görünür)
# ----------------------------------------------------------------------
class AutopilotNoticeDialog(QDialog):
    """QMessageBox yerine kullanılan, yüksek kontrastlı ve kesilmeyen butonlu bilgi penceresi."""

    _PALETTE = {
        "warning": ("#b45309", "#fffbeb", "#fde68a", "!"),
        "success": ("#047857", "#ecfdf5", "#a7f3d0", "✓"),
        "info":    ("#1d4ed8", "#eff6ff", "#bfdbfe", "i"),
        "error":   ("#b91c1c", "#fef2f2", "#fecaca", "×"),
    }
    _ROW_STYLE = {
        "ok":   ("#047857", "#ecfdf5", "✓", "#a7f3d0"),
        "warn": ("#b45309", "#fffbeb", "!", "#fde68a"),
        "fail": ("#b91c1c", "#fef2f2", "×", "#fecaca"),
    }

    def __init__(self, parent=None, *, kind: str = "info", title: str = "", subtitle: str = "",
                 steps_title: str = "", steps: Optional[List[str]] = None,
                 rows: Optional[List[Tuple[str, str, str]]] = None,
                 note: str = "", details: str = "",
                 buttons: Optional[List[Tuple[str, str, str]]] = None):
        super().__init__(parent)
        self.choice: str = ""
        accent, soft, border, glyph = self._PALETTE.get(kind, self._PALETTE["info"])
        self.setWindowTitle(title or "Bilgi")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setMaximumWidth(680)
        self.setObjectName("apNotice")

        font_family = "Segoe UI" if sys.platform == "win32" else ".AppleSystemUIFont"
        self.setStyleSheet(f"""
            QDialog#apNotice {{ background: #ffffff; }}
            QDialog#apNotice QLabel {{ color: #0f172a; background: transparent; font-family: "{font_family}"; }}
            QDialog#apNotice QLabel#apTitle {{ font-size: 17px; font-weight: 700; color: #0f172a; }}
            QDialog#apNotice QLabel#apSubtitle {{ font-size: 13px; color: #334155; }}
            QDialog#apNotice QLabel#apSection {{ font-size: 12px; font-weight: 700; color: #475569; letter-spacing: 0.5px; }}
            QDialog#apNotice QLabel#apStepNum {{ background: {accent}; color: #ffffff; border-radius: 11px;
                                font-size: 12px; font-weight: 700; min-width: 22px; max-width: 22px;
                                min-height: 22px; max-height: 22px; }}
            QDialog#apNotice QLabel#apStepText {{ font-size: 13px; color: #0f172a; }}
            QFrame#apHeader {{ background: {soft}; border: none; border-bottom: 1px solid {border}; }}
            QDialog#apNotice QLabel#apBadge {{ background: {accent}; color: #ffffff; border-radius: 20px; font-size: 20px;
                              font-weight: 800; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; }}
            QFrame#apSteps {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }}
            QFrame#apNote {{ background: #f1f5f9; border-left: 4px solid {accent}; border-radius: 6px; }}
            QDialog#apNotice QLabel#apNoteText {{ font-size: 12px; color: #1e293b; }}
            QFrame#apFooter {{ background: #f8fafc; border-top: 1px solid #e2e8f0; }}
            QPushButton {{ font-family: "{font_family}"; font-size: 13px; font-weight: 600;
                           padding: 8px 16px; border-radius: 8px; min-height: 20px; }}
            QPushButton[apRole="primary"] {{ background: {accent}; color: #ffffff; border: 1px solid {accent}; }}
            QPushButton[apRole="primary"]:hover {{ background: #0f172a; border-color: #0f172a; }}
            QPushButton[apRole="secondary"] {{ background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }}
            QPushButton[apRole="secondary"]:hover {{ background: #f1f5f9; border-color: #94a3b8; }}
            QPushButton#apDetailsBtn {{ background: transparent; color: #475569; border: none;
                                        padding: 4px 0; font-weight: 500; text-decoration: underline; }}
            QTextEdit#apDetails {{ background: #0f172a; color: #e2e8f0; border-radius: 6px;
                                   font-family: Consolas, Menlo, monospace; font-size: 11px; padding: 6px; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Başlık bandı
        header = QFrame(); header.setObjectName("apHeader")
        hl = QHBoxLayout(header); hl.setContentsMargins(22, 18, 22, 18); hl.setSpacing(14)
        badge = QLabel(glyph); badge.setObjectName("apBadge"); badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        tv = QVBoxLayout(); tv.setSpacing(4)
        lt = QLabel(title); lt.setObjectName("apTitle"); lt.setWordWrap(True)
        tv.addWidget(lt)
        if subtitle:
            ls = QLabel(subtitle); ls.setObjectName("apSubtitle"); ls.setWordWrap(True)
            tv.addWidget(ls)
        hl.addLayout(tv, 1)
        root.addWidget(header)

        body = QVBoxLayout(); body.setContentsMargins(22, 16, 22, 16); body.setSpacing(12)

        if steps:
            if steps_title:
                sec = QLabel(steps_title.upper()); sec.setObjectName("apSection")
                body.addWidget(sec)
            box = QFrame(); box.setObjectName("apSteps")
            bl = QVBoxLayout(box); bl.setContentsMargins(14, 12, 14, 12); bl.setSpacing(10)
            for i, s in enumerate(steps, 1):
                row = QHBoxLayout(); row.setSpacing(10)
                n = QLabel(str(i)); n.setObjectName("apStepNum"); n.setAlignment(Qt.AlignmentFlag.AlignCenter)
                t = QLabel(s); t.setObjectName("apStepText"); t.setWordWrap(True)
                t.setTextFormat(Qt.TextFormat.RichText)
                row.addWidget(n, 0, Qt.AlignmentFlag.AlignTop); row.addWidget(t, 1)
                bl.addLayout(row)
            body.addWidget(box)

        if rows:
            for name, text, status in rows:
                fg, bg, g, bd = self._ROW_STYLE.get(status, self._ROW_STYLE["warn"])
                fr = QFrame()
                fr.setStyleSheet(f"QFrame {{ background: {bg}; border: 1px solid {bd}; border-radius: 8px; }}")
                rl = QHBoxLayout(fr); rl.setContentsMargins(12, 9, 12, 9); rl.setSpacing(10)
                ic = QLabel(g); ic.setAlignment(Qt.AlignmentFlag.AlignCenter); ic.setFixedSize(22, 22)
                ic.setStyleSheet(f"background: {fg}; color: #ffffff; border-radius: 11px; font-weight: 800; border: none;")
                nm = QLabel(f"<b>{name}</b>"); nm.setStyleSheet("color: #0f172a; font-size: 13px; border: none;")
                tx = QLabel(text); tx.setWordWrap(True); tx.setStyleSheet(f"color: {fg}; font-size: 12px; font-weight: 600; border: none;")
                rl.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop); rl.addWidget(nm); rl.addWidget(tx, 1)
                body.addWidget(fr)

        if note:
            nf = QFrame(); nf.setObjectName("apNote")
            nl = QHBoxLayout(nf); nl.setContentsMargins(12, 10, 12, 10)
            nt = QLabel(note); nt.setObjectName("apNoteText"); nt.setWordWrap(True)
            nl.addWidget(nt)
            body.addWidget(nf)

        if details:
            self._details = QTextEdit(); self._details.setObjectName("apDetails")
            self._details.setReadOnly(True); self._details.setPlainText(details)
            self._details.setFixedHeight(90); self._details.setVisible(False)
            dbtn = QPushButton("Teknik ayrıntıları göster"); dbtn.setObjectName("apDetailsBtn")
            dbtn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            def _toggle():
                vis = not self._details.isVisible()
                self._details.setVisible(vis)
                dbtn.setText("Teknik ayrıntıları gizle" if vis else "Teknik ayrıntıları göster")
                self.adjustSize()
            dbtn.clicked.connect(_toggle)
            body.addWidget(dbtn, 0, Qt.AlignmentFlag.AlignLeft)
            body.addWidget(self._details)

        root.addLayout(body)

        # Alt buton çubuğu (butonlar asla kesilmez: metne göre genişler)
        footer = QFrame(); footer.setObjectName("apFooter")
        fl = QHBoxLayout(footer); fl.setContentsMargins(22, 12, 22, 12); fl.setSpacing(10)
        fl.addStretch(1)
        for key, text, role in (buttons or [("ok", "Tamam", "primary")]):
            b = QPushButton(text)
            b.setProperty("apRole", role)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setMinimumWidth(max(96, b.fontMetrics().horizontalAdvance(text) + 40))
            b.setAutoDefault(False)
            if role == "primary":
                b.setDefault(True)
            b.clicked.connect(lambda _=False, k=key: self._choose(k))
            fl.addWidget(b)
        root.addWidget(footer)

    def _choose(self, key: str):
        self.choice = key
        self.accept()


# ----------------------------------------------------------------------
# macOS / Windows yardımcıları (otopilot)
# ----------------------------------------------------------------------
_AX_ERROR_MARKERS = ("-1719", "-25211", "1002", "-1743", "assistive", "not allowed",
                     "izin veril", "yardımcı erişim", "erişilebilirlik")


def _run_osascript(script: str, timeout: int = 60) -> Tuple[bool, str, str]:
    """osascript çalıştırır; (başarılı, stdout, stderr) döndürür. Hataları yutmaz."""
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return proc.returncode == 0, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except Exception as exc:  # pragma: no cover - platform dependent
        return False, "", str(exc)


def _is_permission_error(err: str) -> bool:
    low = (err or "").lower()
    return any(m in low for m in _AX_ERROR_MARKERS)


def _mac_accessibility_ok() -> Tuple[bool, str]:
    """System Events üzerinden tuş basabilmek için Erişilebilirlik izni var mı?"""
    if sys.platform != "darwin":
        return True, ""
    ok, _out, err = _run_osascript(
        'tell application "System Events" to count windows of process "Finder"', timeout=15
    )
    if ok:
        return True, ""
    return (False, err) if _is_permission_error(err) else (True, "")


def _mac_host_app_name() -> str:
    """Programı başlatan uygulama (izin bu uygulamaya verilmeli)."""
    bundle = os.environ.get("__CFBundleIdentifier", "")
    term = os.environ.get("TERM_PROGRAM", "")
    mapping = {
        "com.apple.Terminal": "Terminal",
        "com.googlecode.iterm2": "iTerm",
        "com.microsoft.VSCode": "Visual Studio Code",
    }
    if bundle in mapping:
        return mapping[bundle]
    if "pycharm" in bundle.lower():
        return "PyCharm"
    if term == "Apple_Terminal":
        return "Terminal"
    if term:
        return term.replace(".app", "")
    if getattr(sys, "frozen", False):
        return "KoçPilot 360 / OdevTakip"
    return "Terminal (veya Python)"


def _open_mac_accessibility_settings():
    try:
        subprocess.run(
            ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
            check=False,
        )
    except Exception:
        pass


def _prepare_shareable_pdf(pdf_path: str) -> str:
    """PDF'i WhatsApp'ın (sandbox) okuyabileceği kalıcı bir klasöre kopyalar."""
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    src = os.path.abspath(pdf_path)
    try:
        import shutil
        target_dir = os.path.join(os.path.expanduser("~"), "Documents", "KocPilot360", "Haftalik_Planlar")
        os.makedirs(target_dir, exist_ok=True)
        dst = os.path.join(target_dir, os.path.basename(src))
        if os.path.abspath(dst) != src:
            shutil.copy2(src, dst)
        return dst
    except Exception:
        return src


def _copy_file_to_clipboard(abs_path: str) -> bool:
    """Dosyayı panoya Finder/Gezgin'deki 'Kopyala' ile aynı şekilde (dosya nesnesi olarak) koyar.
    
    macOS: AppKit NSPasteboard (NSURL)
    Windows: PyQt6 QMimeData + QUrl (Native CF_HDROP) ve .NET SetFileDropList yedekleri
    """
    if not abs_path or not os.path.exists(abs_path):
        return False

    # 1. PyQt6 Yerel Pano (Tüm platformlarda doğrudan ve en hızlı yöntem)
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QMimeData, QUrl
        app = QApplication.instance()
        if app is not None:
            mime = QMimeData()
            norm_p = os.path.normpath(os.path.abspath(abs_path))
            mime.setUrls([QUrl.fromLocalFile(norm_p)])
            app.clipboard().setMimeData(mime)
            if sys.platform == "win32":
                return True
    except Exception:
        pass

    if sys.platform == "darwin":
        safe = abs_path.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'use framework "AppKit"\n'
            'use scripting additions\n'
            "set pb to current application's NSPasteboard's generalPasteboard()\n"
            "pb's clearContents()\n"
            f"set u to current application's NSURL's fileURLWithPath:\"{safe}\"\n"
            "return ((pb's writeObjects:{u}) as boolean)"
        )
        ok, out, _err = _run_osascript(script, timeout=15)
        if ok and out.lower() == "true":
            return True
        ok2, _o, _e = _run_osascript(f'set the clipboard to (POSIX file "{safe}")', timeout=15)
        return ok2

    if sys.platform == "win32":
        norm_p = os.path.normpath(os.path.abspath(abs_path))
        # 2. Windows PowerShell 5.1 & .NET evrensel FileDropList yöntemi (Tüm Win10/Win11 varsayılanı)
        try:
            ps_path = norm_p.replace("'", "''")
            ps_cmd = (
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"$c = New-Object System.Collections.Specialized.StringCollection; "
                f"$c.Add('{ps_path}'); "
                f"[System.Windows.Forms.Clipboard]::SetFileDropList($c)"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0:
                return True
        except Exception:
            pass

        # 3. Modern PowerShell 7+ veya Set-Clipboard desteği
        try:
            ps_path = norm_p.replace("'", "''")
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", f"Set-Clipboard -Path '{ps_path}'"],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                return True
        except Exception:
            pass
        return False
    return False


def _win_focus_whatsapp(attempts: int = 12) -> bool:
    """Windows: WhatsApp masaüstü penceresini bulup öne getirir; önde olduğunu doğrular.

    ctypes ile (ek paket gerektirmez). Windows'un 'foreground lock' kısıtını aşmak için
    kısa bir ALT tuşu simülasyonu kullanılır.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import time
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        def _title(hwnd) -> str:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            return buf.value or ""

        def _is_wa(hwnd) -> bool:
            return bool(hwnd) and "whatsapp" in _title(hwnd).lower()

        for _ in range(attempts):
            fg = user32.GetForegroundWindow()
            if _is_wa(fg):
                return True
            found = []
            EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def _cb(hwnd, _lp):
                if user32.IsWindowVisible(hwnd) and _is_wa(hwnd):
                    found.append(hwnd)
                    return False
                return True
            user32.EnumWindows(EnumProc(_cb), 0)
            if found:
                hwnd = found[0]
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.keybd_event(0x12, 0, 0, 0)       # ALT basılı
                user32.SetForegroundWindow(hwnd)
                user32.keybd_event(0x12, 0, 0x0002, 0)  # ALT bırak
            time.sleep(0.35)
        return _is_wa(user32.GetForegroundWindow())
    except Exception:
        # Doğrulama yapılamıyorsa eski davranışı koru (gönderimi engelleme)
        return True


def _dispatch_desktop_autopilot(clean_phone: str, message: str, pdf_path: str, student_id: Optional[int]) -> Dict[str, Any]:
    """Opens desktop WhatsApp, sends message, and pastes + sends PDF document in autopilot.

    Returns a result dict: text_sent, pdf_sent, error, permission.
    """
    result: Dict[str, Any] = {"text_sent": False, "pdf_sent": False, "error": "", "permission": False}
    encoded = urllib.parse.quote(message)
    uri = f"whatsapp://send?phone={clean_phone}&text={encoded}"
    abs_pdf = _prepare_shareable_pdf(pdf_path)
    has_pdf = bool(abs_pdf)

    if sys.platform == "darwin":
        # 0. PDF'i önceden panoya dosya olarak koy (izin gerektirmez; otopilot
        #    başarısız olsa bile kullanıcı ⌘V ile yapıştırabilir)
        clip_ok = _copy_file_to_clipboard(abs_pdf) if has_pdf else False

        # 1. WhatsApp uygulamasını aç ve sohbeti yükle
        subprocess.run(["open", uri], check=False)

        # 2. AppleScript: WhatsApp'ı GERÇEKTEN öne getirdiğini doğrulayarak tuşlara bas.
        #    Odak başka uygulamadaysa asla tuş gönderme (yanlış pencereye yazmayı önler).
        paste_block = ""
        if has_pdf and clip_ok:
            paste_block = """
            delay 1.5
            if not my focusWA() then return "TEXT_OK|FOCUS_LOST"
            tell application "System Events"
                keystroke "v" using command down
            end tell
            delay 2.8
            if not my focusWA() then return "TEXT_OK|FOCUS_LOST"
            tell application "System Events"
                key code 36
            end tell
            delay 0.8
            return "TEXT_OK|PDF_OK"
            """
        script = f"""
        on focusWA()
            tell application "WhatsApp" to activate
            delay 0.4
            tell application "System Events"
                repeat 15 times
                    if exists (process "WhatsApp") then
                        set frontmost of process "WhatsApp" to true
                        delay 0.2
                        if frontmost of process "WhatsApp" then return true
                    end if
                    delay 0.3
                end repeat
            end tell
            return false
        end focusWA

        delay 2.8
        if not my focusWA() then return "FOCUS_LOST"
        delay 0.4
        tell application "System Events"
            key code 36
        end tell
        {paste_block if paste_block else 'return "TEXT_OK|NO_PDF"'}
        """
        ok, out, err = _run_osascript(script, timeout=60)
        if not ok:
            result["error"] = err or "AppleScript hatası"
            result["permission"] = _is_permission_error(err)
        else:
            result["text_sent"] = out.startswith("TEXT_OK")
            result["pdf_sent"] = (out == "TEXT_OK|PDF_OK") or (out == "TEXT_OK|NO_PDF" and not has_pdf)
            if out == "FOCUS_LOST":
                result["error"] = "WhatsApp penceresi öne getirilemedi"
            elif has_pdf and not clip_ok:
                result["error"] = "PDF panoya kopyalanamadı"
            elif "FOCUS_LOST" in out:
                result["error"] = "PDF yapıştırılırken WhatsApp odağı kayboldu"
    elif sys.platform == "win32":
        clip_ok = _copy_file_to_clipboard(abs_pdf) if has_pdf else False
        try:
            os.startfile(uri)
        except Exception:
            subprocess.run(f'start "" "{uri}"', shell=True)
        import time
        time.sleep(3.0)
        try:
            import pyautogui as pag
        except Exception:
            result["error"] = "pyautogui kurulu değil (pip install pyautogui)"
            pag = None
        if pag is not None:
            try:
                # Her tuştan önce WhatsApp'ın gerçekten önde olduğunu doğrula
                if not _win_focus_whatsapp():
                    result["error"] = "WhatsApp penceresi öne getirilemedi"
                else:
                    pag.press("enter")  # Metin mesajını gönder
                    result["text_sent"] = True
                    time.sleep(1.5)
                    if has_pdf and clip_ok:
                        if not _win_focus_whatsapp():
                            result["error"] = "PDF yapıştırılırken WhatsApp odağı kayboldu"
                        else:
                            pag.hotkey("ctrl", "v")  # PDF'i yapıştır
                            time.sleep(2.8)
                            if _win_focus_whatsapp():
                                pag.press("enter")  # Belge gönderimini onayla
                                result["pdf_sent"] = True
                            else:
                                result["error"] = "PDF onaylanırken WhatsApp odağı kayboldu"
                    elif not has_pdf:
                        result["pdf_sent"] = True
                    else:
                        result["error"] = "PDF panoya kopyalanamadı"
            except Exception as exc:
                result["error"] = f"pyautogui: {exc}"
    else:
        subprocess.run(["xdg-open", uri], check=False)
        result["error"] = "Bu platformda otomatik gönderim desteklenmiyor"

    _log_whatsapp_dispatch(clean_phone, message, student_id, success=bool(result["text_sent"]))
    return result


def _dispatch_web_autopilot(clean_phone: str, message: str, pdf_path: str, student_id: Optional[int]) -> Dict[str, Any]:
    """Opens WhatsApp Web in default browser, and sets clipboard to PDF."""
    encoded = urllib.parse.quote(message)
    web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded}"
    import webbrowser
    webbrowser.open(web_url)

    abs_pdf = _prepare_shareable_pdf(pdf_path)
    clip_ok = _copy_file_to_clipboard(abs_pdf) if abs_pdf else False

    _log_whatsapp_dispatch(clean_phone, message, student_id, success=True)
    return {"text_sent": False, "pdf_sent": False, "clipboard": clip_ok,
            "error": "", "permission": False}


def _log_whatsapp_dispatch(phone: str, msg: str, student_id: Optional[int], success: bool = True):
    try:
        con = db.get_conn()
        tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con.execute(
            """INSERT INTO whatsapp_log (
                zaman, ogrenci_id, numara, mesaj_onizleme, durum, gonderilen, basarisiz, mesaj
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tarih,
                student_id,
                str(phone),
                (msg or "")[:180],
                "OK" if success else "HATA",
                1 if success else 0,
                0 if success else 1,
                msg or "",
            ),
        )
        con.commit()
    except Exception:
        pass


def enhance_print_preview_dialog(
    preview: QPrintPreviewDialog,
    html_holder: List[str],
    student_id: Optional[int],
    student_name: str,
):
    """Injects [💾 PDF Olarak Kaydet] and [📱 WhatsApp ile Gönder] buttons into the preview toolbar."""
    try:
        from PyQt6.sip import isdeleted
        if isdeleted(preview):
            return
    except Exception:
        pass

    if getattr(preview, "_v35_enhanced", False):
        return
    try:
        preview._v35_enhanced = True
    except Exception:
        pass

    try:
        toolbars = preview.findChildren(QToolBar)
        if not toolbars:
            return

        tb = toolbars[0]
        tb.addSeparator()

        # 1. PDF Kaydet Butonu
        btn_save_pdf = QPushButton("💾 PDF Kaydet")
        btn_save_pdf.setToolTip("Haftalık çalışma planını bilgisayarınıza A4 yatay PDF olarak kaydeder.")
        btn_save_pdf.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_save_pdf.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #1e293b;
                font-weight: 700;
                font-size: 11.5px;
                padding: 5px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
        """)

        def _on_save_pdf():
            try:
                from services.smart_calendar import SmartCalendarService
                html = html_holder[0] if (html_holder and html_holder[0]) else SmartCalendarService.get_latest_html()
                save_weekly_calendar_pdf_file(html, student_name, parent=preview)
            except Exception as ex:
                QMessageBox.warning(preview, "Kayıt Hatası", f"PDF kaydedilirken hata: {ex}")

        btn_save_pdf.clicked.connect(_on_save_pdf)
        tb.addWidget(btn_save_pdf)

        # 2. WhatsApp ile Gönder Butonu
        btn_send_wa = QPushButton("📱 WhatsApp Gönder")
        btn_send_wa.setToolTip("Haftalık plan PDF'ini öğrenci ve veliye otomatik (otopilot) WhatsApp mesajıyla gönderir.")
        btn_send_wa.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_send_wa.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 700;
                font-size: 11.5px;
                padding: 5px 14px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)

        def _on_send_wa():
            try:
                from services.smart_calendar import SmartCalendarService
                html = html_holder[0] if (html_holder and html_holder[0]) else SmartCalendarService.get_latest_html()
                # Create temp pdf for sending
                tmp_dir = tempfile.gettempdir()
                safe_name = _sanitize_filename(student_name)
                date_str = datetime.date.today().strftime("%Y_%m_%d")
                temp_pdf = os.path.join(tmp_dir, f"{safe_name}_Haftalik_Calisma_Plani_{date_str}.pdf")
                export_html_to_pdf_file(html, temp_pdf)

                dlg = WeeklyPlanWhatsAppDialog(preview, student_id, student_name, temp_pdf)
                dlg.exec()
            except Exception as ex:
                QMessageBox.warning(preview, "WhatsApp Hatası", f"WhatsApp penceresi açılırken hata: {ex}")

        btn_send_wa.clicked.connect(_on_send_wa)
        tb.addWidget(btn_send_wa)
    except Exception:
        pass


def wrap_open_smart_calendar_pdf(target_cls):
    """Wraps target_cls._open_smart_calendar_pdf non-invasively at runtime."""
    original_method = getattr(target_cls, "_open_smart_calendar_pdf", None)
    if not original_method:
        return

    def wrapped(self):
        # Synchronously intercept QPrintPreviewDialog.exec right when it executes
        orig_preview_exec = QPrintPreviewDialog.exec

        def exec_hook(dlg):
            try:
                from PyQt6.sip import isdeleted
                if not isdeleted(dlg):
                    s_uid = self._secili_ogrenci_id() if hasattr(self, "_secili_ogrenci_id") else None
                    if not s_uid and hasattr(self, "cmbAd"):
                        s_uid = self.cmbAd.currentData()
                    s_name = ""
                    if hasattr(self, "cmbAd") and hasattr(self, "cmbSoyad"):
                        s_name = f"{self.cmbAd.currentText()} {self.cmbSoyad.currentText()}".strip()

                    enhance_print_preview_dialog(dlg, [""], s_uid, s_name)
            except Exception:
                pass
            return orig_preview_exec(dlg)

        QPrintPreviewDialog.exec = exec_hook
        try:
            return original_method(self)
        finally:
            QPrintPreviewDialog.exec = orig_preview_exec

    target_cls._open_smart_calendar_pdf = wrapped
