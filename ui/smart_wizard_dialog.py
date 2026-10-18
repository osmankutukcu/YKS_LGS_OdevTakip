from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListWidget, 
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, 
    QMessageBox, QWidget, QProgressDialog, QScrollArea, QFrame,
    QTabWidget, QTextBrowser, QLineEdit, QSplitter, QSpinBox,
    QProgressBar, QHeaderView, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QColor
from ui.theme import register_theme_listener, readable_text
from ui.theme_tokens_v37 import semantic_palette
from ui.theme_special_v42 import legible_accent
import db
from services.coach_assistant_v1.event_router_v267 import get_coach_router
import random
import json
from html import escape as html_escape
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class _OfficialSourceCheckThread(QThread):
    result_ready = pyqtSignal(object)

    def run(self):
        from services.coach_official_sources import check_official_sources
        self.result_ready.emit(check_official_sources())


class SmartWizardDialog(QDialog):
    """
    Akıllı Ödev Sihirbazı V7: kanıta dayalı, öğretmen onaylı koçluk.
    Gerçek kayıt eksikse iddialı teşhis/ödev üretimi yapılmaz.
    Öğrenci verileri çevrimdışı analiz edilir; çevrimiçi seçenek sadece
    resmî kaynakların başlığını ve erişilebilirliğini kontrol eder.
    """
    def __init__(self, ogrenci_id=None, parent=None, available_books=None):
        super().__init__(parent)
        self.setWindowTitle("🧭 Akıllı Sihirbaz – Koç Özeti V7")
        self.resize(1200, 800)
        from utils.wizard_integrity_v8 import normalized_identity
        self.ogrenci_id = normalized_identity(ogrenci_id)
        self.fixed_student_id = self.ogrenci_id  # Ana formdan açıldıysa değiştirilemez.
        self.transfer_student_id = None
        self._student_scope_error = None
        self.available_books = available_books or {}
        self.suggested_tasks = []
        self.filtered_tasks = []
        self.selected_homeworks = []
        self.current_filter_category = "all"
        self.analytics_data = None
        self.weekly_plan_data = None
        self.coach_brief = None
        self.curriculum_report = None
        self._source_thread = None

        self._build_ui()
        # Passive freshness warning: do not regenerate a teacher-edited draft
        # or change a selected task behind the teacher's back.
        self._coach_router = get_coach_router()
        self._coach_cursor = self._coach_router.cursor
        self._coach_watch_timer = QTimer(self)
        self._coach_watch_timer.setInterval(15000)
        self._coach_watch_timer.timeout.connect(self._check_coach_freshness)
        self._coach_watch_timer.start()
        self._load_students()
        self._on_theme_changed()
        register_theme_listener(self)

        if self.ogrenci_id:
            QTimer.singleShot(400, self._run_analysis)

        self.showMaximized()

    def _on_theme_changed(self):
        c = semantic_palette()
        self._v42_title.setStyleSheet(
            'font-size:20px; font-weight:bold; color:'
            + legible_accent(c['bg'], '#4338CA') + ';')
        self._v42_description.setStyleSheet(
            'font-size:12px; color:'
            + legible_accent(c['bg'], '#64748B') + ';')
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{background:{c['surface']}; border:1px solid {c['border']};
                border-radius:8px; top:-1px;}}
            QTabBar::tab {{background:{c['alt']}; color:{c['alt_fg']};
                border:1px solid {c['border']}; padding:9px 20px;
                font-weight:600; border-radius:8px; margin-right:4px;}}
            QTabBar::tab:selected {{background:{c['surface']};
                color:{c['surface_fg']}; font-weight:bold;}}
            QTabBar::tab:hover:!selected {{background:{c['tab_hover']};
                color:{c['tab_hover_fg']};}}
        """)
        # Reports are authored with many explicit dark HTML colors. Every
        # reader has an explicitly LIGHT document surface to avoid inherited
        # white text from a dark application palette.
        for attr, bg in (
            ('txtEvidence', '#FFFFFF'), ('txtOfficial', '#FFFFFF'),
            ('txtCurriculum', '#FFFFFF'), ('txtStrategy', '#FAFAFA'),
            ('txtPdrSummary', '#FFFFFF'), ('txtWaStudent', '#F0FDF4'),
            ('txtWaParent', '#EFF6FF')):
            browser = getattr(self, attr, None)
            if browser is None:
                continue
            original = getattr(browser, '_v42_base_qss', None)
            if original is None:
                original = browser.styleSheet()
                browser._v42_base_qss = original
            # Existing accent surfaces stay intact. Set readable base color;
            # child HTML can still carry its own semantic warning colors.
            browser.setStyleSheet(
                original + f' background:{bg}; color:{readable_text(bg, "#172033")};'
            )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 12, 15, 12)
        root.setSpacing(10)

        # --- HEADER ---
        header = QHBoxLayout()
        header.setSpacing(12)

        lbl_icon = QLabel("🧙‍♂️")
        lbl_icon.setStyleSheet("font-size: 38px;")

        vbox = QVBoxLayout()
        lbl_title = QLabel("Akıllı Ödev Sihirbazı · Kanıta Dayalı Koç Özeti")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4338ca;")
        lbl_desc = QLabel("Ödev geçmişi • Deneme verisi • Öğretmen onaylı eylemler • İsteğe bağlı resmî kaynaklar")
        lbl_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        self._v42_title = lbl_title
        self._v42_description = lbl_desc
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_desc)

        header.addWidget(lbl_icon)
        header.addLayout(vbox)
        header.addStretch(1)

        # Öğrenci Seçici (Eğer dışarıdan verilmediyse)
        self.cmbStudent = QComboBox()
        self.cmbStudent.setMinimumWidth(220)
        self.cmbStudent.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 12px; font-weight: bold; 
                color: #15191E;}
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 8px; }
        """)
        self.cmbStudent.setEnabled(self.ogrenci_id is None)
        self.cmbStudent.currentIndexChanged.connect(self._on_student_combo_changed)

        header.addWidget(QLabel("<b>Öğrenci:</b>"))
        header.addWidget(self.cmbStudent)
        root.addLayout(header)

        # --- 4 LIVE EXECUTIVE KPI CARDS ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.card_success = self._create_kpi_card("📊 Ödev Tamamlama", "%0", "0/0 Ödev Tamamlandı", "#059669", "#ecfdf5")
        self.card_overdue = self._create_kpi_card("⏳ Geciken / Telafi", "0 Ödev", "Acil Telafi Bekliyor", "#dc2626", "#fef2f2")
        self.card_ebbinghaus = self._create_kpi_card("🧠 Tekrar Adayı", "0 Konu", "Öneridir, ölçüm değildir", "#7c3aed", "#f5f3ff")
        self.card_exam = self._create_kpi_card("📈 Deneme Karşılaştırma", "0 Ders", "Farklı tarihli ölçümler", "#d97706", "#fffbeb")

        kpi_row.addWidget(self.card_success)
        kpi_row.addWidget(self.card_overdue)
        kpi_row.addWidget(self.card_ebbinghaus)
        kpi_row.addWidget(self.card_exam)
        root.addLayout(kpi_row)

        # --- TABS ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 8px; background: white; top: -1px; } 
            QTabBar::tab { background: #f8fafc; border: 1px solid #cbd5e1; padding: 9px 20px; font-weight: 600; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; color: #475569; }
            QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: bold; color: #4338ca; }
        """)

        # Tek bakışta, kanıta dayalı koçluk (öğretmen için ilk ekran)
        self.tabEvidence = QWidget()
        self._build_evidence_tab(self.tabEvidence)
        self.tabs.addTab(self.tabEvidence, "🧭 Koç Özeti (1 Tık)")

        self.tabCurriculum = QWidget()
        self._build_curriculum_tab(self.tabCurriculum)
        self.tabs.addTab(self.tabCurriculum, "📚 Kazanım & Telafi Kontrolü")

        # Tab 1: Akıllı Ödev Önerileri
        self.tabSuggestions = QWidget()
        self._build_suggestions_tab(self.tabSuggestions)
        self.tabs.addTab(self.tabSuggestions, "🎯 Doğrulanmış Ödev Önerileri")

        # Tab 2: Haftalık Strateji (Pro)
        self.tabStrategy = QWidget()
        self._build_strategy_tab(self.tabStrategy)
        self.tabs.addTab(self.tabStrategy, "📅 Haftalık Strateji & Dağılım (Pro)")

        # Tab 3: AI Koçluk & PDR Raporu
        self.tabCoach = QWidget()
        self._build_coach_tab(self.tabCoach)
        self.tabs.addTab(self.tabCoach, "📝 Öğrenci / Veli Mesaj Taslakları")

        root.addWidget(self.tabs, 1)

    def _build_evidence_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        info = QLabel("📌 Kayıtlı ödev ve varsa deneme sonuçlarından otomatik koçluk özeti. "
                      "Öğretmen onayı olmadan ödev veya profil değişmez.")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.txtEvidence = QTextBrowser()
        self.txtEvidence.setHtml("<p>Öğrenci verileri inceleniyor...</p>")
        layout.addWidget(self.txtEvidence, 1)
        actions = QHBoxLayout()
        refresh = QPushButton("🔄 Yeniden İncele")
        refresh.clicked.connect(self._run_analysis)
        actions.addWidget(refresh)
        copy = QPushButton("📋 Koç Özetini Kopyala")
        copy.clicked.connect(self._copy_evidence)
        actions.addWidget(copy)
        actions.addStretch(1)
        layout.addLayout(actions)

        online_info = QLabel("🌐 İnternet modu isteğe bağlıdır. Yalnızca resmî kaynakların sınırlı sayfa verisi "
                             "ve başlığı okunur; öğrenci bilgileri gönderilmez. "
                             "Bu işlem kazanım doğrulaması veya otomatik müfredat eşleştirmesi yapmaz.")
        online_info.setWordWrap(True)
        layout.addWidget(online_info)
        online = QHBoxLayout()
        self.btnOfficial = QPushButton("🌐 Resmî Kaynakları ve Başlıklarını Kontrol Et")
        self.btnOfficial.clicked.connect(self._check_official_sources)
        online.addWidget(self.btnOfficial)
        online.addStretch(1)
        layout.addLayout(online)
        self.txtOfficial = QTextBrowser()
        self.txtOfficial.setMaximumHeight(120)
        self.txtOfficial.setOpenExternalLinks(True)
        self.txtOfficial.setHtml("<i>Çevrimdışı çalışma etkin. İsterseniz tek tıkla resmî kaynakları kontrol edin.</i>")
        layout.addWidget(self.txtOfficial)

    def _build_curriculum_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 14, 16, 14)
        info = QLabel(
            "Yalnızca sınıfı belli olan ve doğrulanmış katalogda tam konu eşleşmesi bulunan "
            "öğrenciler için kontrol taslağı. Deneme neti tek başına kazanım eksiği sayılmaz. "
            "Öneriler öğretmen onayı olmadan hiçbir kaydı değiştirmez.")
        info.setWordWrap(True)
        layout.addWidget(info)
        grade_line = QHBoxLayout()
        grade_line.addWidget(QLabel("Sınıf doğrulaması:"))
        self.cmbCurriculumGrade = QComboBox()
        self.cmbCurriculumGrade.addItem("Öğrencinin kayıtlı sınıfı", None)
        for grade in range(1, 13):
            self.cmbCurriculumGrade.addItem(f"{grade}. sınıf (yalnızca önizleme)", grade)
        self.cmbCurriculumGrade.currentIndexChanged.connect(self._run_curriculum_review)
        grade_line.addWidget(self.cmbCurriculumGrade)
        grade_line.addStretch(1)
        layout.addLayout(grade_line)
        self.txtCurriculum = QTextBrowser()
        self.txtCurriculum.setOpenExternalLinks(True)
        self.txtCurriculum.setHtml("<p>Kazanım kontrolü için öğrenci seçiniz.</p>")
        layout.addWidget(self.txtCurriculum, 1)
        line = QHBoxLayout()
        refresh = QPushButton("🔎 Kazanım Kontrolünü Yenile")
        refresh.clicked.connect(self._run_curriculum_review)
        line.addWidget(refresh)
        copy = QPushButton("📋 Kontrol Taslağını Kopyala")
        copy.clicked.connect(self._copy_curriculum_review)
        line.addWidget(copy)
        line.addStretch(1)
        layout.addLayout(line)
        foot = QLabel(
            "Katalog şu anda sadece kaynaklı örnek Fizik kazanımlarını kapsıyor; "
            "tüm sınıf ve dersler için otomatik doğrulama iddiası yoktur. "
            "Resmî öğretim programı sürümü ayrıca kontrol edilmelidir.")
        foot.setWordWrap(True)
        layout.addWidget(foot)

    def _run_curriculum_review(self):
        oid = self._get_current_oid()
        if not oid:
            self.curriculum_report = None
            self.txtCurriculum.setPlainText("Önce öğrenci seçin.")
            return
        from services.coach_curriculum_v7 import build_outcome_review, outcome_as_html
        con = db.get_conn()
        try:
            self.curriculum_report = build_outcome_review(
                con, oid, grade_override=self.cmbCurriculumGrade.currentData())
            self.txtCurriculum.setHtml(outcome_as_html(self.curriculum_report))
        except Exception as exc:
            self.curriculum_report = None
            self.txtCurriculum.setPlainText("Kazanım kontrolü hazırlanamadı: " + str(exc))
        finally:
            con.close()

    def _copy_curriculum_review(self):
        if self.curriculum_report is None:
            QMessageBox.information(self, "Veri Yok", "Önce kazanım kontrolünü çalıştırın.")
            return
        from services.coach_curriculum_v7 import outcome_as_text
        QApplication.clipboard().setText(outcome_as_text(self.curriculum_report))
        QMessageBox.information(self, "Kopyalandı", "Kontrol taslağı panoya kopyalandı.")

    def _run_evidence_brief(self, student_id):
        from services.coach_evidence_v5 import build_coach_brief, brief_as_html
        con = db.get_conn()
        try:
            self.coach_brief = build_coach_brief(con, student_id)
            self.txtEvidence.setHtml(brief_as_html(self.coach_brief))
        except Exception as e:
            self.coach_brief = None
            self.txtEvidence.setPlainText("Koç özeti hazırlanamadı: " + str(e))
        finally:
            con.close()

    def _copy_evidence(self):
        if not self.coach_brief:
            QMessageBox.information(self, "Veri Yok", "Önce öğrenci analizini çalıştırın.")
            return
        from services.coach_evidence_v5 import brief_as_text
        QApplication.clipboard().setText(brief_as_text(self.coach_brief))
        QMessageBox.information(self, "Kopyalandı", "Koç özeti panoya kopyalandı.")

    def _check_official_sources(self):
        if self._source_thread is not None and self._source_thread.isRunning():
            return
        self.btnOfficial.setEnabled(False)
        self.txtOfficial.setPlainText("Resmî kaynaklara erişim kontrol ediliyor...")
        self._source_thread = _OfficialSourceCheckThread(self)
        self._source_thread.result_ready.connect(self._show_official_sources)
        self._source_thread.finished.connect(self._official_finished)
        self._source_thread.start()

    def accept(self):
        if self._source_thread is not None and self._source_thread.isRunning():
            QMessageBox.information(self, "Kaynak Kontrolü", "Çevrimiçi kaynak kontrolü bitince işleme devam edebilirsiniz.")
            return
        super().accept()

    def reject(self):
        if self._source_thread is not None and self._source_thread.isRunning():
            QMessageBox.information(self, "Kaynak Kontrolü", "Çevrimiçi kaynak kontrolü bitince kapatabilirsiniz.")
            return
        super().reject()

    def closeEvent(self, event):
        if self._source_thread is not None and self._source_thread.isRunning():
            # A QThread must not be destroyed while its HTTPS requests are active.
            event.ignore()
            QMessageBox.information(self, "Kaynak Kontrolü", "Bağlantı kontrolü bitince pencere kapatılabilir.")
            return
        self._coach_watch_timer.stop()
        super().closeEvent(event)

    def _official_finished(self):
        self.btnOfficial.setEnabled(True)
        # Destroy once Qt safely returns to the main thread.
        if self._source_thread is not None:
            self._source_thread.deleteLater()
            self._source_thread = None

    def _show_official_sources(self, items):
        html = ['<b>Resmî eğitim kaynakları</b><ul>']
        for v in items:
            label = html_escape(v['name'])
            url = html_escape(v['url'], quote=True)
            status = html_escape(v['status'])
            title = html_escape(v.get('title') or 'Başlık okunamadı')
            when = html_escape(v.get('checked_at', '')[:16].replace('T', ' '))
            html.append(f'<li><a href="{url}">{label}</a> — {status}<br/>'
                        f'<small>Sayfa başlığı: {title} · UTC kontrol: {when}</small></li>')
        html.append('</ul><small>Bağlantı kontrolü içerik doğruluğunu veya kazanım eşleşmesini kanıtlamaz.</small>')
        self.txtOfficial.setHtml(''.join(html))

    def _create_kpi_card(self, title: str, main_val: str, subtitle: str, color: str, bg_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {color}40;
                border-radius: 10px;
                padding: 6px 12px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        
        lbl_m = QLabel(main_val)
        lbl_m.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {color};")
        lbl_m.setObjectName("kpi_main")

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet("font-size: 11px; color: #64748b;")
        lbl_s.setObjectName("kpi_sub")

        lay.addWidget(lbl_t)
        lay.addWidget(lbl_m)
        lay.addWidget(lbl_s)
        return card

    def _build_suggestions_tab(self, parent_widget):
        main_lay = QVBoxLayout(parent_widget)
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(10)

        content = QHBoxLayout()
        content.setSpacing(12)

        # --- SOL PANEL: Bilişsel Yük & Pedagojik Durum ---
        left_panel = QFrame()
        left_panel.setFixedWidth(330)
        left_panel.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }")
        lay_left = QVBoxLayout(left_panel)
        lay_left.setContentsMargins(12, 12, 12, 12)
        lay_left.setSpacing(10)

        lbl_left_title = QLabel("🧠 Bilişsel Profil & Analiz")
        lbl_left_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        lay_left.addWidget(lbl_left_title)

        # Profil Rozeti
        self.lblProfileBadge = QLabel("🎯 Profil: Analiz bekleniyor...")
        self.lblProfileBadge.setWordWrap(True)
        self.lblProfileBadge.setStyleSheet("background: #e0e7ff; color: #3730a3; padding: 8px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        lay_left.addWidget(self.lblProfileBadge)

        # Ders Bazlı İlerleme Çubukları Scroll Alanı
        lay_left.addWidget(QLabel("<b>Ders Bazlı Tamamlama Durumu:</b>"))
        scroll_lessons = QScrollArea()
        scroll_lessons.setWidgetResizable(True)
        scroll_lessons.setFrameShape(QFrame.Shape.NoFrame)
        scroll_lessons.setStyleSheet("background: transparent;")
        
        self.lessons_container = QWidget()
        self.lessons_container.setStyleSheet("background: transparent;")
        self.lay_lessons_bars = QVBoxLayout(self.lessons_container)
        self.lay_lessons_bars.setContentsMargins(0, 0, 0, 0)
        self.lay_lessons_bars.setSpacing(6)
        self.lay_lessons_bars.addStretch(1)
        scroll_lessons.setWidget(self.lessons_container)
        lay_left.addWidget(scroll_lessons, 1)

        # Strateji Modu
        lay_left.addWidget(QLabel("<b>Planlama Strateji Modu:</b>"))
        self.cmbStrategyMode = QComboBox()
        self.cmbStrategyMode.addItems([
            "🌟 Dengeli Karma (Tavsiye Edilen)",
            "🎯 Kayıtlı Koçluk Ölçümüne Göre Telafi",
            "🧠 Kaydı Doğrulanmış Kısa Tekrar",
            "📈 Deneme Analizi (Koç Özeti)",
            "📘 Müfredat Kontrolü (Koç Özeti)"
        ])
        self.cmbStrategyMode.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; font-size: 12px; 
                color: #15191E;}
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbStrategyMode.currentIndexChanged.connect(self._on_strategy_mode_changed)
        lay_left.addWidget(self.cmbStrategyMode)

        # Hedef Süre
        h_dur = QHBoxLayout()
        h_dur.addWidget(QLabel("<b>Hedef Süre:</b>"))
        self.spTargetMinutes = QSpinBox()
        self.spTargetMinutes.setRange(30, 480)
        self.spTargetMinutes.setSingleStep(30)
        self.spTargetMinutes.setValue(180)
        self.spTargetMinutes.setSuffix(" dk")
        self.spTargetMinutes.setStyleSheet("background: white; color: #172033; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px;")
        self.spTargetMinutes.valueChanged.connect(self._on_target_minutes_changed)
        h_dur.addWidget(self.spTargetMinutes)
        lay_left.addLayout(h_dur)

        # Yeniden Analiz Butonu
        self.btnReanalyze = QPushButton("🔄 Yeniden Analiz Et")
        self.btnReanalyze.setStyleSheet("""
            QPushButton { background: #4f46e5; color: white; font-weight: bold; border-radius: 6px; padding: 8px; font-size: 12px; }
            QPushButton:hover { background: #4338ca; 
                color: #FFFFFF;}
        """)
        self.btnReanalyze.clicked.connect(self._run_analysis)
        lay_left.addWidget(self.btnReanalyze)

        content.addWidget(left_panel)

        # --- SAĞ PANEL: Öneri Listesi & Tablo ---
        right_panel = QWidget()
        lay_right = QVBoxLayout(right_panel)
        lay_right.setContentsMargins(0, 0, 0, 0)
        lay_right.setSpacing(8)

        # Filtre ve Arama Araç Çubuğu
        tools_lay = QHBoxLayout()
        tools_lay.setSpacing(6)

        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Konu, ders veya kitap ara...")
        self.txtSearch.setStyleSheet("background: white; color: #172033; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        self.txtSearch.textChanged.connect(self._filter_table_items)
        tools_lay.addWidget(self.txtSearch, 2)

        # Kategori Butonları
        self.btnFilterAll = QPushButton("Tümü")
        self.btnFilterRemedial = QPushButton("🚨 Telafi")
        self.btnFilterEbbinghaus = QPushButton("🧠 Tekrar")
        self.btnFilterExam = QPushButton("🔥 Sınav")
        self.btnFilterCurriculum = QPushButton("📘 Müfredat")

        for b in [self.btnFilterAll, self.btnFilterRemedial, self.btnFilterEbbinghaus, self.btnFilterExam, self.btnFilterCurriculum]:
            b.setCheckable(True)
            b.setStyleSheet("""
                QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: 600; color: #334155; }
                QPushButton:checked { background: #4338ca; color: white; border-color: #4338ca; }
            """)
        self.btnFilterAll.setChecked(True)

        self.btnFilterAll.clicked.connect(lambda: self._set_category_filter("all"))
        self.btnFilterRemedial.clicked.connect(lambda: self._set_category_filter("remedial"))
        self.btnFilterEbbinghaus.clicked.connect(lambda: self._set_category_filter("ebbinghaus"))
        self.btnFilterExam.clicked.connect(lambda: self._set_category_filter("exam"))
        self.btnFilterCurriculum.clicked.connect(lambda: self._set_category_filter("curriculum"))

        tools_lay.addWidget(self.btnFilterAll)
        tools_lay.addWidget(self.btnFilterRemedial)
        tools_lay.addWidget(self.btnFilterEbbinghaus)
        tools_lay.addWidget(self.btnFilterExam)
        tools_lay.addWidget(self.btnFilterCurriculum)

        self.btnToggleSelectAll = QPushButton("Tümünü Seç/Kaldır")
        self.btnToggleSelectAll.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: bold;")
        self.btnToggleSelectAll.clicked.connect(self._toggle_selection)
        tools_lay.addWidget(self.btnToggleSelectAll)

        lay_right.addLayout(tools_lay)

        self.lblSuggestionStatus = QLabel("Öneriler yalnızca doğrulanmış öğrenci kaynağına göre sunulur.")
        self.lblSuggestionStatus.setWordWrap(True)
        self.lblSuggestionStatus.setStyleSheet("color:#64748b;font-size:11px;")
        lay_right.addWidget(self.lblSuggestionStatus)

        # Tablo
        self.tableSuggestions = QTableWidget(0, 7)
        self.tableSuggestions.setHorizontalHeaderLabels([
            "Öncelik & Tür", "Ders", "Kitap / Kaynak", "Konu", "Hedef Yük", "Bilimsel Gerekçe & Detay", "Seç"
        ])
        self.tableSuggestions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableSuggestions.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; 
                color: #15191E;}
            QHeaderView::section { background-color: #f8fafc; padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: bold; color: #334155; }
            QTableWidget::item { padding: 4px 6px; }
        """)
        self.tableSuggestions.verticalHeader().setVisible(False)
        lay_right.addWidget(self.tableSuggestions)

        content.addWidget(right_panel, 1)
        main_lay.addLayout(content)

        # --- ALT BAR (Footer) ---
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.lblLiveSummary = QLabel("Seçilen: 0 Ödev (~0 dk, ~0 Soru) | Bilişsel Yük: 🟢 Dengeli")
        self.lblLiveSummary.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        footer.addWidget(self.lblLiveSummary)
        footer.addStretch(1)

        self.btnPrint = QPushButton("🖨️ PDF Raporu")
        self.btnPrint.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 14px; font-weight: 600; color: #334155;")
        self.btnPrint.clicked.connect(self._print_preview)
        footer.addWidget(self.btnPrint)

        self.btnCopyWhatsapp = QPushButton("📋 Panoya Kopyala")
        self.btnCopyWhatsapp.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 14px; font-weight: 600; color: #334155;")
        self.btnCopyWhatsapp.clicked.connect(self._copy_suggestions_text)
        footer.addWidget(self.btnCopyWhatsapp)

        self.btnAddSelected = QPushButton("✅ Seçilenleri Ödev Takip Formuna Aktar")
        self.btnAddSelected.setStyleSheet("""
            QPushButton { background-color: #059669; color: white; padding: 10px 22px; font-weight: bold; border-radius: 8px; font-size: 13px; }
            QPushButton:hover { background-color: #047857; 
                color: #FFFFFF;}
        """)
        self.btnAddSelected.clicked.connect(self._accept_selection)
        footer.addWidget(self.btnAddSelected)

        main_lay.addLayout(footer)

    def _build_strategy_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel("📅 <b>Öğrenci Profiline Göre Önizleme:</b> Kayıtlı rutin, etüt süresi, mola ve boş zamanlar esas alınır. Mevcut ödev planı değişmez.")
        info.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(info)

        self.txtStrategy = QTextBrowser()
        self.txtStrategy.setStyleSheet("background: #fafafa; color: #172033; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-family: 'Segoe UI', sans-serif;")
        layout.addWidget(self.txtStrategy, 1)

        btn_bar = QHBoxLayout()
        self.btnCopyPlan = QPushButton("📋 Haftalık Planı Kopyala")
        self.btnCopyPlan.setStyleSheet("background: #f8fafc; color: #172033; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 14px; font-weight: bold;")
        self.btnCopyPlan.clicked.connect(self._copy_plan_text)

        self.btnRefreshPlan = QPushButton("🔄 Planı Yenile")
        self.btnRefreshPlan.setStyleSheet("background: #4f46e5; color: white; border-radius: 6px; padding: 6px 14px; font-weight: bold;")
        self.btnRefreshPlan.clicked.connect(lambda: self._generate_weekly_plan(silent=False))

        btn_bar.addStretch()
        btn_bar.addWidget(self.btnCopyPlan)
        btn_bar.addWidget(self.btnRefreshPlan)
        layout.addLayout(btn_bar)

    def _build_coach_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_info = QLabel("📝 <b>Öğretmen için bilgilendirme taslağı:</b> Kayıtlı ödev verilerine dayanır; psikolojik değerlendirme veya başarı tanısı değildir.")
        top_info.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(top_info)

        split = QSplitter(Qt.Orientation.Horizontal)

        # Sol PDR Değerlendirme
        pdr_box = QFrame()
        pdr_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        lay_pdr = QVBoxLayout(pdr_box)
        lay_pdr.addWidget(QLabel("<b>📋 Kanıta Dayalı Takip Özeti:</b>"))
        self.txtPdrSummary = QTextBrowser()
        self.txtPdrSummary.setStyleSheet("background: white; color: #172033; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 13px;")
        lay_pdr.addWidget(self.txtPdrSummary)
        split.addWidget(pdr_box)

        # Sağ WhatsApp Mesajları
        wa_box = QFrame()
        wa_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        lay_wa = QVBoxLayout(wa_box)
        
        lay_wa.addWidget(QLabel("<b>📱 Öğrenciye Özel WhatsApp Mesajı:</b>"))
        self.txtWaStudent = QTextBrowser()
        self.txtWaStudent.setStyleSheet("background: #f0fdf4; color: #172033; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px; font-size: 12px;")
        lay_wa.addWidget(self.txtWaStudent)
        
        btn_cp_st = QPushButton("📋 Öğrenci Mesajını Kopyala")
        btn_cp_st.setStyleSheet("background: #059669; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
        btn_cp_st.clicked.connect(lambda: self._copy_to_clipboard(self.txtWaStudent.toPlainText(), "Öğrenci mesajı kopyalandı ✅"))
        lay_wa.addWidget(btn_cp_st)

        lay_wa.addWidget(QLabel("<b>👨‍👩‍👦 Veliye Özel Bilgilendirme Mesajı:</b>"))
        self.txtWaParent = QTextBrowser()
        self.txtWaParent.setStyleSheet("background: #eff6ff; color: #172033; border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px; font-size: 12px;")
        lay_wa.addWidget(self.txtWaParent)

        btn_cp_pr = QPushButton("📋 Veli Mesajını Kopyala")
        btn_cp_pr.setStyleSheet("background: #2563eb; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
        btn_cp_pr.clicked.connect(lambda: self._copy_to_clipboard(self.txtWaParent.toPlainText(), "Veli mesajı kopyalandı ✅"))
        lay_wa.addWidget(btn_cp_pr)

        split.addWidget(wa_box)
        layout.addWidget(split, 1)

    # ---------------- LOGIC & DATA LOADING ----------------

    def _load_students(self):
        """Gönderilen öğrenci ID'si bulunamazsa ASLA ilk öğrenciyi seçme."""
        from utils.wizard_integrity_v8 import normalized_identity, same_student
        con = db.get_conn()
        was_blocked = self.cmbStudent.blockSignals(True)
        try:
            self.cmbStudent.clear()
            rows = con.execute(
                "SELECT id, ad, soyad FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad, id"
            ).fetchall()
            if self.fixed_student_id is not None:
                selected = next((r for r in rows
                                 if same_student(r['id'], self.fixed_student_id)), None)
                if selected is None:
                    # Önceden pasife alınan bir öğrenciyi de yanlış kişiye döndürme.
                    selected = con.execute(
                        "SELECT id, ad, soyad FROM ogrenci WHERE id=?",
                        (self.fixed_student_id,)
                    ).fetchone()
                if selected is None:
                    self._student_scope_error = (
                        "Sihirbaz için seçilen öğrenci kaydı bulunamadı. "
                        "Ödev önerileri ve aktarım durduruldu."
                    )
                    self.cmbStudent.addItem("Öğrenci bulunamadı", None)
                else:
                    name = f"{selected['ad'] or ''} {selected['soyad'] or ''}".strip()
                    self.cmbStudent.addItem(name, normalized_identity(selected['id']))
                    self.cmbStudent.setCurrentIndex(0)
            else:
                self.cmbStudent.addItem("Öğrenci seçiniz", None)
                for r in rows:
                    name = f"{r['ad'] or ''} {r['soyad'] or ''}".strip()
                    self.cmbStudent.addItem(name, normalized_identity(r['id']))
                self.cmbStudent.setCurrentIndex(0)
        finally:
            self.cmbStudent.blockSignals(was_blocked)
            con.close()

    def _get_current_oid(self):
        from utils.wizard_integrity_v8 import normalized_identity, same_student
        selected_id = normalized_identity(self.cmbStudent.currentData())
        if self._student_scope_error:
            return None
        if self.fixed_student_id is not None:
            return self.fixed_student_id if same_student(selected_id, self.fixed_student_id) else None
        return selected_id

    def _on_student_combo_changed(self, idx):
        if self.fixed_student_id is not None:
            return
        self.ogrenci_id = self._get_current_oid()
        if self.ogrenci_id is not None:
            self._run_analysis()

    def _check_coach_freshness(self):
        """Only label cached reports stale; never overwrite selected tasks."""
        oid = self._get_current_oid()
        if not self.isVisible() or type(oid) is not int or oid <= 0:
            return
        try:
            check = self._coach_router.check(self._coach_cursor, student_id=oid)
            self._coach_cursor = check.cursor
            if check.changed:
                self.lblProfileBadge.setText(
                    '⚠️ Koçluk kaydı değişti. Mevcut öneriler eski olabilir; Yeniden İncele ile doğrulayın.')
        except (TypeError, ValueError):
            pass

    def _run_analysis(self):
        oid = self._get_current_oid()
        if not oid:
            return
        # Events during the read remain visible on the next passive check.
        self._coach_cursor = self._coach_router.cursor
        # Independent read-only brief remains available if the legacy suggestion
        # generator fails; it never writes assignments or student records.
        self._run_evidence_brief(oid)
        self._run_curriculum_review()

        progress = QProgressDialog("Öğrencinin kayıtlı ödev ve deneme verileri inceleniyor...", "İptal", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        progress.setValue(20)

        con = db.get_conn()
        try:
            from utils import ai_recommend

            # 1. Kapsamlı Öğrenci Analitiği Çek
            analytics = ai_recommend.get_comprehensive_student_analytics(con, oid)
            self.analytics_data = analytics
            progress.setValue(50)

            # 2. KPI Kartlarını Güncelle
            evidence_stats = self.coach_brief.get('stats', {}) if self.coach_brief else {}
            ratio = evidence_stats.get('completion_percent')
            done = evidence_stats.get('completed', 0)
            total = evidence_stats.get('assigned', 0)
            overdue = evidence_stats.get('overdue', 0)
            ratio = ratio if ratio is not None else '—'
            ebbinghaus_cnt = 0
            gaps_cnt = len(self.coach_brief.get('exam_notes', [])) if self.coach_brief else 0

            self.card_success.findChild(QLabel, "kpi_main").setText(f"%{ratio}")
            self.card_success.findChild(QLabel, "kpi_sub").setText(f"{done}/{total} Ödev Tamamlandı")

            self.card_overdue.findChild(QLabel, "kpi_main").setText(f"{overdue} Ödev")
            self.card_overdue.findChild(QLabel, "kpi_sub").setText("Teslim tarihi geçmiş; kontrol gerekli" if overdue > 0 else "Teslim tarihi geçmiş kayıt yok")

            self.card_ebbinghaus.findChild(QLabel, "kpi_main").setText(f"{ebbinghaus_cnt} Konu")
            self.card_ebbinghaus.findChild(QLabel, "kpi_sub").setText("Ölçüm değil, tekrar önerisi")

            self.card_exam.findChild(QLabel, "kpi_main").setText(f"{gaps_cnt} Ders")
            self.card_exam.findChild(QLabel, "kpi_sub").setText("Yalnızca kaydedilmiş denemeler")

            # 3. Sol Panel Profil ve İlerleme Çubukları
            self.lblProfileBadge.setText("🎯 Ödev takibi: Akademik başarı ayrıca ölçülmelidir")
            safe_lessons = {}
            for d, item in (self.coach_brief or {}).get('subjects', {}).items():
                total_d = item['assigned']
                done_d = item['completed']
                ratio_d = round(100 * done_d / total_d) if total_d else 0
                safe_lessons[d] = {'name': d, 'ratio': ratio_d, 'done':done_d,
                                   'total':total_d, 'color': '#059669' if ratio_d>=70 else '#d97706'}
            self._update_lesson_progress_bars(safe_lessons)
            progress.setValue(70)

            # 4. Akıllı Ödev Önerilerini Üret
            mode_map = {
                0: "balanced",
                1: "remedial",
                2: "ebbinghaus",
                3: "exam_focus",
                4: "curriculum",
            }
            curr_mode = mode_map.get(self.cmbStrategyMode.currentIndex(), "balanced")
            tgt_min = self.spTargetMinutes.value()

            from services.coach_evidence_v5 import build_safe_homework_suggestions
            suggestions = build_safe_homework_suggestions(
                con, oid, available_books=self.available_books,
                mode=curr_mode, target_minutes=tgt_min, limit=14
            )
            self.suggested_tasks = suggestions
            self.filtered_tasks = list(suggestions)
            ebbinghaus_cnt = sum(1 for x in suggestions if x['type']=='ebbinghaus')
            self.card_ebbinghaus.findChild(QLabel, "kpi_main").setText(f"{ebbinghaus_cnt} Konu")
            self._fill_table()
            progress.setValue(85)

            # 5. Haftalık Plan ve PDR Raporunu Üret
            self._generate_weekly_plan(silent=True)
            self._generate_pdr_report()
            progress.setValue(100)

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Analiz Hatası", f"Analiz sırasında bir hata oluştu:\n{e}")
        finally:
            con.close()
            progress.setValue(100)

    def _update_lesson_progress_bars(self, lesson_stats: Dict[str, Any]):
        # Mevcut barları temizle
        while self.lay_lessons_bars.count() > 1:
            child = self.lay_lessons_bars.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for d_key, data in lesson_stats.items():
            box = QWidget()
            b_lay = QVBoxLayout(box)
            b_lay.setContentsMargins(0, 2, 0, 2)
            b_lay.setSpacing(2)

            h_lbl = QHBoxLayout()
            lbl_name = QLabel(data["name"])
            lbl_name.setStyleSheet("font-size: 11px; font-weight: 600; color: #334155;")
            lbl_pct = QLabel(f"%{data['ratio']} ({data['done']}/{data['total']})")
            lbl_pct.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {data['color']};")
            h_lbl.addWidget(lbl_name)
            h_lbl.addStretch(1)
            h_lbl.addWidget(lbl_pct)
            b_lay.addLayout(h_lbl)

            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(data["ratio"])
            pbar.setTextVisible(False)
            pbar.setFixedHeight(6)
            pbar.setStyleSheet(f"""
                QProgressBar {{ background-color: #e2e8f0; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {data['color']}; border-radius: 3px; }}
            """)
            b_lay.addWidget(pbar)

            self.lay_lessons_bars.insertWidget(self.lay_lessons_bars.count() - 1, box)

    def _fill_table(self):
        if not self.filtered_tasks:
            self.lblSuggestionStatus.setText(
                "Doğrulanmış yeni ödev önerisi bulunamadı. Geciken görevler, deneme karşılaştırmaları "
                "ve müfredat kontrolü için ilk sekmedeki Koç Özetine bakın. Eksiklik tahmin edilmedi.")
        else:
            self.lblSuggestionStatus.setText(
                "Öneriler öğretmen onayı bekliyor. Varsayılan olarak hiçbiri işaretli değildir; "
                "öğrencinin çalışma profilindeki gerçek boş zamanı da kontrol edin.")
        self.tableSuggestions.setRowCount(0)
        for i, task in enumerate(self.filtered_tasks):
            self.tableSuggestions.insertRow(i)

            # 0: Badge (Öncelik & Tür)
            badge_text = task.get("badge") or "📌 Öneri"
            badge_col = task.get("badge_color") or "#4338ca"
            lbl_badge = QLabel(f" {badge_text} ")
            lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_badge.setStyleSheet(f"""
                background-color: {badge_col}15;
                color: {badge_col};
                border: 1px solid {badge_col}40;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 6px;
            """)
            self.tableSuggestions.setCellWidget(i, 0, lbl_badge)

            # 1: Ders
            d_name = task.get("ders", "-").replace("_", " ").title()
            it_ders = QTableWidgetItem(d_name)
            it_ders.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tableSuggestions.setItem(i, 1, it_ders)

            # 2: Kitap
            it_kitap = QTableWidgetItem(task.get("kitap", "-"))
            self.tableSuggestions.setItem(i, 2, it_kitap)

            # 3: Konu
            it_konu = QTableWidgetItem(task.get("konu", "-"))
            it_konu.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tableSuggestions.setItem(i, 3, it_konu)

            # 4: Hedef Yük
            dk = task.get("dk", 30)
            soru = task.get("soru", 20)
            it_load = QTableWidgetItem(f"🎯 ~{soru} Soru • ⏱️ {dk} dk")
            it_load.setForeground(QColor("#059669"))
            self.tableSuggestions.setItem(i, 4, it_load)

            # 5: Bilimsel Gerekçe & Detay
            reason = task.get("reason") or task.get("explain") or task.get("aciklama", "")
            it_reason = QTableWidgetItem(str(reason))
            it_reason.setToolTip(str(reason))
            self.tableSuggestions.setItem(i, 5, it_reason)

            # 6: Checkbox
            chk = QCheckBox()
            chk.setChecked(bool(task.get('auto_selected', False)))
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(chk)
            self.tableSuggestions.setCellWidget(i, 6, w)
            w.chk = chk
            chk.stateChanged.connect(self._update_summary)

        self.tableSuggestions.resizeColumnsToContents()
        h = self.tableSuggestions.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.tableSuggestions.setColumnWidth(6, 45)

        self._update_summary()

    def _update_summary(self):
        count = 0
        total_min = 0
        total_q = 0
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w and hasattr(w, 'chk') and w.chk.isChecked():
                count += 1
                if i < len(self.filtered_tasks):
                    task = self.filtered_tasks[i]
                    total_min += int(task.get('dk', 30) or 30)
                    total_q += int(task.get('soru', 20) or 20)

        saat = total_min // 60
        dk_mod = total_min % 60
        time_str = f"{total_min} dk"
        if saat > 0:
            time_str = f"{saat} sa {dk_mod} dk ({total_min} dk)"

        # Bilişsel Yük Seviyesi
        tgt = self.spTargetMinutes.value()
        if total_min <= tgt:
            load_txt = "✅ Seçim hedef süre içinde (gerçek öğrenci rutini ayrıca kontrol edilmeli)"
            c_code = "#059669"
        else:
            load_txt = "⚠️ Seçim hedef süreyi aşıyor"
            c_code = "#dc2626"

        self.lblLiveSummary.setText(f"Seçilen: {count} Ödev (~{time_str}, ~{total_q} Soru) | {load_txt}")
        self.lblLiveSummary.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c_code};")

    def _set_category_filter(self, cat: str):
        self.current_filter_category = cat
        # Buton stillerini güncelle
        self.btnFilterAll.setChecked(cat == "all")
        self.btnFilterRemedial.setChecked(cat == "remedial")
        self.btnFilterEbbinghaus.setChecked(cat == "ebbinghaus")
        self.btnFilterExam.setChecked(cat == "exam")
        self.btnFilterCurriculum.setChecked(cat == "curriculum")
        self._filter_table_items()

    def _filter_table_items(self):
        search_txt = self.txtSearch.text().strip().lower()
        cat = self.current_filter_category

        filtered = []
        for t in self.suggested_tasks:
            # Kategori kontrolü
            t_type = t.get("type", "")
            if cat == "remedial" and t_type != "remedial":
                continue
            if cat == "ebbinghaus" and t_type != "ebbinghaus":
                continue
            if cat == "exam" and "🔥" not in (t.get("badge") or ""):
                continue
            if cat == "curriculum" and t_type != "curriculum":
                continue

            # Arama kontrolü
            if search_txt:
                d = t.get("ders", "").lower()
                k = t.get("konu", "").lower()
                b = t.get("kitap", "").lower()
                r = str(t.get("reason", "")).lower()
                if search_txt not in d and search_txt not in k and search_txt not in b and search_txt not in r:
                    continue

            filtered.append(t)

        self.filtered_tasks = filtered
        self._fill_table()

    def _toggle_selection(self):
        if self.tableSuggestions.rowCount() == 0:
            return
        w = self.tableSuggestions.cellWidget(0, 6)
        tgt = not w.chk.isChecked() if w else True
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w:
                w.chk.setChecked(tgt)

    def _on_strategy_mode_changed(self, idx):
        self._run_analysis()

    def _on_target_minutes_changed(self, val):
        self._run_analysis()

    def _accept_selection(self):
        final_list = []
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w and w.chk.isChecked() and i < len(self.filtered_tasks):
                final_list.append(self.filtered_tasks[i])

        if not final_list:
            QMessageBox.information(self, "Seçim Yapılmadı", "Lütfen listeye eklemek için en az bir ödev seçiniz.")
            return

        total = sum(int(x.get('dk') or 0) for x in final_list)
        if total > self.spTargetMinutes.value():
            QMessageBox.warning(self, "Süre Aşıldı", "Seçilen ödevler hedef süreyi aşıyor. Seçimi azaltın.")
            return
        from utils.wizard_integrity_v8 import same_student
        oid = self._get_current_oid()
        if oid is None or (self.fixed_student_id is not None and not same_student(oid, self.fixed_student_id)):
            QMessageBox.warning(self, "Öğrenci Uyumsuzluğu", "Seçili öğrenci doğrulanamadı. Aktarım iptal edildi.")
            return
        parent = self.parent()
        if parent is not None and callable(getattr(parent, "_secili_ogrenci_id", None)):
            if not same_student(oid, parent._secili_ogrenci_id()):
                QMessageBox.warning(self, "Öğrenci Değişti", "Ana formdaki öğrenci değişti. Lütfen sihirbazı yeniden açın.")
                return
        self.transfer_student_id = oid
        self.selected_homeworks = final_list
        self.accept()

    def _generate_weekly_plan(self, silent=False):
        oid = self._get_current_oid()
        if not oid:
            return
        try:
            from services.plan_profile_store import load_profiles, load_assignments
            from services.coach_evidence_v5 import build_profile_weekly_preview
            profile_name = load_assignments().get(str(oid))
            saved = load_profiles()
            profile = saved.get(profile_name) if profile_name else None
            if not isinstance(profile, dict):
                self.weekly_plan_data = None
                self.txtStrategy.setPlainText(
                    "Öğrenciye atanmış kayıtlı bir çalışma profili bulunmuyor. "
                    "Önce Akıllı Haftalık Planlama ekranında öğrencinin rutin profilini kaydedip ilişkilendirin. "
                    "Profil olmadan rastgele saatlere çalışma yerleştirilmez.")
                return
            con = db.get_conn()
            try:
                plan = build_profile_weekly_preview(con, oid, profile, self.available_books)
            finally:
                con.close()
            self.weekly_plan_data = plan
            parts = ['<div style="font:13px Segoe UI;line-height:1.55">',
                     '<h3>📅 Kayıtlı öğrenci rutinine göre çalışma taslağı</h3>',
                     '<p><b>Önemli:</b> Bu, yalnızca doğrulanmış tekrar önerilerinin taslağıdır; mevcut ödevleri ve onaylı takvimi değiştirmez.</p>']
            for day in plan['schedule']:
                parts.append(f'<h4>{html_escape(day["date"])} · '
                             f'{day["planned_minutes"]}/{day["available_minutes"]} dk</h4>')
                if not day['items']:
                    parts.append('<p style="color:#64748b">Yerleştirilmiş yeni öneri yok.</p>')
                else:
                    parts.append('<ul>')
                    for task in day['items']:
                        parts.append(f'<li>{html_escape(task["start"])}–{html_escape(task["end"])} '
                                     f'· {html_escape(task["ders"])} / {html_escape(task["konu"])} '
                                     f'({task["dk"]} dk)</li>')
                    parts.append('</ul>')
            if plan['leftovers']:
                parts.append('<h4>⚠️ Yerleştirilemeyenler</h4><ul>')
                for u in plan['leftovers']:
                    parts.append(f'<li>{html_escape(u["task"]["konu"])}: '
                                 f'{html_escape(u["reason"])}</li>')
                parts.append('</ul>')
            parts.append('</div>')
            self.txtStrategy.setHtml(''.join(parts))
        except Exception as e:
            self.weekly_plan_data = None
            self.txtStrategy.setPlainText('Kayıtlı rutin veya takvim ayarları okunamadı: ' + str(e))

    def _generate_pdr_report(self):
        # Safer drafts: no psychological diagnosis or fabricated mastery scores.
        if not self.coach_brief:
            return
        from services.coach_evidence_v5 import brief_as_html
        data = self.coach_brief
        st = data['stats']
        name = data['student']['name']
        self.txtPdrSummary.setHtml(brief_as_html(data))
        if st['assigned'] == 0:
            student_msg = (f"Merhaba {name}, henüz yeterli ödev kaydı bulunmuyor. "
                           "Çalışma hedeflerini öğretmeninle birlikte belirleyebilirsiniz.")
            parent_msg = ("Merhaba, öğrencimizin çalışma takibini değerlendirmek için henüz "
                          "yeterli ödev kaydı bulunmuyor. Öğretmenimizle birlikte planlama yapılacaktır.")
        else:
            student_msg = (f"Merhaba {name}, kayıtlı {st['assigned']} ödevinin "
                           f"{st['completed']} tanesi tamamlanmış görünüyor. "
                           f"Kontrol bekleyen {st['overdue']} görev var. "
                           "Birlikte kısa bir kontrol yapıp yeni çalışma planını netleştirebiliriz.")
            parent_msg = (f"Merhaba, kayıtlı {st['assigned']} ödevden {st['completed']} tanesi "
                          f"tamamlanmış görünüyor; {st['overdue']} görev kontrol bekliyor. "
                          "Bu sayılar akademik başarı ölçümü değil, ödev takip verisidir. "
                          "İlgili çalışmalar öğretmen değerlendirmesiyle planlanacaktır.")
        self.txtWaStudent.setPlainText(student_msg)
        self.txtWaParent.setPlainText(parent_msg)

    def _copy_to_clipboard(self, text: str, msg: str = "Panoya kopyalandı ✅"):
        cb = QApplication.clipboard()
        cb.setText(text)
        QMessageBox.information(self, "Kopyalandı", msg)

    def _copy_suggestions_text(self):
        lines = ["📌 *Akıllı Ödev Sihirbazı - Seçilen Ödevler*\n"]
        for i, t in enumerate(self.filtered_tasks):
            cell = self.tableSuggestions.cellWidget(i, 6)
            if not cell or not hasattr(cell, 'chk') or not cell.chk.isChecked():
                continue
            d = t.get("ders", "").replace("_", " ").title()
            k = t.get("konu", "")
            b = t.get("kitap", "")
            dk = t.get("dk", 30)
            soru = t.get("soru", 20)
            r = t.get("reason", "")
            lines.append(f"• *{d}* ({b}): {k} | ~{soru} Soru ({dk} dk)\n  ↳ _{r}_")
        self._copy_to_clipboard("\n".join(lines), "Ödev listesi panoya kopyalandı ✅")

    def _copy_plan_text(self):
        if self.weekly_plan_data:
            txt = self.txtStrategy.toPlainText()
            self._copy_to_clipboard(txt, "Haftalık plan metni kopyalandı ✅")

    def _print_preview(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument, QPageSize

        student_name = html_escape(self.cmbStudent.currentText())
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 30px; color: #1e293b; }}
                h1 {{ color: #4338ca; border-bottom: 2px solid #4338ca; padding-bottom: 8px; font-size: 20pt; }}
                .kpi-box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 10pt; }}
                th {{ background-color: #4338ca; color: white; padding: 8px; text-align: left; border: 1px solid #3730a3; }}
                td {{ padding: 8px; border: 1px solid #cbd5e1; vertical-align: top; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
                .footer {{ margin-top: 30px; font-size: 9pt; color: #64748b; text-align: right; border-top: 1px solid #e2e8f0; padding-top: 8px; }}
            </style>
        </head>
        <body>
            <h1>Ödev & Başarı Raporu: {student_name}</h1>
            <div class="kpi-box">
                <b>Ödev Takibi:</b> {html_escape(self.lblProfileBadge.text())}<br>
                <b>Durum Özeti:</b> {html_escape(self.lblLiveSummary.text())}
            </div>
            <h3>📌 Önerilen Çalışma & Telafi Listesi</h3>
            <table>
                <thead>
                    <tr>
                        <th width="15%">Tür</th>
                        <th width="18%">Ders</th>
                        <th width="20%">Kitap</th>
                        <th width="22%">Konu</th>
                        <th width="10%">Hedef</th>
                        <th width="15%">Açıklama</th>
                    </tr>
                </thead>
                <tbody>
        """
        for t in self.filtered_tasks:
            badge = html_escape(t.get("badge", ""))
            ders = html_escape(t.get("ders", "").replace("_", " ").title())
            kitap = html_escape(t.get("kitap", ""))
            konu = html_escape(t.get("konu", ""))
            dk = t.get("dk", 30)
            soru = t.get("soru", 20)
            reason = html_escape(t.get("reason", ""))
            html += f"""
                <tr>
                    <td><b>{badge}</b></td>
                    <td>{ders}</td>
                    <td>{kitap}</td>
                    <td>{konu}</td>
                    <td>{soru} Soru ({dk} dk)</td>
                    <td>{reason}</td>
                </tr>
            """
        html += f"""
                </tbody>
            </table>
            <div class="footer">Rapor Tarihi: {now_str} | Akıllı Ödev ve Başarı Sihirbazı v3.0 Pro</div>
        </body>
        </html>
        """

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        try:
            from PyQt6.QtCore import QMarginsF
            from PyQt6.QtGui import QPageLayout
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            layout = QPageLayout(printer.pageLayout())
            layout.setMargins(QMarginsF(12.0, 12.0, 12.0, 12.0))
            printer.setPageLayout(layout)
        except Exception:
            pass

        preview = QPrintPreviewDialog(printer, self)
        preview.setMinimumSize(1100, 850)

        def handle_print(p):
            doc = QTextDocument()
            doc.setHtml(html)
            try:
                doc.setPageSize(p.pageRect(QPrinter.Unit.Point).size())
            except Exception:
                pass
            doc.print(p)

        preview.paintRequested.connect(handle_print)
        preview.exec()
