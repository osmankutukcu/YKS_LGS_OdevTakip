# -*- coding: utf-8 -*-
"""Compact non-modal Coach Assistant dialog with saved generic question templates.

Only question text explicitly favorited is persisted for the current OS profile.
Previous student answers disappear when the active student changes. The existing
read-only question engine and teacher-approved action callbacks stay unchanged.
"""
from __future__ import annotations

from contextlib import closing
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, Qt, QTimer, QStandardPaths, QPoint
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QLineEdit, QPushButton, QMessageBox,
                             QToolButton, QMenu, QWidget, QGraphicsDropShadowEffect)

from services.coach_assistant_v1.dialogue import read_context
from services.coach_assistant_v1.conversation_followup import (
    answer_with_memory, next_memory, ConversationMemory,
)
from services.coach_assistant_v1.question_library import QuestionLibrary, RecentQuestions


class _Signals(QObject):
    finished = pyqtSignal(int, int, object, object)


class _QuestionWork(QRunnable):
    def __init__(self, seq: int, student_id: int, question: str, memory=None, store_path=None):
        super().__init__()
        self.seq = seq
        self.student_id = student_id
        self.question = question
        self.memory = memory
        self.store_path = store_path
        self.signals = _Signals()

    def run(self):
        try:
            from db import DB_PATH
            uri = DB_PATH.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
                con.execute("PRAGMA query_only=ON")
                context = read_context(con, self.student_id)
            result = answer_with_memory(context, self.question, self.memory)
            # One short supporting note only. Prefer explicitly reviewed local notes;
            # fall back to the preinstalled V12.5 reference when no local note matches.
            reviewed_matched = False
            try:
                from services.coach_assistant_v1.knowledge_manager_v126 import (
                    enrich_with_reviewed, ReviewStore,
                )
                enriched = enrich_with_reviewed(result, self.question,
                                                ReviewStore(self.store_path))
                reviewed_matched = enriched is not result
                result = enriched
            except (OSError, ValueError, RuntimeError, ImportError) as review_error:
                import logging
                logging.getLogger(__name__).warning(
                    "Öğretmen rehberleri okunamadı: %s", type(review_error).__name__)
            if not reviewed_matched:
                try:
                    from services.coach_assistant_v1.knowledge_bank_v125 import enrich_answer
                    result = enrich_answer(result, self.question)
                except (OSError, ValueError, ImportError) as knowledge_exc:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Koçluk kütüphanesi okunamadı: %s", type(knowledge_exc).__name__)
            error = None
        except Exception:
            result, error = None, "Öğrenci verisi şu anda güvenilir şekilde okunamadı. Lütfen tekrar deneyin."
        self.signals.finished.emit(self.seq, self.student_id, result, error)


