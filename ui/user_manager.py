# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import json
import shutil
import hashlib
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QFormLayout,
    QCheckBox, QComboBox, QInputDialog, QTabWidget, QFileDialog, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QSize

import db
from utils import settings as appset


# =========================
# Yardımcı: UI/Validation
# =========================
def _info(parent, title: str, text: str):
    QMessageBox.information(parent, title, text)

def _warn(parent, title: str, text: str):
    QMessageBox.warning(parent, title, text)

def _err(parent, title: str, text: str):
    QMessageBox.critical(parent, title, text)

def _ask_yes_no(parent, title: str, text: str) -> bool:
    return QMessageBox.question(parent, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class PasswordPolicy:
    min_len: int = 6
    require_upper: bool = False
    require_lower: bool = False
    require_digit: bool = False
    require_symbol: bool = False

    def validate(self, password: str) -> Tuple[bool, str]:
        p = password or ""
        if len(p) < self.min_len:
            return False, f"Şifre en az {self.min_len} karakter olmalı."
        if self.require_upper and not re.search(r"[A-ZÇĞİÖŞÜ]", p):
            return False, "Şifre en az 1 büyük harf içermeli."
        if self.require_lower and not re.search(r"[a-zçğıöşü]", p):
            return False, "Şifre en az 1 küçük harf içermeli."
        if self.require_digit and not re.search(r"\d", p):
            return False, "Şifre en az 1 rakam içermeli."
        if self.require_symbol and not re.search(r"[^\w\s]", p):
            return False, "Şifre en az 1 sembol içermeli."
        return True, "OK"


class UserManagerDialog(QWidget):
    """
    Yönetici Paneli:
    - Kullanıcılar ve Roller
    - Erişim ve Güvenlik
    - Bakım ve Yedekleme
    - Genel Ayarlar

    Not: Mevcut veritabanı/uygulama yapısını bozmaz. Sadece db/appset üzerinden okur-yazar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yönetim Paneli")
        self.resize(900, 600)

        # Çalışma değişkenleri
        self._users_cache: List[Dict[str, Any]] = []
        self._audit_enabled = True  # UI’dan ayarlanabilir (Genel Ayarlar)
        self._policy = self._load_password_policy()

        try:
            self._ensure_users_table()  # <--- FIX
            self._init_ui()
            self._load_users()
            self._load_security_settings()
            self._load_general_settings()
        except Exception as e:
            _err(self, "Hata", f"Panel yüklenirken hata oluştu:\n{e}")

    def _ensure_users_table(self):
        """Kullanıcı tablosunu oluşturur (yoksa)."""
        try:
            con = db.get_conn()
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cur.fetchone():
                cur.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now'))
                )""")
                # Varsayılan admin
                h = hashlib.sha256("admin".encode()).hexdigest()
                try:
                    cur.execute("INSERT INTO users(username, password_hash, role, active) VALUES(?, ?, ?, 1)", ('admin', h, 'admin'))
                except:
                    pass
                con.commit()
            con.close()
        except:
            pass

    # ======================================================
    # UI
    # ======================================================
    def _init_ui(self):
        # --- Modern & Profesyonel Stil (mevcut stil korunur/iyileştirilir) ---
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; color: #333; }
            QTabWidget::pane { border: 1px solid #ddd; background: #fff; border-radius: 4px; top: -1px; }
            QTabBar::tab {
                background: #f1f3f5; border: 1px solid #ddd; padding: 10px 20px; font-weight: bold; color: #555;
                border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
            }
            QTabBar::tab:selected { background: #fff; border-bottom-color: #fff; color: #007bff; }
            QTabBar::tab:hover { background: #e9ecef; }

            QGroupBox { font-weight: bold; border: 1px solid #e0e0e0; border-radius: 6px; margin-top: 20px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #007bff; }

            QPushButton {
                background-color: #f8f9fa; border: 1px solid #ced4da; padding: 6px 12px; border-radius: 4px; font-weight: 600;
            }
            QPushButton:hover { background-color: #e2e6ea; }
            QPushButton#btnPrimary { background-color: #007bff; color: white; border: none; }
            QPushButton#btnPrimary:hover { background-color: #0056b3; }
            QPushButton#btnDanger { background-color: #dc3545; color: white; border: none; }
            QPushButton#btnDanger:hover { background-color: #bd2130; }
            QPushButton#btnSuccess { background-color: #28a745; color: white; border: none; }
            QPushButton#btnSuccess:hover { background-color: #218838; }

            QLineEdit, QComboBox { padding: 6px; border: 1px solid #ced4da; border-radius: 4px; }
            QLineEdit:focus, QComboBox:focus { border-color: #80bdff; }

            QTableWidget { border: 1px solid #dee2e6; gridline-color: #f1f3f5; selection-background-color: #e7f1ff; selection-color: #0056b3; }
            QHeaderView::section { background-color: #f8f9fa; padding: 6px; border: none; font-weight: bold; border-bottom: 1px solid #dee2e6; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Üst Başlık
        header = QHBoxLayout()
        lbl_title = QLabel("Yönetici Kontrol Paneli")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header.addWidget(lbl_title)

        header.addStretch()

        # Mini durum etiketi + yenile
        self.lbl_status = QLabel("Hazır")
        self.lbl_status.setStyleSheet("color:#64748b;")
        header.addWidget(self.lbl_status)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.clicked.connect(self._refresh_all)
        header.addWidget(btn_refresh)

        layout.addLayout(header)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(20, 20))

        # Sekmeler
        self.tab_users = QWidget()
        self.tab_security = QWidget()
        self.tab_maintenance = QWidget()
        self.tab_general = QWidget()

        self.tabs.addTab(self.tab_users, "👥 Kullanıcılar ve Roller")
        self.tabs.addTab(self.tab_security, "🔐 Erişim ve Güvenlik")
        self.tabs.addTab(self.tab_maintenance, "🛠️ Bakım ve Yedekleme")
        self.tabs.addTab(self.tab_general, "⚙️ Genel Ayarlar")

        layout.addWidget(self.tabs)

        # Init Tabs
        self._init_tab_users()
        self._init_tab_security()
        self._init_tab_maintenance()
        self._init_tab_general()

    # ======================================================
    # TAB 1: KULLANICILAR
    # ======================================================
    def _init_tab_users(self):
        lay = QHBoxLayout(self.tab_users)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(20)

        # SOL: Liste
        left_layout = QVBoxLayout()

        # Arama/Filtre bar (EKSTRA - yapıyı bozmaz)
        filter_bar = QHBoxLayout()
        self.txt_user_search = QLineEdit()
        self.txt_user_search.setPlaceholderText("Kullanıcı ara (adı/rol/durum)...")
        self.txt_user_search.textChanged.connect(self._apply_user_filter)
        filter_bar.addWidget(self.txt_user_search)

        self.cmb_role_filter = QComboBox()
        self.cmb_role_filter.addItem("Tümü", "")
        self.cmb_role_filter.addItem("Admin", "admin")
        self.cmb_role_filter.addItem("User", "user")
        self.cmb_role_filter.currentIndexChanged.connect(self._apply_user_filter)
        filter_bar.addWidget(self.cmb_role_filter)

        btn_export = QPushButton("⬇️ Dışa Aktar (JSON)")
        btn_export.clicked.connect(self._export_users_json)
        filter_bar.addWidget(btn_export)

        btn_import = QPushButton("⬆️ İçe Aktar (JSON)")
        btn_import.clicked.connect(self._import_users_json)
        filter_bar.addWidget(btn_import)

        left_layout.addLayout(filter_bar)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(4)
        self.table_users.setHorizontalHeaderLabels(["ID", "Kullanıcı Adı", "Rol", "Durum"])
        self.table_users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_users.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_users.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_users.verticalHeader().setVisible(False)
        self.table_users.setAlternatingRowColors(True)
        self.table_users.itemSelectionChanged.connect(self._on_user_selected)
        left_layout.addWidget(self.table_users)

        # Mini özet
        self.lbl_user_summary = QLabel("")
        self.lbl_user_summary.setStyleSheet("color:#64748b;")
        left_layout.addWidget(self.lbl_user_summary)

        lay.addLayout(left_layout, 2)

        # SAĞ: İşlemler
        right_layout = QVBoxLayout()

        # Seçili kullanıcı işlemleri
        grp_actions = QGroupBox("Seçili Kullanıcı İşlemleri")
        v_act = QVBoxLayout(grp_actions)

        self.btn_pass = QPushButton("🔑 Şifre Değiştir")
        self.btn_pass.clicked.connect(self._user_change_pass)
        v_act.addWidget(self.btn_pass)

        self.btn_role = QPushButton("🛡️ Rol Değiştir")
        self.btn_role.clicked.connect(self._user_change_role)
        v_act.addWidget(self.btn_role)

        self.btn_toggle = QPushButton("⏸️ Aktif/Pasif")
        self.btn_toggle.clicked.connect(self._user_toggle_active)
        v_act.addWidget(self.btn_toggle)

        self.btn_del = QPushButton("🗑️ Kullanıcıyı Sil")
        self.btn_del.setObjectName("btnDanger")
        self.btn_del.clicked.connect(self._user_delete)
        v_act.addWidget(self.btn_del)

        # Güvenli reset
        self.btn_reset = QPushButton("♻️ Şifre Sıfırla (Geçici)")
        self.btn_reset.clicked.connect(self._user_reset_password_temp)
        v_act.addWidget(self.btn_reset)

        right_layout.addWidget(grp_actions)

        # Yeni kullanıcı ekle
        grp_add = QGroupBox("Yeni Kullanıcı Ekle")
        f_add = QFormLayout(grp_add)

        self.txtNewUser = QLineEdit()
        self.txtNewUser.setPlaceholderText("ör: admin, ogretmen1 ...")
        self.txtNewPass = QLineEdit()
        self.txtNewPass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txtNewPass.setPlaceholderText("••••••")

        self.cmbNewRole = QComboBox()
        self.cmbNewRole.addItem("👤 Standart Kullanıcı", "user")
        self.cmbNewRole.addItem("🛡️ Yönetici (Admin)", "admin")

        f_add.addRow("Kullanıcı Adı:", self.txtNewUser)
        f_add.addRow("Şifre:", self.txtNewPass)
        f_add.addRow("Rol:", self.cmbNewRole)

        btn_add = QPushButton("✅ Kullanıcı Ekle")
        btn_add.setObjectName("btnSuccess")
        btn_add.clicked.connect(self._user_add)
        f_add.addRow(btn_add)

        # Hızlı öneri
        self.lbl_user_hint = QLabel("💡 İpucu: Admin sayısını az tut, günlük kullanım için user rolü kullan.")
        self.lbl_user_hint.setStyleSheet("color:#64748b; font-size:11px;")
        f_add.addRow(self.lbl_user_hint)

        right_layout.addWidget(grp_add)
        right_layout.addStretch()

        lay.addLayout(right_layout, 1)

        self._set_user_actions_enabled(False)

    def _set_user_actions_enabled(self, enabled: bool):
        for b in [self.btn_pass, self.btn_role, self.btn_toggle, self.btn_del, self.btn_reset]:
            b.setEnabled(enabled)

    def _on_user_selected(self):
        row = self._selected_user_row()
        self._set_user_actions_enabled(row is not None)

    def _selected_user_row(self) -> Optional[int]:
        rows = self.table_users.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _selected_user_id(self) -> Optional[int]:
        r = self._selected_user_row()
        if r is None:
            return None
        try:
            return int(self.table_users.item(r, 0).text())
        except:
            return None

    # ======================================================
    # TAB 2: GÜVENLİK (mevcut mantık korunur)
    # ======================================================
    def _init_tab_security(self):
        lay = QVBoxLayout(self.tab_security)
        lay.setContentsMargins(20, 20, 20, 20)

        grp_login = QGroupBox("Giriş Politikası")
        f_login = QFormLayout(grp_login)
        f_login.setSpacing(15)

        self.chkEnableLogin = QCheckBox("Program açılışında kimlik doğrulama iste")
        self.chkEnableLogin.setStyleSheet("font-size: 14px;")
        f_login.addRow(self.chkEnableLogin)

        f_login.addRow(QLabel("<hr>"))

        self.cmbLoginMode = QComboBox()
        self.cmbLoginMode.addItem("👤 Her kullanıcı kendi şifresiyle girsin (Önerilen)", "user_pass")
        self.cmbLoginMode.addItem("🔑 Tek bir ortak şifre ile giriş yapılsın", "pass_only")
        self.cmbLoginMode.currentIndexChanged.connect(self._sec_mode_changed)
        f_login.addRow("Giriş Yöntemi:", self.cmbLoginMode)

        self.txtSystemPass = QLineEdit()
        self.txtSystemPass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txtSystemPass.setPlaceholderText("Sadece 'Ortak Şifre' modunda gereklidir")
        f_login.addRow("Ortak Şifre:", self.txtSystemPass)

        # EKSTRA: parola politikası özeti (bozmaz)
        self.lbl_policy = QLabel("")
        self.lbl_policy.setStyleSheet("color:#64748b; font-size:11px;")
        f_login.addRow("Şifre Politikası:", self.lbl_policy)
        self._render_policy_label()

        btn_save_sec = QPushButton("Ayarları Kaydet")
        btn_save_sec.setObjectName("btnPrimary")
        btn_save_sec.setFixedWidth(150)
        btn_save_sec.clicked.connect(self._save_security)
        f_login.addRow("", btn_save_sec)

        lay.addWidget(grp_login)
        lay.addStretch()

    def _sec_mode_changed(self, idx):
        mode = self.cmbLoginMode.currentData()
        is_pass_only = (mode == "pass_only")
        self.txtSystemPass.setEnabled(is_pass_only)
        if is_pass_only:
            self.txtSystemPass.setPlaceholderText("Değiştirmek için yeni şifreyi girin")
        else:
            self.txtSystemPass.setPlaceholderText("Sadece 'Ortak Şifre' modunda aktiftir")

    def _load_security_settings(self):
        try:
            val_enable = appset.ayar_get("enable_login", "1")
            self.chkEnableLogin.setChecked(str(val_enable) == "1")

            val_mode = appset.ayar_get("login_mode", "user_pass")
            idx = self.cmbLoginMode.findData(val_mode)
            if idx >= 0:
                self.cmbLoginMode.setCurrentIndex(idx)

            self._sec_mode_changed(0)
        except:
            pass

    def _save_security(self):
        try:
            # Enable Login
            val_enable = "1" if self.chkEnableLogin.isChecked() else "0"
            appset.ayar_set("enable_login", val_enable)

            # Login Mode
            val_mode = self.cmbLoginMode.currentData()
            appset.ayar_set("login_mode", val_mode)

            # System Password (only pass_only)
            if val_mode == "pass_only":
                sys_pass = self.txtSystemPass.text().strip()
                if sys_pass:
                    ok, msg = self._policy.validate(sys_pass)
                    if not ok:
                        _warn(self, "Şifre Politikası", msg)
                        return
                    appset.ayar_set("system_password_hash", _sha256(sys_pass))
                    _info(self, "Güvenlik", "Ortak şifre güncellendi.")

            _info(self, "Başarılı", "Güvenlik ayarları kaydedildi.\nDeğişiklikler bir sonraki girişte geçerli olacak.")
            self._audit("security_save", {"enable_login": val_enable, "login_mode": val_mode})
        except Exception as e:
            _err(self, "Hata", str(e))

    # ======================================================
    # TAB 3: BAKIM & YEDEKLEME (geliştirilmiş)
    # ======================================================
    def _init_tab_maintenance(self):
        lay = QVBoxLayout(self.tab_maintenance)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(20)

        # Yedekleme
        grp_backup = QGroupBox("Veritabanı Yedekleme")
        v_back = QVBoxLayout(grp_backup)
        v_back.setSpacing(10)

        lbl_info = QLabel("Verilerinizi düzenli olarak yedeklemeniz önerilir. Yedek dosyası .db veya .zip olarak kaydedilebilir.")
        lbl_info.setStyleSheet("color:#475569;")
        v_back.addWidget(lbl_info)

        row = QHBoxLayout()
        btn_backup = QPushButton("💾 Yedek Al")
        btn_backup.setObjectName("btnPrimary")
        btn_backup.clicked.connect(self._backup_db)
        row.addWidget(btn_backup)

        btn_backup_zip = QPushButton("🗜️ Sıkıştırılmış Yedek (ZIP)")
        btn_backup_zip.clicked.connect(self._backup_db_zip)
        row.addWidget(btn_backup_zip)

        btn_restore = QPushButton("♻️ Yedekten Geri Yükle")
        btn_restore.setObjectName("btnDanger")
        btn_restore.clicked.connect(self._restore_db)
        row.addWidget(btn_restore)

        row.addStretch()
        v_back.addLayout(row)

        # Bakım
        grp_clean = QGroupBox("Bakım Araçları")
        v_clean = QVBoxLayout(grp_clean)

        btn_clean = QPushButton("🧹 Geçici Dosyaları Temizle")
        btn_clean.clicked.connect(self._clean_temp_files)
        v_clean.addWidget(btn_clean)

        btn_integrity = QPushButton("🧪 Veritabanı Bütünlük Kontrolü")
        btn_integrity.clicked.connect(self._db_integrity_check)
        v_clean.addWidget(btn_integrity)

        btn_vacuum = QPushButton("⚡ Performans İyileştir (VACUUM)")
        btn_vacuum.clicked.connect(self._db_vacuum)
        v_clean.addWidget(btn_vacuum)

        self.prg_maint = QProgressBar()
        self.prg_maint.setRange(0, 100)
        self.prg_maint.setValue(0)
        v_clean.addWidget(self.prg_maint)

        lay.addWidget(grp_backup)
        lay.addWidget(grp_clean)
        lay.addStretch()

    def _get_db_path(self) -> Optional[str]:
        # Öncelik: db.DB_PATH (Path objesi olabilir)
        if hasattr(db, "DB_PATH"):
            return str(db.DB_PATH)

        # Legacy: DB_NAME_FILE
        db_path = "data.db"
        if hasattr(db, "DB_NAME_FILE"):
            try:
                db_path = getattr(db, "DB_NAME_FILE")
            except:
                pass
        return db_path

    def _backup_db(self):
        try:
            db_path = self._get_db_path()
            if not db_path or not os.path.exists(db_path):
                _warn(self, "Hata", "Veritabanı dosyası bulunamadı.")
                return

            def_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
            path, _ = QFileDialog.getSaveFileName(self, "Yedek Kaydet", def_name, "SQLite Database (*.db)")
            if not path:
                return

            self.prg_maint.setValue(15)
            shutil.copy2(db_path, path)
            self.prg_maint.setValue(90)

            # Mini doğrulama
            ok, msg = self._quick_sqlite_check(path)
            self.prg_maint.setValue(100)

            if ok:
                _info(self, "Başarılı", f"Yedekleme tamamlandı:\n{path}")
            else:
                _warn(self, "Uyarı", f"Yedek alındı ama doğrulama uyarısı:\n{msg}\n\nDosya: {path}")

            self._audit("backup_db", {"dest": path, "ok": ok, "msg": msg})
        except Exception as e:
            self.prg_maint.setValue(0)
            _err(self, "Hata", f"Yedekleme başarısız: {e}")

    def _backup_db_zip(self):
        try:
            db_path = self._get_db_path()
            if not db_path or not os.path.exists(db_path):
                _warn(self, "Hata", "Veritabanı dosyası bulunamadı.")
                return

            def_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
            path, _ = QFileDialog.getSaveFileName(self, "Sıkıştırılmış Yedek Kaydet", def_name, "ZIP (*.zip)")
            if not path:
                return

            self.prg_maint.setValue(10)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_path, arcname=os.path.basename(db_path))
            self.prg_maint.setValue(100)

            _info(self, "Başarılı", f"Sıkıştırılmış yedek tamamlandı:\n{path}")
            self._audit("backup_zip", {"dest": path})
        except Exception as e:
            self.prg_maint.setValue(0)
            _err(self, "Hata", f"ZIP yedek başarısız: {e}")

    def _restore_db(self):
        try:
            db_path = self._get_db_path()
            if not db_path:
                _warn(self, "Hata", "Veritabanı yolu belirlenemedi.")
                return

            if not _ask_yes_no(self, "Dikkat", "Geri yükleme mevcut veritabanının ÜZERİNE yazacaktır.\nDevam edilsin mi?"):
                return

            path, _ = QFileDialog.getOpenFileName(self, "Yedek Seç", "", "SQLite/ZIP (*.db *.zip)")
            if not path:
                return

            self.prg_maint.setValue(10)

            tmp_db = None
            if path.lower().endswith(".zip"):
                # zip içinden db çıkar
                with zipfile.ZipFile(path, "r") as zf:
                    members = [m for m in zf.namelist() if m.lower().endswith(".db")]
                    if not members:
                        _warn(self, "Hata", "ZIP içinde .db dosyası bulunamadı.")
                        return
                    tmp_db = os.path.join(os.path.dirname(db_path), f"__tmp_restore_{int(datetime.now().timestamp())}.db")
                    zf.extract(members[0], path=os.path.dirname(tmp_db))
                    extracted = os.path.join(os.path.dirname(tmp_db), members[0])
                    shutil.move(extracted, tmp_db)
            else:
                tmp_db = path

            self.prg_maint.setValue(40)

            ok, msg = self._quick_sqlite_check(tmp_db)
            if not ok:
                _warn(self, "Hata", f"Seçilen dosya SQLite olarak doğrulanamadı:\n{msg}")
                if path.lower().endswith(".zip") and tmp_db and os.path.exists(tmp_db):
                    os.remove(tmp_db)
                return

            # önce mevcut db’yi güvenli bir yere al
            backup_current = f"{db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(db_path):
                shutil.copy2(db_path, backup_current)

            self.prg_maint.setValue(70)

            # restore
            shutil.copy2(tmp_db, db_path)

            self.prg_maint.setValue(100)
            _info(self, "Başarılı", "Geri yükleme tamamlandı.\nUygulamayı yeniden başlatmanız önerilir.")

            self._audit("restore_db", {"source": path, "saved_prev": backup_current})

            # temp sil
            if path.lower().endswith(".zip") and tmp_db and os.path.exists(tmp_db):
                os.remove(tmp_db)

            # UI yenile
            self._refresh_all()
        except Exception as e:
            self.prg_maint.setValue(0)
            _err(self, "Hata", f"Geri yükleme başarısız: {e}")

    def _clean_temp_files(self):
        try:
            from pathlib import Path
            
            if not _ask_yes_no(self, "Onay", "Geçici dosyalar (Loglar, Önbellek) silinecek.\nDevam edilsin mi?"):
                 return

            self.prg_maint.setValue(10)
            total_deleted = 0
            total_size_bytes = 0
            
            # 1. Clean logs (keep last 5 for safety)
            log_dir = Path("logs")
            if log_dir.exists():
                all_logs = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
                # İlk 5 tanesini tut, gerisini sil
                to_delete = all_logs[5:]
                for f in to_delete:
                    try:
                        sz = f.stat().st_size
                        f.unlink()
                        total_deleted += 1
                        total_size_bytes += sz
                    except: pass
            
            self.prg_maint.setValue(40)

            # 2. Clean __pycache__ recursive
            root_dir = Path(".")
            # rglob generator olduğu için listeye çevirip iterate edelim (veya direkt)
            # DİKKAT: .venv içini silmemeli!
            for p in root_dir.rglob("__pycache__"):
                # .venv veya env klasörleri içindeyse atla
                if ".venv" in str(p) or "env" in str(p) or "venv" in str(p):
                    continue
                
                if p.is_dir():
                    try:
                        # calculate size
                        for sub in p.rglob("*"):
                            if sub.is_file():
                                total_size_bytes += sub.stat().st_size
                                total_deleted += 1
                        shutil.rmtree(p)
                    except: pass
            
            self.prg_maint.setValue(80)
            
            # 3. Clean .DS_Store
            for p in root_dir.rglob(".DS_Store"):
                try:
                    p.unlink()
                    total_deleted += 1
                except: pass

            self.prg_maint.setValue(100)

            # Convert to readable size
            size_mb = total_size_bytes / (1024*1024)
            msg = f"Temizlik Tamamlandı. 🧹\n\nSilinen Dosya: {total_deleted}\nKazanılan Alan: {size_mb:.2f} MB"
            _info(self, "Temizlik", msg)
            self._audit("clean_temp", {"deleted": total_deleted, "bytes": total_size_bytes})
            
        except Exception as e:
             _err(self, "Hata", f"Temizlik sırasında hata: {e}")
             self.prg_maint.setValue(0)

    def _quick_sqlite_check(self, path: str) -> Tuple[bool, str]:
        # sqlite header kontrolü (hızlı)
        try:
            with open(path, "rb") as f:
                head = f.read(16)
            if head != b"SQLite format 3\x00":
                return False, "Dosya SQLite header taşımıyor."
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def _db_integrity_check(self):
        try:
            con = db.get_conn()
            self.prg_maint.setValue(20)
            cur = con.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()
            self.prg_maint.setValue(100)
            con.close()

            msg = res[0] if res else "unknown"
            if str(msg).lower() == "ok":
                _info(self, "Bütünlük Kontrolü", "✅ integrity_check: OK\nVeritabanı sağlam görünüyor.")
            else:
                _warn(self, "Bütünlük Kontrolü", f"⚠️ integrity_check sonucu:\n{msg}\n\nYedek alıp geri yükleme düşünebilirsin.")
            self._audit("integrity_check", {"result": msg})
        except Exception as e:
            self.prg_maint.setValue(0)
            _err(self, "Hata", f"Bütünlük kontrolü başarısız: {e}")

    def _db_vacuum(self):
        # veri yapısını bozmaz; SQLite bakım komutu
        try:
            if not _ask_yes_no(self, "VACUUM", "VACUUM işleminde veritabanı kısa süre kilitlenebilir.\nDevam edilsin mi?"):
                return
            con = db.get_conn()
            self.prg_maint.setValue(10)
            cur = con.cursor()
            cur.execute("VACUUM;")
            con.commit()
            con.close()
            self.prg_maint.setValue(100)
            _info(self, "Başarılı", "VACUUM tamamlandı. Veritabanı optimize edildi.")
            self._audit("vacuum", {})
        except Exception as e:
            self.prg_maint.setValue(0)
            _err(self, "Hata", f"VACUUM başarısız: {e}")

    # ======================================================
    # TAB 4: GENEL (mevcut ayar korunur + ekstra)
    # ======================================================
    def _init_tab_general(self):
        lay = QVBoxLayout(self.tab_general)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)

        grp = QGroupBox("Kurum Bilgileri")
        f = QFormLayout(grp)
        f.setSpacing(12)

        self.txtInstitutionName = QLineEdit()
        self.txtInstitutionName.setPlaceholderText("ör: Özel XYZ Kursu")
        f.addRow("Kurum Adı:", self.txtInstitutionName)

        btn_save = QPushButton("Kaydet")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save_general)
        f.addRow("", btn_save)

        lay.addWidget(grp)

        grp2 = QGroupBox("Gelişmiş Ayarlar")
        f2 = QFormLayout(grp2)
        f2.setSpacing(12)

        self.chkAudit = QCheckBox("İşlem kayıtlarını (audit log) tut")
        self.chkAudit.stateChanged.connect(self._toggle_audit)
        f2.addRow(self.chkAudit)

        # Şifre politikası (ayarlanabilir)
        self.sp_minlen = QComboBox()
        for v in [4, 6, 8, 10, 12]:
            self.sp_minlen.addItem(str(v), v)

        self.chk_up = QCheckBox("Büyük harf zorunlu")
        self.chk_lo = QCheckBox("Küçük harf zorunlu")
        self.chk_dg = QCheckBox("Rakam zorunlu")
        self.chk_sy = QCheckBox("Sembol zorunlu")

        f2.addRow("Minimum Şifre Uzunluğu:", self.sp_minlen)
        f2.addRow(self.chk_up)
        f2.addRow(self.chk_lo)
        f2.addRow(self.chk_dg)
        f2.addRow(self.chk_sy)

        btn_save_policy = QPushButton("Şifre Politikasını Kaydet")
        btn_save_policy.clicked.connect(self._save_password_policy)
        f2.addRow("", btn_save_policy)

        lay.addWidget(grp2)
        lay.addStretch()

    def _load_general_settings(self):
        try:
            name = appset.ayar_get("kurum_adi", "")
            self.txtInstitutionName.setText(name)
        except:
            pass

        # audit ayarı
        try:
            v = appset.ayar_get("audit_enabled", "1")
            self._audit_enabled = (str(v) != "0")
            self.chkAudit.setChecked(self._audit_enabled)
        except:
            pass

        # policy UI
        self._policy = self._load_password_policy()
        self._sync_policy_ui()

    def _save_general(self):
        try:
            name = self.txtInstitutionName.text().strip()
            appset.ayar_set("kurum_adi", name)
            _info(self, "Başarılı", "Kurum bilgileri güncellendi.")
            self._audit("general_save", {"kurum_adi": name})
        except Exception as e:
            _err(self, "Hata", str(e))

    def _toggle_audit(self):
        self._audit_enabled = self.chkAudit.isChecked()
        try:
            appset.ayar_set("audit_enabled", "1" if self._audit_enabled else "0")
        except:
            pass

    # ======================================================
    # Kullanıcı İşlemleri (DB'yi bozmaz: varsa kullan)
    # ======================================================
    def _load_users(self):
        """
        DB’den kullanıcıları çek.
        """
        self.lbl_status.setText("Kullanıcılar yükleniyor...")
        self._users_cache = []
        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            # 1) Olası tablolar: users / kullanici / kullanicilar
            candidates = [
                ("users", ["id", "username", "role", "active"]),
                ("kullanicilar", ["id", "kullanici_adi", "rol", "aktif"]),
                ("kullanici", ["id", "kullanici_adi", "rol", "aktif"]),
            ]

            rows = None
            used = None
            
            # İlk deneme
            for table, cols in candidates:
                try:
                    q = f"SELECT {', '.join(cols)} FROM {table} ORDER BY 1 DESC"
                    cur.execute(q)
                    rows = cur.fetchall()
                    used = (table, cols)
                    break
                except:
                    continue
            
            # Eğer tablo bulunamadıysa, oluşturmayı dene ve tekrar oku
            if rows is None:
                # Conn kapat
                try: con.close()
                except: pass
                
                # Tabloyu garantiye al (Yeni bağlantı açıp kapatır)
                self._ensure_users_table()
                
                # Yeni bağlantı aç
                con = db.get_conn()
                cur = con.cursor()
                
                # Tekrar dene
                for table, cols in candidates:
                    try:
                        q = f"SELECT {', '.join(cols)} FROM {table} ORDER BY 1 DESC"
                        cur.execute(q)
                        rows = cur.fetchall()
                        used = (table, cols)
                        break
                    except:
                        continue

            if rows is None:
                # Hala yoksa
                try:
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tbls = [r[0] for r in cur.fetchall()]
                    _warn(self, "Uyarı", f"Kullanıcı tablosu oluşturulamadı ve bulunamadı.\nMevcut tablolar:\n- " + "\n- ".join(tbls[:20]))
                except:
                    _warn(self, "Uyarı", "Kullanıcı tablosu bulunamadı.")
                self._render_users_table([])
                return

            table, cols = used

            for r in rows:
                d = {}
                for i, c in enumerate(cols):
                    d[c] = r[i]
                uid = int(d.get("id", 0) or 0)
                uname = d.get("username") or d.get("kullanici_adi") or ""
                role = d.get("role") or d.get("rol") or "user"
                active = d.get("active")
                if active is None:
                    active = d.get("aktif", 1)
                active = int(active or 0)
                self._users_cache.append({
                    "id": uid,
                    "username": str(uname),
                    "role": str(role),
                    "active": 1 if active else 0,
                    "_table": table,
                    "_cols": cols
                })

            self._render_users_table(self._users_cache)
            self._apply_user_filter()
            self.lbl_status.setText("Hazır")
        except Exception as e:
            self.lbl_status.setText("Hata")
            _err(self, "Hata", f"Kullanıcılar yüklenemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _ensure_users_table(self):
        """Kullanıcı tablosunu oluşturur ve sütunları kontrol eder."""
        try:
            con = db.get_conn()
            cur = con.cursor()
            
            # Doğrudan oluşturmayı dene (IF NOT EXISTS)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            )""")
            
            # Eğer tablo önceden varsa ama sütunlar eksikse (örn: active)
            # Basitçe alter table ile eklemeyi dene (hata verirse yoksay - zaten vardır)
            try:
                cur.execute("ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1")
            except:
                pass # Zaten varsa hata verir

            # Varsayılan admin
            # Güvenlik için: eğer hiç kullanıcı yoksa ekle
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                h = hashlib.sha256("admin".encode()).hexdigest()
                try:
                    cur.execute("INSERT INTO users(username, password_hash, role, active) VALUES(?, ?, ?, 1)", ('admin', h, 'admin'))
                except:
                    pass
            
            con.commit()
            con.close()
        except Exception as e:
            QMessageBox.critical(self, "Tablo Oluşturma Hatası", f"Users tablosu işlemlerinde hata:\n{e}")

    def _render_users_table(self, users: List[Dict[str, Any]]):
        self.table_users.setRowCount(0)
        for u in users:
            r = self.table_users.rowCount()
            self.table_users.insertRow(r)

            it_id = QTableWidgetItem(str(u.get("id", "")))
            it_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            it_user = QTableWidgetItem(str(u.get("username", "")))

            raw_role = str(u.get("role", "")).lower()
            if "admin" in raw_role:
                role_txt = "🛡️ Yönetici (Admin)"
            elif "koc" in raw_role or "coach" in raw_role:
                role_txt = "🎓 Eğitim Koçu"
            elif "ogretmen" in raw_role or "teacher" in raw_role:
                role_txt = "👨‍🏫 Öğretmen"
            else:
                role_txt = "👤 Kullanıcı"
            it_role = QTableWidgetItem(role_txt)

            active = int(u.get("active", 1) or 0)
            status_txt = "🟢 Aktif" if active else "🔴 Pasif"
            it_status = QTableWidgetItem(status_txt)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Görsel ipucu
            if not active:
                it_user.setForeground(Qt.GlobalColor.gray)
                it_role.setForeground(Qt.GlobalColor.gray)

            self.table_users.setItem(r, 0, it_id)
            self.table_users.setItem(r, 1, it_user)
            self.table_users.setItem(r, 2, it_role)
            self.table_users.setItem(r, 3, it_status)

        self._update_user_summary(users)

    def _update_user_summary(self, users: List[Dict[str, Any]]):
        total = len(users)
        admins = sum(1 for u in users if "admin" in str(u.get("role", "")).lower())
        active_cnt = sum(1 for u in users if int(u.get("active", 1)) == 1)
        inactive = total - active_cnt
        self.lbl_user_summary.setText(f"👥 Toplam: {total}  •  🛡️ Admin: {admins}  •  🟢 Aktif: {active_cnt}  •  🔴 Pasif: {inactive}")

    def _apply_user_filter(self):
        q = (self.txt_user_search.text() or "").strip().lower()
        role = self.cmb_role_filter.currentData() or ""

        def ok(u: Dict[str, Any]) -> bool:
            if role and str(u.get("role", "")) != role:
                return False
            if not q:
                return True
            blob = f"{u.get('username','')} {u.get('role','')} {'aktif' if u.get('active',1) else 'pasif'}".lower()
            return q in blob

        filtered = [u for u in self._users_cache if ok(u)]
        self._render_users_table(filtered)

    def _user_add(self):
        uname = (self.txtNewUser.text() or "").strip()
        pwd = (self.txtNewPass.text() or "").strip()
        role = self.cmbNewRole.currentData() or "user"

        if not uname:
            _warn(self, "Uyarı", "Kullanıcı adı boş olamaz.")
            return

        if not re.match(r"^[a-zA-Z0-9_.-]{3,32}$", uname):
            _warn(self, "Uyarı", "Kullanıcı adı 3-32 karakter olmalı ve sadece harf/rakam/._- içermeli.")
            return

        ok, msg = self._policy.validate(pwd)
        if not ok:
            _warn(self, "Şifre Politikası", msg)
            return

        # mevcut kullanıcı var mı?
        if any(u["username"].lower() == uname.lower() for u in self._users_cache):
            _warn(self, "Uyarı", "Bu kullanıcı adı zaten var.")
            return

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            # tablo tespiti: cache’ten öğren
            table = self._users_cache[0]["_table"] if self._users_cache else "users"
            cols = self._users_cache[0]["_cols"] if self._users_cache else ["id", "username", "role", "active"]

            # insert stratejisi
            # users(id, username, role, active) / kullanicilar(id, kullanici_adi, rol, aktif)
            if "username" in cols:
                cur.execute(f"INSERT INTO {table} (username, role, active) VALUES (?, ?, ?)", (uname, role, 1))
            elif "kullanici_adi" in cols:
                cur.execute(f"INSERT INTO {table} (kullanici_adi, rol, aktif) VALUES (?, ?, ?)", (uname, role, 1))
            else:
                _warn(self, "Uyarı", "Kullanıcı tablosu sütunları tanınamadı. Insert yapılamadı.")
                return

            # şifre alanı varsa yaz
            # olası alanlar: password_hash, sifre_hash, pass_hash
            pw_hash = _sha256(pwd)
            updated = False
            for pw_col in ["password_hash", "sifre_hash", "pass_hash"]:
                try:
                    # yeni eklenen id
                    uid = cur.lastrowid
                    cur.execute(f"UPDATE {table} SET {pw_col}=? WHERE id=?", (pw_hash, uid))
                    updated = True
                    break
                except:
                    continue

            con.commit()

            self.txtNewUser.clear()
            self.txtNewPass.clear()
            _info(self, "Başarılı", "Kullanıcı eklendi.")
            self._audit("user_add", {"username": uname, "role": role, "pwd_col_updated": updated})
            self._load_users()
        except Exception as e:
            _err(self, "Hata", f"Kullanıcı eklenemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _user_change_pass(self):
        uid = self._selected_user_id()
        if uid is None:
            return

        new_pass, ok = QInputDialog.getText(self, "Şifre Değiştir", "Yeni şifre:", echo=QLineEdit.EchoMode.Password)
        if not ok:
            return

        new_pass = (new_pass or "").strip()
        okv, msg = self._policy.validate(new_pass)
        if not okv:
            _warn(self, "Şifre Politikası", msg)
            return

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            table = self._users_cache[0]["_table"] if self._users_cache else "users"
            pw_hash = _sha256(new_pass)

            # password column bul
            pw_cols = ["password_hash", "sifre_hash", "pass_hash"]
            done = False
            for c in pw_cols:
                try:
                    cur.execute(f"UPDATE {table} SET {c}=? WHERE id=?", (pw_hash, uid))
                    done = True
                    break
                except:
                    continue

            if not done:
                _warn(self, "Uyarı", "Şifre sütunu bulunamadı (password_hash/sifre_hash/pass_hash).")
                return

            con.commit()
            _info(self, "Başarılı", "Şifre güncellendi.")
            self._audit("user_change_pass", {"user_id": uid})
        except Exception as e:
            _err(self, "Hata", f"Şifre değiştirilemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _user_change_role(self):
        uid = self._selected_user_id()
        if uid is None:
            return

        role, ok = QInputDialog.getItem(
            self, "Rol Değiştir", "Yeni rol seç:", ["user", "admin"], 0, False
        )
        if not ok:
            return

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            table = self._users_cache[0]["_table"] if self._users_cache else "users"
            cols = self._users_cache[0]["_cols"] if self._users_cache else ["id", "username", "role", "active"]

            # role col
            role_col = "role" if "role" in cols else ("rol" if "rol" in cols else None)
            if not role_col:
                _warn(self, "Uyarı", "Rol sütunu bulunamadı.")
                return

            cur.execute(f"UPDATE {table} SET {role_col}=? WHERE id=?", (role, uid))
            con.commit()

            _info(self, "Başarılı", "Rol güncellendi.")
            self._audit("user_change_role", {"user_id": uid, "role": role})
            self._load_users()
        except Exception as e:
            _err(self, "Hata", f"Rol değiştirilemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _user_toggle_active(self):
        uid = self._selected_user_id()
        if uid is None:
            return

        # mevcut değeri bul
        u = next((x for x in self._users_cache if int(x.get("id", 0)) == int(uid)), None)
        if not u:
            return
        new_val = 0 if int(u.get("active", 1)) == 1 else 1

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            table = u["_table"]
            cols = u["_cols"]
            active_col = "active" if "active" in cols else ("aktif" if "aktif" in cols else None)
            if not active_col:
                _warn(self, "Uyarı", "Aktif/Pasif sütunu bulunamadı.")
                return

            cur.execute(f"UPDATE {table} SET {active_col}=? WHERE id=?", (new_val, uid))
            con.commit()

            _info(self, "Başarılı", "Durum güncellendi.")
            self._audit("user_toggle_active", {"user_id": uid, "active": new_val})
            self._load_users()
        except Exception as e:
            _err(self, "Hata", f"Durum değiştirilemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _user_reset_password_temp(self):
        """
        Güvenli yaklaşım:
        - Rastgele geçici şifre üret
        - Kullanıcıya göster (kopyalayabilsin)
        - Şifreyi hash olarak güncelle (sütun varsa)
        """
        uid = self._selected_user_id()
        if uid is None:
            return

        if not _ask_yes_no(self, "Onay", "Geçici şifre üretilecek ve kullanıcıya verilecektir.\nDevam edilsin mi?"):
            return

        temp = self._generate_temp_password()
        okv, _ = self._policy.validate(temp)
        if not okv:
            # politika çok sıkıysa temp üretimi yeniden
            temp = self._generate_temp_password(strong=True)

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            table = self._users_cache[0]["_table"] if self._users_cache else "users"
            pw_hash = _sha256(temp)

            done = False
            for c in ["password_hash", "sifre_hash", "pass_hash"]:
                try:
                    cur.execute(f"UPDATE {table} SET {c}=? WHERE id=?", (pw_hash, uid))
                    done = True
                    break
                except:
                    continue

            if not done:
                _warn(self, "Uyarı", "Şifre sütunu bulunamadı (password_hash/sifre_hash/pass_hash).")
                return

            con.commit()
            _info(self, "Geçici Şifre", f"Kullanıcıya şu geçici şifreyi ver:\n\n{temp}\n\nİlk girişten sonra değiştirmesi önerilir.")
            self._audit("user_reset_temp", {"user_id": uid})
        except Exception as e:
            _err(self, "Hata", f"Şifre sıfırlanamadı:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    def _generate_temp_password(self, strong: bool = False) -> str:
        import random
        import string
        base = string.ascii_letters + string.digits
        if strong:
            base += "!@#-_+?"
        ln = max(self._policy.min_len, 8 if strong else self._policy.min_len)
        return "".join(random.choice(base) for _ in range(ln))

    def _user_delete(self):
        uid = self._selected_user_id()
        if uid is None:
            return

        if not _ask_yes_no(self, "Dikkat", "Bu kullanıcı silinecek.\nDevam edilsin mi?"):
            return

        con = None
        try:
            con = db.get_conn()
            cur = con.cursor()

            table = self._users_cache[0]["_table"] if self._users_cache else "users"

            # Güvenli silme: önce pasif yapmayı öner
            if _ask_yes_no(self, "Öneri", "Tam silmek yerine pasif yapmayı öneririm.\nPasif yapılsın mı?"):
                # toggle pasif
                u = next((x for x in self._users_cache if int(x.get("id", 0)) == int(uid)), None)
                if u:
                    cols = u["_cols"]
                    active_col = "active" if "active" in cols else ("aktif" if "aktif" in cols else None)
                    if active_col:
                        cur.execute(f"UPDATE {table} SET {active_col}=? WHERE id=?", (0, uid))
                        con.commit()
                        _info(self, "Başarılı", "Kullanıcı pasif yapıldı.")
                        self._audit("user_deactivate_instead_delete", {"user_id": uid})
                        self._load_users()
                        return

            # gerçekten sil
            cur.execute(f"DELETE FROM {table} WHERE id=?", (uid,))
            con.commit()
            _info(self, "Başarılı", "Kullanıcı silindi.")
            self._audit("user_delete", {"user_id": uid})
            self._load_users()
        except Exception as e:
            _err(self, "Hata", f"Kullanıcı silinemedi:\n{e}")
        finally:
            try:
                if con:
                    con.close()
            except:
                pass

    # ======================================================
    # Export / Import (JSON) - ekstra, yapıyı bozmaz
    # ======================================================
    def _export_users_json(self):
        try:
            def_name = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            path, _ = QFileDialog.getSaveFileName(self, "Kullanıcıları Dışa Aktar", def_name, "JSON (*.json)")
            if not path:
                return
            data = [{
                "id": u.get("id"),
                "username": u.get("username"),
                "role": u.get("role"),
                "active": u.get("active"),
            } for u in self._users_cache]

            with open(path, "w", encoding="utf-8") as f:
                json.dump({"exported_at": _now_str(), "users": data}, f, ensure_ascii=False, indent=2)

            _info(self, "Başarılı", f"Dışa aktarıldı:\n{path}")
            self._audit("users_export", {"path": path, "count": len(data)})
        except Exception as e:
            _err(self, "Hata", f"Export başarısız:\n{e}")

    def _import_users_json(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Kullanıcıları İçe Aktar", "", "JSON (*.json)")
            if not path:
                return

            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)

            users = obj.get("users", [])
            if not isinstance(users, list) or not users:
                _warn(self, "Uyarı", "JSON içinde 'users' listesi bulunamadı ya da boş.")
                return

            if not _ask_yes_no(self, "Onay", f"{len(users)} kullanıcı içe aktarılacak.\nAynı kullanıcı adları atlanır.\nDevam edilsin mi?"):
                return

            con = db.get_conn()
            cur = con.cursor()

            table = self._users_cache[0]["_table"] if self._users_cache else "users"
            cols = self._users_cache[0]["_cols"] if self._users_cache else ["id", "username", "role", "active"]

            inserted = 0
            skipped = 0

            for u in users:
                uname = str(u.get("username", "")).strip()
                role = str(u.get("role", "user")).strip() or "user"
                active = int(u.get("active", 1) or 0)

                if not uname:
                    skipped += 1
                    continue
                if any(x["username"].lower() == uname.lower() for x in self._users_cache):
                    skipped += 1
                    continue

                try:
                    if "username" in cols:
                        cur.execute(f"INSERT INTO {table} (username, role, active) VALUES (?, ?, ?)", (uname, role, active))
                    elif "kullanici_adi" in cols:
                        cur.execute(f"INSERT INTO {table} (kullanici_adi, rol, aktif) VALUES (?, ?, ?)", (uname, role, active))
                    else:
                        skipped += 1
                        continue
                    inserted += 1
                except:
                    skipped += 1

            con.commit()
            con.close()

            _info(self, "Tamamlandı", f"İçe aktarma bitti.\nEklenen: {inserted}\nAtlanan: {skipped}")
            self._audit("users_import", {"path": path, "inserted": inserted, "skipped": skipped})
            self._load_users()
        except Exception as e:
            _err(self, "Hata", f"Import başarısız:\n{e}")

    # ======================================================
    # Audit Log (bozmaz: settings + optional file)
    # ======================================================
    def _audit(self, action: str, payload: Dict[str, Any]):
        if not self._audit_enabled:
            return
        try:
            base = appset.ayar_get("audit_log_path", "")
            if not base:
                base = os.path.join(os.path.expanduser("~"), "HomeworkManager_audit.log")
            line = {"ts": _now_str(), "action": action, "payload": payload}
            with open(base, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except:
            pass

    # ======================================================
    # Parola Politikası
    # ======================================================
    def _load_password_policy(self) -> PasswordPolicy:
        try:
            min_len = int(appset.ayar_get("pwd_min_len", 6))
            return PasswordPolicy(
                min_len=min_len,
                require_upper=str(appset.ayar_get("pwd_req_upper", "0")) == "1",
                require_lower=str(appset.ayar_get("pwd_req_lower", "0")) == "1",
                require_digit=str(appset.ayar_get("pwd_req_digit", "0")) == "1",
                require_symbol=str(appset.ayar_get("pwd_req_symbol", "0")) == "1",
            )
        except:
            return PasswordPolicy()

    def _save_password_policy(self):
        try:
            min_len = int(self.sp_minlen.currentData() or 6)
            appset.ayar_set("pwd_min_len", str(min_len))
            appset.ayar_set("pwd_req_upper", "1" if self.chk_up.isChecked() else "0")
            appset.ayar_set("pwd_req_lower", "1" if self.chk_lo.isChecked() else "0")
            appset.ayar_set("pwd_req_digit", "1" if self.chk_dg.isChecked() else "0")
            appset.ayar_set("pwd_req_symbol", "1" if self.chk_sy.isChecked() else "0")

            self._policy = self._load_password_policy()
            self._render_policy_label()

            _info(self, "Başarılı", "Şifre politikası kaydedildi.")
            self._audit("pwd_policy_save", {
                "min_len": self._policy.min_len,
                "upper": self._policy.require_upper,
                "lower": self._policy.require_lower,
                "digit": self._policy.require_digit,
                "symbol": self._policy.require_symbol,
            })
        except Exception as e:
            _err(self, "Hata", f"Şifre politikası kaydedilemedi:\n{e}")

    def _sync_policy_ui(self):
        # minlen
        idx = self.sp_minlen.findData(self._policy.min_len)
        if idx >= 0:
            self.sp_minlen.setCurrentIndex(idx)
        self.chk_up.setChecked(self._policy.require_upper)
        self.chk_lo.setChecked(self._policy.require_lower)
        self.chk_dg.setChecked(self._policy.require_digit)
        self.chk_sy.setChecked(self._policy.require_symbol)
        self._render_policy_label()

    def _render_policy_label(self):
        p = self._policy
        parts = [f"min {p.min_len}"]
        if p.require_upper: parts.append("Büyük Harf")
        if p.require_lower: parts.append("Küçük Harf")
        if p.require_digit: parts.append("Rakam")
        if p.require_symbol: parts.append("Sembol")
        self.lbl_policy.setText(" + ".join(parts))

    # ======================================================
    # Genel Yenile
    # ======================================================
    def _refresh_all(self):
        try:
            self._load_users()
            self._load_security_settings()
            self._load_general_settings()
            self.lbl_status.setText("Güncellendi")
        except Exception as e:
            self.lbl_status.setText("Hata")
            _err(self, "Hata", str(e))
