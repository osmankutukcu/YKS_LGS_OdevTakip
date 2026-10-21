# -*- coding: utf-8 -*-
"""KoçPilot 360 - yönlendirici Rapor Merkezi (V3.5.81 pilot).

Bu ekran rapor verisini HESAPLAMAZ ve veritabanına YAZMAZ.
Yalnızca mevcut, çalışma biçimi korunmuş rapor modüllerini açar.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPalette, QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget, QMenu,
)

# Basit, test edilebilir yönlendirme kataloğu. Yeni rapor motoru yerine mevcut
# ana pencere giriş noktalarını kullanıyoruz; raporlardaki filtreler değişmez.
REPORT_ROUTES = (
    {
        "title": "Veliye / öğrenciye rapor ver",
        "question": "Bir veya birden çok öğrenci için hızlıca PDF hazırlamak istiyorum.",
        "contents": "Ödev durumu ve veli karnesi • öğrenci seçimi • toplu çıktı",
        "output": "PDF / Yazdır",
        "destination": "Hızlı PDF",
        "method": "_create_pdf_report",
        "accent": "#2563eb",
        "icon": "📄",
    },
    {
        "title": "Bir öğrenciyi ayrıntılı incele",
        "question": "Öğrencinin eksiklerini, ders dağılımını ve gelişimini görmek istiyorum.",
        "contents": "Bireysel grafikler • tamamlanmamış ödevler • koçluk notları",
        "output": "Analiz / PDF",
        "destination": "Öğrenci Detayı",
        "method": "_ogrenci_detay",
        "accent": "#0891b2",
        "icon": "👤",
    },
    {
        "title": "Sınıf veya kurumu karşılaştır",
        "question": "Bir gruptaki öğrencileri ve ders bazlı oranları kıyaslayacağım.",
        "contents": "Sınıf filtresi • öğrenci sıralaması • ders grafikleri",
        "output": "Tablo / PDF / Excel",
        "destination": "Detaylı Raporlar",
        "method": "_rapor_ac",
        "accent": "#7c3aed",
        "icon": "📊",
    },
    {
        "title": "Haftalık ödev performansını gör",
        "question": "Öğrencilerin bu haftaki durumunu, gelişimini ve panoyu hazırlayacağım.",
        "contents": "Haftalık ödev takibi • öne çıkanlar • teslim dönemi",
        "output": "Pano PDF / Excel",
        "destination": "Performans Paneli",
        "method": "_performans_paneli",
        "accent": "#d97706",
        "icon": "🏆",
    },
    {
        "title": "Hedef ve net açığını değerlendir",
        "question": "Öğrencinin hedefiyle sınav netlerini birlikte ele almak istiyorum.",
        "contents": "Hedef analizi • net farkları • senaryo ve öneriler",
        "output": "Analiz / Planlama",
        "destination": "Hedef Analizi",
        "method": "_hedef_analiz_open",
        "accent": "#059669",
        "icon": "🎯",
    },
    {
        "title": "Gelişmiş grafikler hazırla",
        "question": "Konu, ders, tarih aralığı ve rapor grafiği seçmek istiyorum.",
        "contents": "Detaylı Raporlar içindeki gelişmiş rapor ve grafik ekranı",
        "output": "Grafik / PDF / Excel",
        "destination": "Gelişmiş Grafik Raporları",
        "method": "_open_advanced_from_center",
        "accent": "#be185d",
        "icon": "📈",
    },
)


class ReportCenterDialog(QDialog):
    """İş amacından rapora: özgün modülleri değiştirmeyen görsel yönlendirme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.approved_navigation = None
        self.pending_route = None
        self.setObjectName("ReportCenterV3581")
        self.setWindowTitle("KoçPilot 360 • Rapor Merkezi")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(1050, 760)
        self.setMinimumSize(720, 560)
        self._set_theme()
        self._build_ui()

    def _set_theme(self):
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 130
        page = "#101827" if dark else "#f8fafc"
        card = "#18253b" if dark else "#ffffff"
        ink = "#f1f5f9" if dark else "#0f172a"
        subtle = "#cbd5e1" if dark else "#475569"
        line = "#3e5069" if dark else "#dce5f0"
        chip = "#25374e" if dark else "#eef2ff"
        self.setStyleSheet(f"""
            QDialog#ReportCenterV3581 {{ background: {page}; }}
            QFrame#ReportRouteCard {{ background: {card}; border: 1px solid {line};
                                      border-radius: 12px; }}
            QLabel#RouteTitle {{ color: {ink}; font-weight: 750; font-size: 15px; }}
            QLabel#RouteQuestion {{ color: {subtle}; font-size: 12px; }}
            QLabel#RouteDetail {{ color: {subtle}; font-size: 11px; }}
            QLabel#RouteDestination {{ color: {ink}; background: {chip};
                                       padding: 4px 8px; border-radius: 4px; }}
            QLabel#BodyTitle {{ color: {ink}; font-weight: 750; font-size: 17px; }}
            QLabel#BodyHelp {{ color: {subtle}; font-size: 12px; }}
            QPushButton#RouteAction {{ background: #2563eb; border: none;
                                       color: white; padding: 9px 14px;
                                       border-radius: 6px; font-weight: 750; }}
            QPushButton#RouteAction:hover {{ background: #1d4ed8; color: white; }}
            QPushButton#SecondaryAction {{ background: {card}; color: {ink};
                                           border: 1px solid {line}; padding: 8px 14px;
                                           border-radius: 6px; }}
            QScrollArea {{ background: transparent; border: none; }}
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        banner = QFrame()
        banner.setStyleSheet("QFrame { background: #14233c; border-radius: 12px; }"
                             "QLabel { color: #ffffff; background: transparent; }")
        head = QVBoxLayout(banner)
        head.setContentsMargins(20, 16, 20, 16)
        head.setSpacing(5)
        name = QLabel("📑  RAPOR MERKEZİ")
        name.setStyleSheet("font-size: 21px; font-weight: 800; color: #ffffff;")
        header_line = QHBoxLayout()
        header_line.addWidget(name)
        header_line.addStretch()
        check_sources = QPushButton("🔎 Veri Kontrolü")
        check_sources.setToolTip("Yalnızca yerel kayıtları okuyan çakışma ön denetimi")
        check_sources.setStyleSheet(
            "QPushButton { color:#eff6ff; background:#223e61; "
            "padding:7px 12px; border-radius:6px; }"
        )
        check_sources.clicked.connect(self._inspect_local_data)
        header_line.addWidget(check_sources)
        sources = QPushButton("🌐 Resmî Kaynaklar")
        sources.setToolTip(
            "ÖSYM sınav takvimi ve MEB öğretim programlarını resmî sitede açar. "
            "Öğrenci bilgileri gönderilmez."
        )
        sources.setStyleSheet(
            "QPushButton { color:#eff6ff; background:#223e61; "
            "padding:7px 12px; border-radius:6px; }"
        )
        official_menu = QMenu(sources)
        official_menu.addAction(
            "ÖSYM - Sınav Takvimi",
            lambda: self._open_official("https://www.osym.gov.tr/Sayfa/SinavTakvimi/tr-TR")
        )
        official_menu.addAction(
            "MEB - Öğretim Programları",
            lambda: self._open_official("https://tymm.meb.gov.tr/ogretim-programlari")
        )
        sources.setMenu(official_menu)
        header_line.addWidget(sources)
        # V3593: read-only decision panel; original six report routes stay intact.
        advisor = QPushButton("🧭 Öğretmen Karar Paneli")
        advisor.setAccessibleName("Öğrenciyi seçerek kanıta dayalı öğretmen önerilerini görüntüle")
        advisor.setToolTip("Öğrenci bazlı deneme/konu kanıtı ve kontrollü sonraki adımlar")
        advisor.setStyleSheet(
            "QPushButton { color:#ffffff; background:#1366ce; "
            "padding:7px 12px; border-radius:6px; font-weight:700; }"
        )
        advisor.clicked.connect(self._open_teacher_decision)
        header_line.addWidget(advisor)
        head.addLayout(header_line)
        intro = QLabel("Önce ne yapmak istediğinizi seçin. KoçPilot sizi doğru rapora götürsün.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #dbeafe; font-size: 12px;")
        head.addWidget(intro)
        layout.addWidget(banner)

        caption = QLabel("Hangi işlemi yapmak istiyorsunuz?")
        caption.setObjectName("BodyTitle")
        layout.addWidget(caption)
        help_text = QLabel("Raporun amacını seçmek yeterli. Mevcut raporlar, filtreler ve yazdırma seçenekleri aynen çalışır.")
        help_text.setObjectName("BodyHelp")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        scroller = QScrollArea(self)
        scroller.setWidgetResizable(True)
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(2, 4, 2, 4)
        grid.setSpacing(12)
        for ix, route in enumerate(REPORT_ROUTES):
            grid.addWidget(self._make_card(route), ix // 2, ix % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        scroller.setWidget(holder)
        layout.addWidget(scroller, 1)

        foot = QHBoxLayout()
        note = QLabel("Bilgi: Ödev tamamlanma oranı sınav başarısı değildir. Gecikme, eksik ve dönem oranları farklı ölçülerdir.")
        note.setObjectName("BodyHelp")
        note.setWordWrap(True)
        foot.addWidget(note, 1)
        guide = QPushButton("ℹ️ Ayrıntılı Rehber")
        guide.setObjectName("SecondaryAction")
        guide.clicked.connect(self._show_guide)
        foot.addWidget(guide)
        # V3.5.83: opt-in PDF atölyesi; mevcut altı yönlendirme değiştirilmez.
        studio = QPushButton("📑 Yeni PDF Şablonları (Pilot)")
        studio.setObjectName("SecondaryAction")
        studio.setToolTip("Yeni veli ve öğretmen PDF şablonlarını deneyin; eski raporlar korunur")
        studio.clicked.connect(self._open_professional_pdf)
        foot.addWidget(studio)
        bulk = QPushButton("📚 Toplu PDF + Önizleme (Pilot)")
        bulk.setObjectName("SecondaryAction")
        bulk.setToolTip("Grup bazlı öğrenci seçimi, birleşik PDF ve gerçek sayfa önizlemesi")
        bulk.clicked.connect(self._open_bulk_pdf)
        foot.addWidget(bulk)
        close = QPushButton("Kapat")
        close.setObjectName("SecondaryAction")
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        layout.addLayout(foot)

    def _make_card(self, route):
        card = QFrame()
        card.setObjectName("ReportRouteCard")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(15, 14, 15, 14)
        inner.setSpacing(7)
        header = QHBoxLayout()
        icon = QLabel(route["icon"])
        icon.setStyleSheet("font-size: 20px;")
        header.addWidget(icon)
        label = QLabel(route["title"])
        label.setObjectName("RouteTitle")
        label.setWordWrap(True)
        header.addWidget(label, 1)
        inner.addLayout(header)

        question = QLabel(route["question"])
        question.setObjectName("RouteQuestion")
        question.setWordWrap(True)
        inner.addWidget(question)
        detail = QLabel(route["contents"])
        detail.setObjectName("RouteDetail")
        detail.setWordWrap(True)
        inner.addWidget(detail)
        inner.addStretch()

        bottom = QHBoxLayout()
        output = QLabel(route["output"])
        output.setObjectName("RouteDestination")
        output.setToolTip("Raporun kullanılabildiği mevcut çıktı seçenekleri")
        bottom.addWidget(output)
        bottom.addStretch(1)
        action = QPushButton("Aç  →")
        action.setObjectName("RouteAction")
        action.setToolTip(f"{route['destination']} ekranını aç")
        action.setAccessibleName(f"{route['title']} - {route['destination']} ekranını aç")
        action.clicked.connect(lambda checked=False, name=route["method"]: self._launch(name))
        bottom.addWidget(action)
        inner.addLayout(bottom)
        return card

    def _open_legacy_reports(self):
        """Mevcut detaylı/grafik raporlarına güvenli yönlendirme."""
        self._launch("_open_advanced_from_center")

    def _launch(self, method_name):
        import logging
        from PyQt6.QtCore import QTimer
        parent = self.parent()
        allowed = {r["method"] for r in REPORT_ROUTES} | {"_open_advanced_from_center", "_open_legacy_reports"}
        if method_name not in allowed:
            QMessageBox.warning(self, "Rapor açılamadı", "Seçilen rapor bu kurulumda kullanılamıyor.")
            return

        self.pending_route = method_name

        def _dispatch():
            if method_name == "_open_advanced_from_center":
                dashboard = getattr(parent, "_report_dashboard", None)
                if dashboard is None and hasattr(parent, "_rapor_ac"):
                    parent._rapor_ac()
                    dashboard = getattr(parent, "_report_dashboard", None)
                if dashboard is not None and hasattr(dashboard, "_open_legacy_reports"):
                    dashboard._open_legacy_reports()
                else:
                    try:
                        from ui.safe_reports_v3589 import AciklanabilirRaporlarFormu
                        legacy = AciklanabilirRaporlarFormu(parent)
                        legacy.setWindowTitle("Gelişmiş Grafik ve Detaylı Raporlar — KoçPilot 360")
                        legacy.setWindowFlag(Qt.WindowType.Window, True)
                        legacy.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                        legacy.resize(1200, 700)
                        legacy.show()
                        legacy.raise_()
                        legacy.activateWindow()
                    except Exception:
                        logging.getLogger(__name__).exception("Gelişmiş rapor açılamadı")
                        QMessageBox.warning(self, "Rapor açılamadı",
                                            "Seçilen rapor şu anda açılamadı. Diğer raporları kullanabilirsiniz.")
                return

            target = getattr(parent, method_name, None)
            if not callable(target):
                QMessageBox.warning(self, "Rapor açılamadı", "Seçilen rapor bu kurulumda kullanılamıyor.")
                return

            try:
                target()
            except Exception:
                logging.getLogger(__name__).exception("Rapor ekranı açılamadı: %s", method_name)
                QMessageBox.warning(self, "Rapor açılamadı",
                                    "Seçilen rapor şu anda açılamadı. Diğer raporları kullanabilirsiniz.")

        # Rapor Merkezini kapat ve ana ekran üzerinde hedefi güvenle çalıştır
        self.close()
        if self.isModal():
            self.accept()
        if parent is not None:
            QTimer.singleShot(0, _dispatch)

    @staticmethod
    def _open_official(url):
        """Yalnızca sabit resmî HTTPS adresleri; öğrenci verisi/parametre yok."""
        allowed = {
            "https://www.osym.gov.tr/Sayfa/SinavTakvimi/tr-TR",
            "https://tymm.meb.gov.tr/ogretim-programlari",
        }
        if url in allowed:
            QDesktopServices.openUrl(QUrl(url))

    def _inspect_local_data(self):
        """V3590: Mevcut kanonik motor ile kişisel veri içermeyen kaynak denetimi."""
        from importlib import import_module
        from services.report_integrity_v3590 import (
            audit_cohort_report_sources, explain_cohort_audit,
        )
        conn = None
        owns_connection = False
        try:
            dashboard = getattr(self.parent(), "_report_dashboard", None)
            conn = getattr(dashboard, "con", None)
            if conn is None:
                conn = import_module("db").get_conn()
                owns_connection = True
            result = audit_cohort_report_sources(conn)
            QMessageBox.information(
                self, "Rapor Kaynakları ve Kanıt Denetimi",
                explain_cohort_audit(result)
            )
        except Exception:
            # SQL details or names should not appear in end-user error messages.
            QMessageBox.warning(
                self, "Denetim tamamlanamadı",
                "Yerel kayıtlar doğrulanamadı. Veri kaynağını kontrol edin; "
                "hiçbir kayıt değiştirilmedi."
            )
        finally:
            if owns_connection and conn is not None:
                conn.close()

    def _show_guide(self):
        parent = self.parent()
        target = getattr(parent, "_show_report_guide", None)
        if not callable(target):
            QMessageBox.warning(self, "Rehber açılamadı", "Rehber bu kurulumda bulunamadı.")
            return
        self.pending_route = "_show_report_guide"
        self.close()
        if self.isModal():
            self.accept()
        if parent is not None:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, target)

    def _open_professional_pdf(self):
        """Rapor merkezinden isteğe bağlı yeni şablonlar; ana pencere değişmez."""
        import sys
        parent = self.parent()
        dashboard = getattr(parent, "_report_dashboard", None)
        con = getattr(dashboard, "con", None)
        if con is None:
            try:
                db_mod = sys.modules.get("db")
                if db_mod and hasattr(db_mod, "get_conn"):
                    con = db_mod.get_conn()
            except Exception:
                con = None
        if con is None:
            QMessageBox.warning(self, "Bağlantı bulunamadı", "Veritabanı bağlantısı açılamadı.")
            return
        try:
            from ui.professional_pdf_dialog_v3583 import ProfessionalPDFDialog
            dialog = ProfessionalPDFDialog(con, self)
            dialog.exec()
        except Exception as exc:
            QMessageBox.warning(self, "PDF atölyesi açılamadı", str(exc))

    def _open_bulk_pdf(self):
        """V3586 opt-in: new dialog, never alters any legacy export path."""
        import sys
        parent = self.parent()
        dashboard = getattr(parent, "_report_dashboard", None)
        con = getattr(dashboard, "con", None)
        if con is None:
            try:
                db_mod = sys.modules.get("db")
                if db_mod and hasattr(db_mod, "get_conn"):
                    con = db_mod.get_conn()
            except Exception:
                con = None
        if con is None:
            QMessageBox.warning(self, "Bağlantı bulunamadı", "Veritabanı bağlantısı açılamadı.")
            return
        try:
            from ui.bulk_report_dialog_v3586 import BulkReportDialog
            dialog = BulkReportDialog(con, self)
            dialog.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Toplu rapor açılamadı", str(exc))

    def _open_teacher_decision(self):
        """V3593: an opt-in, read-only decision view with connection ownership."""
        from importlib import import_module
        con = None
        owns_connection = False
        try:
            parent = self.parent()
            dashboard = getattr(parent, "_report_dashboard", None)
            con = getattr(dashboard, "con", None)
            if con is None:
                con = import_module("db").get_conn()
                owns_connection = True
            from ui.teacher_decision_dialog_v3593 import TeacherDecisionDialog
            dialog = TeacherDecisionDialog(con, self)
            dialog.exec()
            intent = dialog.approved_navigation
            if intent is not None:
                self.approved_navigation = intent
                self.close()
                self.accept()  # Return to app.py before opening legacy form.
                def _open_nav():
                    try:
                        from ui.report_navigation_bridge_v3594 import open_confirmed_navigation
                        open_confirmed_navigation(parent, intent)
                    except Exception:
                        pass
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, _open_nav)
        except Exception:
            self.approved_navigation = None
            QMessageBox.warning(self, "Karar Paneli açılamadı",
                                "Yerel öğrenci kayıtlarına erişilemedi. "
                                "Mevcut raporlar kullanılmaya devam edebilir.")
        finally:
            if owns_connection and con is not None:
                try:
                    con.close()
                except Exception:
                    pass