class CoachDialogueV121(QFrame):
    """Sleek in-app floating Coach Assistant card anchored inside OdevTakipFormu.

    Lives inside the main form window so it can NEVER drop behind the form when clicking
    table cells or changing students. Features glassmorphic styling, collapsible header,
    drag support, and zero obstruction of the teacher's active workspace.
    """

    def __init__(self, form, get_selected_id, *, open_learning=None, open_control=None):
        super().__init__(form)
        self.form = form
        self.get_selected_id = get_selected_id
        self.open_learning = open_learning
        self.open_control = open_control
        self._seq = 0
        self._outstanding = {}
        self._last_action = None
        self._last_student_id = None
        self._last_asked_text = ""
        self._memory = None  # Only transient same-student conversation context.
        self._pending_questions = {}
        self._active_student_id = get_selected_id()
        self._recent = RecentQuestions()
        self._custom_positioned = False
        self._is_dragging = False
        self._drag_start = QPoint()
        self._compact = False

        config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        # Empty Qt path must never cause writes to the project working directory.
        base = Path(config_dir) if config_dir else (Path.home() / ".config" / "EduTrack")
        self._library = QuestionLibrary(base / "coach_question_library_v1.json")
        self._knowledge_store_path = base / "coach_knowledge_reviews_v126.json"
        self._knowledge_window = None

        self.setObjectName("coachDialogueToast")
        self.setFixedWidth(430)
        self.setFixedHeight(368)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(15, 23, 42, 160))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QFrame#coachDialogueToast {
                background: rgba(15, 23, 42, 0.96);
                border: 1.5px solid rgba(56, 189, 248, 0.65);
                border-radius: 12px;
            }
            QFrame#coachDialogueToast QLabel {
                background: transparent;
                color: #f8fafc;
            }
            QTextEdit {
                background: rgba(30, 41, 59, 0.88);
                border: 1px solid rgba(71, 85, 105, 0.7);
                border-radius: 8px;
                color: #f1f5f9;
                font-size: 11px;
                padding: 6px;
                line-height: 1.4;
            }
            QLineEdit {
                background: rgba(30, 41, 59, 0.95);
                border: 1px solid rgba(100, 116, 139, 0.8);
                border-radius: 6px;
                color: #f8fafc;
                font-size: 11px;
                padding: 5px 9px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
            QPushButton, QToolButton {
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid rgba(100, 116, 139, 0.6);
                border-radius: 5px;
                color: #e2e8f0;
                font-size: 10.5px;
                padding: 4px 8px;
                font-weight: 600;
            }
            QPushButton:hover, QToolButton:hover {
                background: rgba(51, 65, 85, 0.95);
                border-color: #38bdf8;
                color: #ffffff;
            }
            QPushButton#coachDialogueSendBtn {
                background: #0284c7;
                border: 1px solid #38bdf8;
                color: #121212;
                font-weight: 700;
                padding: 5px 12px;
            }
            QPushButton#coachDialogueSendBtn:hover {
                background: #0369a1;
            
                color: #FFFFFF;}
            QPushButton#coachDialogueOpenBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                border: 1px solid #34d399;
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QPushButton#coachDialogueOpenBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                border-color: #6ee7b7;
                color: #ffffff;
            }
            QPushButton#coachDialogueOpenBtn:disabled {
                background: rgba(30, 41, 59, 0.45);
                border: 1px solid rgba(71, 85, 105, 0.4);
                color: #64748b;
                font-weight: 500;
            }
            QToolButton#coachSavedBtn {
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid rgba(56, 189, 248, 0.45);
                border-radius: 6px;
                color: #bae6fd;
                font-weight: 600;
                font-size: 10.5px;
                padding: 4px 10px;
            }
            QToolButton#coachSavedBtn:hover {
                background: rgba(14, 165, 233, 0.25);
                border-color: #38bdf8;
                color: #ffffff;
            }
            QToolButton#coachSavedBtn::menu-indicator {
                image: none;
                width: 0px;
            }
            QMenu {
                background-color: #0f172a;
                border: 1.5px solid rgba(56, 189, 248, 0.7);
                border-radius: 8px;
                padding: 4px;
                color: #f1f5f9;
            }
            QMenu::item {
                background-color: transparent;
                color: #f1f5f9;
                padding: 6px 16px 6px 12px;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #121212;
                font-weight: 700;
            }
            QMenu::item:disabled {
                color: #475569;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 6px;
            }
            QMenu::section {
                color: #7dd3fc;
                font-size: 10px;
                font-weight: 700;
                padding: 4px 10px;
                background: transparent;
            }
            QPushButton#coachDialogueCloseBtn, QPushButton#coachDialogueCollapseBtn {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(148, 163, 184, 0.3);
                color: #94a3b8;
                border-radius: 5px;
                font-size: 11px;
                padding: 2px 7px;
            }
            QPushButton#coachDialogueCloseBtn:hover {
                background: rgba(239, 68, 68, 0.3);
                border-color: #ef4444;
                color: #fca5a5;
            }
            QPushButton#coachDialogueCollapseBtn:hover {
                background: rgba(51, 65, 85, 0.9);
                color: #f8fafc;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        # Header Row (Draggable area)
        header = QHBoxLayout()
        header.setSpacing(6)
        self.caption = QLabel("💬 Koça Sor")
        self.caption.setStyleSheet("font-weight: 800; font-size: 12.5px; color: #7dd3fc;")
        header.addWidget(self.caption)

        self.badge = QLabel("Kanıta Dayalı")
        self.badge.setStyleSheet(
            "background: rgba(30, 58, 138, 180); color: #e0f2fe; font-size: 9.5px; font-weight: 700; "
            "padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(125, 211, 252, 90);"
        )
        header.addWidget(self.badge)

        self.drag_hint = QLabel("⋮⋮")
        self.drag_hint.setToolTip("Taşımak için buradan sürükleyin")
        self.drag_hint.setStyleSheet("color: #64748b; font-size: 13px; font-weight: bold; padding: 0 4px;")
        header.addWidget(self.drag_hint)

        header.addStretch(1)

        self.collapse_button = QPushButton("— Daralt")
        self.collapse_button.setObjectName("coachDialogueCollapseBtn")
        self.collapse_button.setToolTip("Formu kullanırken asistanı küçük bir satıra indir")
        self.collapse_button.clicked.connect(self._toggle_compact)
        header.addWidget(self.collapse_button)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("coachDialogueCloseBtn")
        self.close_button.setToolTip("Koça Sor'u kapat")
        self.close_button.clicked.connect(self.hide)
        header.addWidget(self.close_button)

        outer.addLayout(header)

        # Content Container
        self.content = QWidget(self)
        body = QVBoxLayout(self.content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)

        self.hint = QLabel("Yanıtlar seçili öğrencinin güncel yerel kayıtlarından üretilir.")
        self.hint.setStyleSheet("font-size: 10px; color: #94a3b8;")
        self.hint.setWordWrap(True)
        body.addWidget(self.hint)

        self.history = QTextEdit(self)
        self.history.setObjectName("coachDialogueHistory")
        self.history.setReadOnly(True)
        body.addWidget(self.history, 1)

        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(5)
        for title, question in (("Önceliğim?", "En önemli gizli sorun ne?"),
                                ("Ödev–öğrenme", "Ödevler ile öğrenme kanıtı tutarlı mı?"),
                                ("Hangi konu?", "Hangi konuda zorlanıyor?")):
            btn = QPushButton(title, self)
            btn.setToolTip(question)
            btn.clicked.connect(lambda _, q=question: self.ask(q))
            shortcuts.addWidget(btn)
        body.addLayout(shortcuts)

        followups = QHBoxLayout()
        followups.setSpacing(5)
        self.why_button = QPushButton("Neden?", self)
        self.next_button = QPushButton("Peki, ne yapalım?", self)
        for button, prompt in ((self.why_button, "Neden?"),
                               (self.next_button, "Peki bu hafta ne yapalım?")):
            button.setEnabled(False)
            button.setToolTip("Önceki yanıtı, güncel öğrenci verileriyle yeniden değerlendir")
            button.clicked.connect(lambda checked=False, q=prompt: self.ask(q))
            followups.addWidget(button)
        body.addLayout(followups)

        self.open_button = QPushButton("İlgili mevcut ekrana git", self)
        self.open_button.setObjectName("coachDialogueOpenBtn")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_related)
        body.addWidget(self.open_button)

        favorites = QHBoxLayout()
        favorites.setSpacing(5)
        self.saved_button = QToolButton(self)
        self.saved_button.setObjectName("coachSavedBtn")
        self.saved_button.setText("⭐ Kayıtlı Sorular  ▾")
        self.saved_button.setToolTip("Kaydedilen veya bu oturumda sorulan soruyu bir tıkla tekrar sor")
        self.saved_menu = QMenu(self)
        self.saved_menu.aboutToShow.connect(self._fill_menu)
        self.saved_menu.setMaximumWidth(390)
        self.saved_button.setMenu(self.saved_menu)
        self.saved_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        favorites.addWidget(self.saved_button)

        self.save_button = QPushButton("＋ Kaydet")
        self.save_button.setToolTip("Öğrenci adı/özel bilgi içermeyen genel soruları bu cihazda saklayın; cevaplar kaydedilmez")
        self.save_button.clicked.connect(self._save_template)
        favorites.addWidget(self.save_button)

        self.knowledge_button = QPushButton("📚 Bilgiler")
        self.knowledge_button.setToolTip("Öğretmen tarafından incelenmiş koçluk belgelerini yönet")
        self.knowledge_button.clicked.connect(self._open_knowledge_manager)
        favorites.addWidget(self.knowledge_button)
        favorites.addStretch(1)
        body.addLayout(favorites)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.question = QLineEdit(self)
        self.question.setObjectName("coachDialogueInput")
        self.question.setPlaceholderText("Örneğin: Bu önerinin dayanağı ne?")
        self.question.setMaxLength(600)
        self.question.returnPressed.connect(self.submit)
        row.addWidget(self.question, 1)

        self.send = QPushButton("Sor", self)
        self.send.setObjectName("coachDialogueSendBtn")
        self.send.clicked.connect(self.submit)
        row.addWidget(self.send)
        body.addLayout(row)

        outer.addWidget(self.content, 1)

        self._log("Koç Asistanı: Öğrencinin güncel yerel kayıtlarını sorabilirsiniz.\n")
        self._student_timer = QTimer(self)
        self._student_timer.setInterval(800)
        self._student_timer.timeout.connect(self._sync_student)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.pos().y() <= 38:
            self._drag_start = event.globalPosition().toPoint() - self.pos()
            self._is_dragging = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, "_is_dragging", False) and self.parentWidget() is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_start
            pw = self.parentWidget().width()
            ph = self.parentWidget().height()
            x = max(8, min(new_pos.x(), pw - self.width() - 8))
            y = max(8, min(new_pos.y(), ph - self.height() - 8))
            self.move(x, y)
            self._custom_positioned = True
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def reposition(self) -> None:
        if self.parentWidget() is None:
            return
        pw = self.parentWidget().width()
        ph = self.parentWidget().height()
        if self._custom_positioned:
            x = max(8, min(self.x(), pw - self.width() - 8))
            y = max(8, min(self.y(), ph - self.height() - 8))
            self.move(x, y)
            return
        x = max(16, pw - self.width() - 20)
        y = max(16, ph - self.height() - 44)
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self.reposition()
        self._sync_student()
        self._student_timer.start()
        self.raise_()

    def hideEvent(self, event):
        self._student_timer.stop()
        super().hideEvent(event)

    def _sync_student(self):
        try:
            sid = self.get_selected_id()
        except Exception:
            sid = None
        if sid == self._active_student_id:
            return
        self._active_student_id = sid
        self._seq += 1  # Cancel any outstanding answer's right to appear.
        self._last_action = None
        self._last_student_id = None
        self._last_asked_text = ""
        self._memory = None
        self._pending_questions.clear()
        self._recent = RecentQuestions()  # Avoid a previous student's free-text queries.
        self.why_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.question.clear()
        self.history.clear()  # Never display the previous student's answer.
        self._log("Koç Asistanı: Öğrenci değişti. Yeni öğrencinin verileri için yeniden sorabilirsiniz.\n")

    def _log(self, message: str):
        self.history.moveCursor(QTextCursor.MoveOperation.End)
        self.history.insertPlainText(str(message)[:3000] + "\n")

    def _fill_menu(self):
        self.saved_menu.clear()
        self.saved_menu.addSection("⭐ Kaydedilen soru kalıpları")
        stored = self._library.list_questions()
        if not stored:
            self.saved_menu.addAction("Henüz kayıtlı soru yok").setEnabled(False)
        for q in stored:
            action = self.saved_menu.addAction(q[:50] + ("…" if len(q) > 50 else ""))
            action.setToolTip(q)
            action.triggered.connect(lambda checked=False, text=q: self.ask(text))
        if stored:
            delete = self.saved_menu.addMenu("Kayıtlı soruyu sil ▸")
            for q in stored:
                act = delete.addAction(q[:50] + ("…" if len(q) > 50 else ""))
                act.triggered.connect(lambda checked=False, text=q: self._delete_template(text))
        recent = self._recent.list_questions()
        if recent:
            self.saved_menu.addSeparator()
            self.saved_menu.addSection("Bu oturumda sorulanlar")
            for q in recent:
                action = self.saved_menu.addAction(q[:50] + ("…" if len(q) > 50 else ""))
                action.setToolTip(q)
                action.triggered.connect(lambda checked=False, text=q: self.ask(text))

    def _save_template(self):
        q = self.question.text().strip() or self._last_asked_text
        try:
            added = self._library.add(q)
        except (ValueError, OSError) as exc:
            QMessageBox.information(self, "Soru kaydedilemedi", str(exc))
            return
        if added:
            self.caption.setText("⭐ Soru kaydedildi (yalnızca bu cihazda)")
        else:
            self.caption.setText("⭐ Bu soru zaten kayıtlı")

    def _delete_template(self, q):
        try:
            removed = self._library.remove(q)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Soru silinemedi", str(exc))
            return
        if removed:
            self.caption.setText("Soru kayıtlardan silindi")

    def _open_knowledge_manager(self):
        # Management opens only on demand. The compact assistant stays untouched.
        try:
            from ui.coach_knowledge_manager_v126 import CoachKnowledgeManagerV126
            top_parent = self.form or self.parentWidget() or self
            if self._knowledge_window is None:
                self._knowledge_window = CoachKnowledgeManagerV126(
                    top_parent, self._knowledge_store_path)
            self._knowledge_window.show()
            self._knowledge_window.raise_()
            self._knowledge_window.activateWindow()
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Bilgi kütüphanesi", str(exc))

    def _toggle_compact(self):
        self._compact = not self._compact
        self.content.setVisible(not self._compact)
        self.collapse_button.setText("▢ Genişlet" if self._compact else "— Daralt")
        if self._compact:
            self.setFixedHeight(38)
        else:
            self.setFixedHeight(368)
        self.reposition()
        self.raise_()

    def submit(self):
        self.ask(self.question.text())

    def ask(self, question: str):
        question = str(question or "").strip()[:600]
        if not question:
            return
        self._sync_student()
        sid = self.get_selected_id()
        if type(sid) is not int or sid <= 0:
            QMessageBox.information(self, "Öğrenci seçin", "Önce ödev takip formundan bir öğrenci seçin.")
            return
        self._recent.add(question)
        self._last_asked_text = question
        self.question.clear()
        self._seq += 1
        seq = self._seq
        self._last_action = None
        self.open_button.setEnabled(False)
        self._log(f"Öğretmen: {question}\nKoç Asistanı: Güncel yerel kayıtlar inceleniyor...\n")
        self._pending_questions[seq] = question
        task = _QuestionWork(seq, sid, question, self._memory, self._knowledge_store_path)
        self._outstanding[seq] = task
        task.signals.finished.connect(self._received)
        QThreadPool.globalInstance().start(task)

    def _received(self, seq: int, sid: int, answer, error):
        self._outstanding.pop(seq, None)
        submitted = self._pending_questions.pop(seq, None)
        self._sync_student()
        if not self.isVisible() or seq != self._seq:
            return
        if self.get_selected_id() != sid:
            self._log("Koç Asistanı: Öğrenci değiştiği için eski öğrenciye ait sonuç gösterilmedi.\n")
            return
        if error:
            self._log("Koç Asistanı: " + error + "\n")
            return
        # Memory holds only a question anchor; it never retains stale student metrics.
        if submitted:
            self._memory = next_memory(
                sid, submitted, self._memory
            )
        self.why_button.setEnabled(bool(self._memory))
        self.next_button.setEnabled(bool(self._memory))
        self._log(f"Koç Asistanı — {answer.title}:\n{answer.message}")
        if answer.evidence:
            self._log("Dayanaklar: " + " | ".join(answer.evidence) + "\n")
        self._last_action = answer.action_target
        self._last_student_id = sid
        self.open_button.setEnabled(bool(self._last_action))
        if self._last_action == "btnOgrenme":
            self.open_button.setText("🎯 İlgili Ekrana Git: 🧠 Öğrenme Panosu")
        elif self._last_action == "btnKontrol":
            self.open_button.setText("🎯 İlgili Ekrana Git: ✅ Ödev Kontrol")
        else:
            self.open_button.setText("İlgili mevcut ekrana git")
        if self._compact:
            self.caption.setText("💬 Yanıt hazır · Genişleterek okuyun")

    def _open_related(self):
        if self.get_selected_id() != self._last_student_id:
            QMessageBox.information(self, "Öğrenci değişti", "Önce seçili öğrenci için tekrar sorgulayın.")
            return
        if self._last_action == "btnOgrenme" and callable(self.open_learning):
            self.open_learning()
        elif self._last_action == "btnKontrol" and callable(self.open_control):
            self.open_control()
