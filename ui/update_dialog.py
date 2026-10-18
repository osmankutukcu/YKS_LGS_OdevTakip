# -*- coding: utf-8 -*-
"""
YKS/LGS Ödev & Takip Yöneticisi - Otomatik Güncelleme Diyaloğu (PyQt6)
"""

import re
import html
import sys
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QFrame, QWidget, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.theme import register_theme_listener, _contrast_safe_background
from ui.theme_tokens_v37 import semantic_palette
from ui.theme_special_v42 import legible_accent

from utils.updater import (
    UpdateDownloaderThread, apply_update_and_restart
)


class UpdateDialog(QDialog):
    """
    Modern & Profesyonel Yazılım Güncelleme Penceresi.
    - Sürüm karşılaştırma kartları
    - Zengin sürüm notları (Changelog)
    - Canlı parça parça indirme ve ilerleme çubuğu
    - Tek tıkla otomatik yenileme ve yeniden başlatma
    """
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.downloader_thread = None
        self._downloaded_installer = None
        self._install_pending = False

        self.setWindowTitle("Yazılım Güncellemesi")
        self.resize(580, 520)
        self.setMinimumSize(520, 460)
        self.setModal(True)

        self._build_ui()
        self._on_theme_changed()
        register_theme_listener(self)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        # 1. Başlık Alanı (Executive Header)
        h_row = QHBoxLayout()
        h_row.setSpacing(14)
        
        lbl_icon = QLabel("🚀")
        lbl_icon.setStyleSheet("font-size: 34px;")
        
        v_title = QVBoxLayout()
        v_title.setSpacing(3)
        lbl_t = QLabel("Yeni Bir Güncelleme Mevcut!")
        lbl_t.setStyleSheet("font-size: 18px; font-weight: bold; color: #0f172a;")
        lbl_sub = QLabel("Daha kararlı ve gelişmiş bir deneyim için son sürüme geçin.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        v_title.addWidget(lbl_t)
        v_title.addWidget(lbl_sub)

        h_row.addWidget(lbl_icon)
        h_row.addLayout(v_title)
        h_row.addStretch(1)
        root.addLayout(h_row)

        # 2. Sürüm Karşılaştırma Kartı
        fr_versions = QFrame()
        fr_versions.setObjectName("VersionCard")
        lay_v = QHBoxLayout(fr_versions)
        lay_v.setContentsMargins(16, 12, 16, 12)
        lay_v.setSpacing(12)

        cur_v = self.update_info.get("current_version", "3.5.0")
        new_v = self.update_info.get("latest_version", "3.6.0")
        f_size_mb = self.update_info.get("file_size", 0) / (1024 * 1024)
        size_txt = f"{f_size_mb:.1f} MB" if f_size_mb > 0 else "Otomatik Boyut"

        # Mevcut Sürüm
        col_cur = QVBoxLayout()
        lbl_c_tag = QLabel("Mevcut Sürüm")
        lbl_c_tag.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        lbl_c_val = QLabel(f"v{cur_v}")
        lbl_c_val.setStyleSheet("font-size: 14px; font-weight: bold; color: #475569;")
        col_cur.addWidget(lbl_c_tag)
        col_cur.addWidget(lbl_c_val)

        # Ok simgesi
        lbl_arrow = QLabel("➔")
        lbl_arrow.setStyleSheet("font-size: 18px; color: #94a3b8; font-weight: bold;")
        lbl_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Yeni Sürüm
        col_new = QVBoxLayout()
        lbl_n_tag = QLabel("Yeni Sürüm")
        lbl_n_tag.setStyleSheet("font-size: 11px; color: #059669; font-weight: 600;")
        lbl_n_val = QLabel(f"v{new_v}")
        lbl_n_val.setStyleSheet("""
            background-color: #ecfdf5; color: #047857; font-size: 14px;
            font-weight: bold; padding: 2px 10px; border-radius: 6px;
            border: 1px solid #a7f3d0;
        """)
        col_new.addWidget(lbl_n_tag)
        col_new.addWidget(lbl_n_val)

        # Bilgi (Boyut / Tarih)
        col_info = QVBoxLayout()
        col_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_size = QLabel(f"📦 {size_txt}")
        lbl_size.setStyleSheet("font-size: 12px; color: #334155; font-weight: 600;")
        pub_date = self.update_info.get("published_at", "")
        lbl_date = QLabel(f"📅 {pub_date}" if pub_date else "")
        lbl_date.setStyleSheet("font-size: 11px; color: #94a3b8;")
        col_info.addWidget(lbl_size)
        if pub_date:
            col_info.addWidget(lbl_date)

        lay_v.addLayout(col_cur)
        lay_v.addWidget(lbl_arrow)
        lay_v.addLayout(col_new)
        lay_v.addStretch(1)
        lay_v.addLayout(col_info)
        root.addWidget(fr_versions)

        # 3. Sürüm Değişiklik Notları (Changelog)
        lbl_ch_title = QLabel("📝 Yenilikler ve Değişiklikler:")
        lbl_ch_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #334155;")
        root.addWidget(lbl_ch_title)

        self.txtChangelog = QTextBrowser()
        self.txtChangelog.setOpenExternalLinks(True)
        changelog_text = self.update_info.get("changelog", "Detaylı sürüm notu bulunmuyor.")
        # Basit Markdown -> HTML dönüşümü
        html_notes = self._format_changelog_to_html(changelog_text)
        self.txtChangelog.setHtml(html_notes)
        root.addWidget(self.txtChangelog, 1)

        # 4. İndirme & İlerleme Alanı (Başlangıçta Gizli)
        self.frProgress = QFrame()
        self.frProgress.setObjectName("ProgressCard")
        self.frProgress.setVisible(False)
        lay_pr = QVBoxLayout(self.frProgress)
        lay_pr.setContentsMargins(14, 12, 14, 12)
        lay_pr.setSpacing(8)

        self.lblProgressStatus = QLabel("İndirme başlatılıyor...")
        self.lblProgressStatus.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(True)
        self.progressBar.setMinimumHeight(22)

        self.lblProgressStats = QLabel("0 MB / 0 MB (%0)")
        self.lblProgressStats.setStyleSheet("font-size: 11px; color: #64748b;")

        lay_pr.addWidget(self.lblProgressStatus)
        lay_pr.addWidget(self.progressBar)
        lay_pr.addWidget(self.lblProgressStats)
        root.addWidget(self.frProgress)

        # 5. Alt Butonlar
        self.btnBar = QHBoxLayout()
        self.btnBar.setSpacing(10)

        self.btnGitHub = QPushButton("🌐 GitHub'da Gör")
        self.btnGitHub.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnGitHub.clicked.connect(self._open_github)

        self.btnLater = QPushButton("Daha Sonra")
        self.btnLater.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnLater.clicked.connect(self.reject)

        self.btnUpdate = QPushButton("🚀 Güncellemeyi İndir ve Kur")
        self.btnUpdate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnUpdate.setObjectName("btnUpdateAction")
        self.btnUpdate.clicked.connect(self._start_update)
        if not self.update_info.get("installable", False) or not (sys.platform.startswith("win") and getattr(sys, "frozen", False)):
            self.btnUpdate.setText("GitHub üzerinden kurulum gerekli")
            self.btnUpdate.setEnabled(False)
            self.btnGitHub.setText("🌐 GitHub sürüm sayfası")

        self.btnBar.addWidget(self.btnGitHub)
        self.btnBar.addStretch(1)
        self.btnBar.addWidget(self.btnLater)
        self.btnBar.addWidget(self.btnUpdate)
        root.addLayout(self.btnBar)
        self._theme_labels = [
            (lbl_t, 'strong'), (lbl_sub, 'muted'),
            (lbl_c_tag, 'muted'), (lbl_c_val, 'strong'),
            (lbl_arrow, 'muted'), (lbl_n_tag, 'success'),
            (lbl_size, 'strong'), (lbl_date, 'muted'),
            (lbl_ch_title, 'strong'),
            (self.lblProgressStatus, 'strong'), (self.lblProgressStats, 'muted'),
        ]

    def _on_theme_changed(self):
        self._apply_styles()
        c = semantic_palette()
        colors = {
            'strong': c['fg'],
            'muted': legible_accent(c['bg'], '#94A3B8' if c['dark'] else '#64748B'),
            'success': c['surface_fg'],
        }
        for widget, role in self._theme_labels:
            style = widget.styleSheet()
            # Modify foreground only, without touching font sizing or badge fills.
            style = re.sub(r'(?<![-\w])color\s*:\s*#[0-9a-fA-F]{3,8}',
                           'color: ' + colors[role], style)
            widget.setStyleSheet(style)

    def _apply_styles(self):
        c = semantic_palette()
        success = _contrast_safe_background('#059669', '#FFFFFF')
        success_hover = _contrast_safe_background('#047857', '#FFFFFF')
        progress = _contrast_safe_background('#10B981', c['alt_fg'])
        self.setStyleSheet(f"""
            QDialog {{ background:{c['bg']}; color:{c['fg']};
                font-family:'Segoe UI', system-ui, -apple-system, sans-serif; }}
            QFrame#VersionCard, QFrame#ProgressCard {{
                background:{c['surface']}; border:1px solid {c['border']};
                border-radius:10px; }}
            QTextBrowser {{
                background:#FFFFFF; color:#1E293B;
                border:1px solid {c['border']}; border-radius:8px;
                padding:10px 12px; font-size:13px; }}
            QProgressBar {{
                background:{c['alt']}; color:{c['alt_fg']};
                border:1px solid {c['border']}; border-radius:6px;
                text-align:center; font-weight:bold; font-size:11px; }}
            QProgressBar::chunk {{ background:{progress}; border-radius:5px; }}
            QPushButton {{
                background:{c['neutral']}; color:{c['neutral_fg']};
                border:1px solid {c['border']}; border-radius:6px;
                padding:8px 16px; font-size:12px; font-weight:600; }}
            QPushButton:hover {{ background:{c['tab_hover']};
                color:{c['tab_hover_fg']}; border-color:{c['border']}; }}
            QPushButton#btnUpdateAction {{
                background:{success}; color:#FFFFFF;
                border:none; font-weight:bold; padding:8px 20px; }}
            QPushButton#btnUpdateAction:hover {{
                background:{success_hover}; color:#FFFFFF; }}
            QPushButton#btnUpdateAction:disabled {{
                background:{c['alt']}; color:{c['alt_fg']}; }}
        """)

    def _format_changelog_to_html(self, raw: str) -> str:
        """Markdown benzeri metni şık HTML formatına çevirir."""
        lines = []
        for line in raw.splitlines():
            s = html.escape(line.strip())
            # **bold** desteği
            s = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)
            if s.startswith("### "):
                lines.append(f"<h4 style='color:#0f172a; margin:8px 0 4px 0;'>{s[4:]}</h4>")
            elif s.startswith("## "):
                lines.append(f"<h3 style='color:#0f172a; margin:10px 0 4px 0;'>{s[3:]}</h3>")
            elif s.startswith("# "):
                lines.append(f"<h2 style='color:#0f172a; margin:12px 0 4px 0;'>{s[2:]}</h2>")
            elif s.startswith("- ") or s.startswith("* "):
                lines.append(f"<li style='margin-bottom:3px;'>{s[2:]}</li>")
            elif s:
                lines.append(f"<p style='margin:4px 0;'>{s}</p>")
        return f"<div style='font-family:sans-serif;'>{''.join(lines)}</div>"

    def _open_github(self):
        url = self.update_info.get("html_url") or "https://github.com/osmankutukcu/YKS_LGS_OdevTakip/releases"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _start_update(self):
        url = self.update_info.get("download_url")
        if not url or not self.update_info.get("installable"):
            QMessageBox.warning(
                self, "İndirme Bağlantısı Yok",
                "Bu sürüm için otomatik indirme paketi henüz eklenmemiş.\n"
                "GitHub sürüm sayfasına yönlendiriliyorsunuz."
            )
            self._open_github()
            return

        # UI'ı indirme moduna geçir
        self.btnUpdate.setEnabled(False)
        self.btnLater.setText("İptal Et")
        self.frProgress.setVisible(True)
        self.txtChangelog.setMaximumHeight(130)

        # İndirme Thread'ini Başlat
        self.downloader_thread = UpdateDownloaderThread(self.update_info, parent=self)
        self.downloader_thread.progress.connect(self._on_download_progress)
        self.downloader_thread.download_completed.connect(self._on_download_completed)
        self.downloader_thread.download_failed.connect(self._on_download_failed)
        self.downloader_thread.start()

    def _on_download_progress(self, downloaded: int, total: int, pct: float):
        self.progressBar.setValue(int(pct))
        d_mb = downloaded / (1024 * 1024)
        t_mb = total / (1024 * 1024)
        self.lblProgressStatus.setText("📦 Güncelleme paketi indiriliyor...")
        if total > 0:
            self.lblProgressStats.setText(f"{d_mb:.1f} MB / {t_mb:.1f} MB  (%{pct:.0f})")
        else:
            self.lblProgressStats.setText(f"{d_mb:.1f} MB indirildi...")

    def _on_download_completed(self, installer_path: str):
        self._downloaded_installer = installer_path
        self._install_pending = True
        self.lblProgressStatus.setText("⚙️ Güncelleme dosyaları hazırlanıyor (Veritabanı güvenceye alınıyor)...")
        self.progressBar.setValue(100)
        self.lblProgressStats.setText("İndirme doğrulandı. Windows kurulum sihirbazı açılacak.")
        QApplication.processEvents()

        # 1-2 saniye bekletip kurulumu uygula
        QTimer.singleShot(800, self._apply_update_final)

    def _apply_update_final(self):
        if not self._install_pending:
            return
        self._install_pending = False
        try:
            if self.downloader_thread is None or not self.downloader_thread.verified_digest:
                raise RuntimeError("Doğrulanmış SHA-256 eksik")
            apply_update_and_restart(
                self._downloaded_installer,
                self.downloader_thread.verified_digest,
                int(self.update_info["file_size"]),
            )
        except Exception as e:
            QMessageBox.critical(self, "Kurulum Hatası", f"Güncelleme yüklenirken bir hata oluştu:\n{e}")
            self.btnUpdate.setEnabled(True)
            self.frProgress.setVisible(False)

    def _on_download_failed(self, err_msg: str):
        self.lblProgressStatus.setText("❌ İndirme Başarısız Oldu")
        self.frProgress.setVisible(False)
        self.btnUpdate.setEnabled(True)
        self.btnLater.setText("Kapat")
        self.btnLater.setEnabled(True)
        QMessageBox.warning(self, "Güncelleme Hatası", f"{err_msg}\nLütfen internet bağlantınızı kontrol edin veya GitHub sayfasından manuel indirin.")

    def reject(self):
        self._install_pending = False
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.cancel()
            self.btnLater.setEnabled(False)
            self.lblProgressStatus.setText("İndirme iptal ediliyor...")
            return
        super().reject()
