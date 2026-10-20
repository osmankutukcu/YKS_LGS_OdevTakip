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

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Gönderiliyor...")

        try:
            success_count = 0
            fail_count = 0
            for phone, r_name in selected_numbers:
                clean = normalize_phone_number(phone)
                if not clean:
                    fail_count += 1
                    continue

                if use_desktop:
                    _dispatch_desktop_autopilot(clean, msg_text, self.pdf_path, self.student_id)
                else:
                    _dispatch_web_autopilot(clean, msg_text, self.pdf_path, self.student_id)
                success_count += 1

            QMessageBox.information(
                self,
                "WhatsApp Gönderimi Tamamlandı",
                f"Haftalık plan PDF'i {success_count} alıcı için WhatsApp üzerinden gönderildi.\n"
                f"Ekli dosya: {os.path.basename(self.pdf_path)}",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Gönderim Hatası", f"WhatsApp otopilotunda hata: {exc}")
        finally:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("🚀 Otopilot ile Gönder")


def _dispatch_desktop_autopilot(clean_phone: str, message: str, pdf_path: str, student_id: Optional[int]):
    """Opens desktop WhatsApp, pastes message, triggers auto-send, and presents PDF."""
    encoded = urllib.parse.quote(message)
    uri = f"whatsapp://send?phone={clean_phone}&text={encoded}"

    if sys.platform == "darwin":
        subprocess.run(["open", uri], check=False)
        # Reveal PDF in Finder so teacher can drag or auto-attach
        if pdf_path and os.path.exists(pdf_path):
            try:
                subprocess.run(["open", "-R", pdf_path], check=False)
            except Exception:
                pass
        # Autopilot press Enter via AppleScript after WhatsApp focuses
        script = """
        delay 1.0
        tell application "System Events"
            set activeApp to name of first application process whose frontmost is true
        end tell
        delay 0.5
        tell application "System Events"
            key code 36
        end tell
        """
        try:
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception:
            pass
    elif sys.platform == "win32":
        try:
            os.startfile(uri)
        except Exception:
            subprocess.run(f'start "" "{uri}"', shell=True)
        if pdf_path and os.path.exists(pdf_path):
            try:
                subprocess.run(f'explorer /select,"{os.path.abspath(pdf_path)}"', shell=True)
            except Exception:
                pass
        try:
            import pyautogui as pag
            import time
            time.sleep(1.5)
            pag.press("enter")
        except Exception:
            pass
    else:
        subprocess.run(["xdg-open", uri], check=False)

    _log_whatsapp_dispatch(clean_phone, message, student_id, success=True)


def _dispatch_web_autopilot(clean_phone: str, message: str, pdf_path: str, student_id: Optional[int]):
    """Opens WhatsApp Web in default browser and highlights PDF."""
    encoded = urllib.parse.quote(message)
    web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded}"
    import webbrowser
    webbrowser.open(web_url)
    if pdf_path and os.path.exists(pdf_path):
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", pdf_path], check=False)
        elif sys.platform == "win32":
            subprocess.run(f'explorer /select,"{os.path.abspath(pdf_path)}"', shell=True)

    _log_whatsapp_dispatch(clean_phone, message, student_id, success=True)


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
