# -*- coding: utf-8 -*-
"""
YKS/LGS Ödev & Takip Yöneticisi - Otomatik Güncelleme Diyaloğu (PyQt6)
"""

import re
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QFrame, QWidget, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from utils.updater import (
    UpdateDownloaderThread, prepare_staging_directory,
    apply_update_and_restart, get_application_root
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
        self._downloaded_zip = None

        self.setWindowTitle("Yazılım Güncellemesi")
        self.resize(580, 520)
        self.setMinimumSize(520, 460)
        self.setModal(True)

        self._build_ui()
        self._apply_styles()

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

        self.btnUpdate = QPushButton("🚀 Şimdi Güncelle ve Yeniden Başlat")
        self.btnUpdate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnUpdate.setObjectName("btnUpdateAction")
        self.btnUpdate.clicked.connect(self._start_update)

        self.btnBar.addWidget(self.btnGitHub)
        self.btnBar.addStretch(1)
        self.btnBar.addWidget(self.btnLater)
        self.btnBar.addWidget(self.btnUpdate)
        root.addLayout(self.btnBar)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QFrame#VersionCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QFrame#ProgressCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
            }
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.5;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: #f1f5f9;
                text-align: center;
                color: #0f172a;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 16px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
                border-color: #94a3b8;
            }
            QPushButton#btnUpdateAction {
                background-color: #059669;
                color: #ffffff;
                border: none;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton#btnUpdateAction:hover {
                background-color: #047857;
            }
            QPushButton#btnUpdateAction:disabled {
                background-color: #94a3b8;
            }
        """)

    def _format_changelog_to_html(self, raw: str) -> str:
        """Markdown benzeri metni şık HTML formatına çevirir."""
        lines = []
        for line in raw.splitlines():
            s = line.strip()
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
        if not url:
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
        self.downloader_thread = UpdateDownloaderThread(url, get_application_root(), self)
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

    def _on_download_completed(self, zip_path: str):
        self._downloaded_zip = zip_path
        self.lblProgressStatus.setText("⚙️ Güncelleme dosyaları hazırlanıyor (Veritabanı güvenceye alınıyor)...")
        self.progressBar.setValue(100)
        self.lblProgressStats.setText("Tamamlandı! Uygulama yeniden başlatılıyor...")
        QApplication.processEvents()

        # 1-2 saniye bekletip kurulumu uygula
        QTimer.singleShot(800, self._apply_update_final)

    def _apply_update_final(self):
        try:
            root = get_application_root()
            # Staging ve Güvenlik Filtresi
            prepare_staging_directory(self._downloaded_zip, root)
            # Hot-Swap ve Yeniden Başlatma
            apply_update_and_restart(root)
        except Exception as e:
            QMessageBox.critical(self, "Kurulum Hatası", f"Güncelleme yüklenirken bir hata oluştu:\n{e}")
            self.btnUpdate.setEnabled(True)
            self.frProgress.setVisible(False)

    def _on_download_failed(self, err_msg: str):
        self.lblProgressStatus.setText("❌ İndirme Başarısız Oldu")
        self.frProgress.setVisible(False)
        self.btnUpdate.setEnabled(True)
        self.btnLater.setText("Kapat")
        QMessageBox.warning(self, "Güncelleme Hatası", f"{err_msg}\nLütfen internet bağlantınızı kontrol edin veya GitHub sayfasından manuel indirin.")

    def reject(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.cancel()
        super().reject()
