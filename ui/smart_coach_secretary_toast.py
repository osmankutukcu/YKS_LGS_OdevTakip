# -*- coding: utf-8 -*-
"""Modular, Semi-Transparent Coach Assistant Toast & Pointer Overlay (V12.7).

Guides the teacher with curiosity-driven, original data insights ("✨ Koç Asistanı")
rather than bossy commands:
1. Semi-transparent glassmorphic toast (`QPainter` alpha-blended) so the
   underlying homework table remains subtly visible and unblocked.
2. Click-through (`WA_TransparentForMouseEvents`) semi-transparent directional
   arrow + callout pill pointing to the exact button on screen (`🧠 Öğrenme`,
   `✅ Kontrol`, `🧭 Öğrenci 360°`) where the intriguing data lives.
3. Background SQLite queries via `QThreadPool` for zero-lag UI responsiveness.
4. "💬 Koça Sor" interactive non-modal dialogue window.
5. Proactive attention management with quiet/balanced/active modes and inbox.
"""
from __future__ import annotations

from collections import deque
from contextlib import closing
import math
import sqlite3
import time

from PyQt6.QtCore import (
    Qt, QTimer, QSettings, QEvent, QObject, QPoint, QPointF, QRectF,
    QRunnable, QThreadPool, pyqtSignal
)
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QMenu, QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QFont, QFontMetrics, QPolygonF
)

from services.coach_assistant_v1.proactive_policy import (
    ProactiveGate, database_stamp, VALID_MODES
)
from services.coach_assistant_v1.attention_v263 import attention_decision
from services.coach_assistant_v1 import (
    AssistantInsight,
    build_student_curiosity_insight,
    build_topic_curiosity_insight,
)


SETTINGS_ORG = "EduTrack"
SETTINGS_APP = "HomeworkManagerV2"
SETTINGS_KEY_ENABLED = "smart_coach_secretary_enabled"


class TransparentPointerOverlay(QWidget):
    """Click-through overlay drawing a semi-transparent arrow & callout to a target button."""

    def __init__(self, form: QWidget):
        super().__init__(form)
        self.form = form
        self._target_widget: QWidget | None = None
        self._toast_widget: QWidget | None = None
        self._caption: str = ""
        self._accent_color = QColor("#38bdf8")

        self.setObjectName("coachAssistantPointerOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide()

    def point_to(
        self,
        target_widget: QWidget | None,
        *,
        toast_widget: QWidget | None = None,
        caption: str = "",
        color_hex: str = "#38bdf8",
    ) -> None:
        if target_widget is None or not target_widget.isVisible():
            self.hide()
            return
        self._target_widget = target_widget
        self._toast_widget = toast_widget
        self._caption = caption or ""
        self._accent_color = QColor(color_hex or "#38bdf8")
        self.sync_geometry()
        self.show()
        self.raise_()
        self.update()

    def sync_geometry(self) -> None:
        if self.form is not None:
            self.setGeometry(self.form.rect())

    def paintEvent(self, event) -> None:
        if self._target_widget is None or not self._target_widget.isVisible():
            return

        try:
            top_left = self._target_widget.mapTo(self.form, QPoint(0, 0))
        except Exception:
            return

        tw = self._target_widget.width()
        th = self._target_widget.height()
        if tw <= 2 or th <= 2:
            return

        target_rect = QRectF(float(top_left.x()), float(top_left.y()), float(tw), float(th))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        accent = QColor(self._accent_color)

        # 1. Soft translucent glow & ring around the target button
        outer_glow = target_rect.adjusted(-6.0, -5.0, 6.0, 5.0)
        glow_fill = QColor(accent.red(), accent.green(), accent.blue(), 38)
        glow_pen = QColor(accent.red(), accent.green(), accent.blue(), 195)
        painter.setBrush(QBrush(glow_fill))
        painter.setPen(QPen(glow_pen, 2.0))
        painter.drawRoundedRect(outer_glow, 8.0, 8.0)

        # 2. Semi-transparent floating callout pill above the target button
        target_anchor = QPointF(target_rect.center().x(), outer_glow.top() - 3.0)

        if self._caption:
            font = QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(self._caption)
            pill_w = float(min(max(text_w + 26, 185), 370))
            pill_h = 28.0

            # Offset the pill slightly left of the target button center so the arrow forms a graceful curve
            pill_cx = max(
                pill_w / 2.0 + 16.0,
                min(target_anchor.x() - 54.0, self.width() - pill_w / 2.0 - 16.0),
            )
            pill_top = max(16.0, target_anchor.y() - 72.0)

            # Avoid overlapping with the toast widget if visible
            if self._toast_widget is not None and self._toast_widget.isVisible():
                t_geo = QRectF(self._toast_widget.geometry())
                candidate_rect = QRectF(pill_cx - pill_w / 2.0, pill_top, pill_w, pill_h)
                if candidate_rect.intersects(t_geo.adjusted(-12, -12, 12, 12)):
                    pill_cx = max(pill_w / 2.0 + 16.0, t_geo.left() - pill_w / 2.0 - 22.0)

            pill_rect = QRectF(pill_cx - pill_w / 2.0, pill_top, pill_w, pill_h)

            # 2a. Subtle dashed connector from Toast left edge to Callout Pill right edge
            if self._toast_widget is not None and self._toast_widget.isVisible():
                t_rect = QRectF(self._toast_widget.geometry())
                toast_anchor = QPointF(t_rect.left() + 4.0, t_rect.bottom() - 28.0)
                pill_right_anchor = QPointF(pill_rect.right() + 4.0, pill_rect.center().y())
                if toast_anchor.x() > pill_right_anchor.x() + 20.0:
                    dash_path = QPainterPath(toast_anchor)
                    ctrl1 = QPointF(
                        (toast_anchor.x() + pill_right_anchor.x()) * 0.5,
                        min(toast_anchor.y(), pill_right_anchor.y()) - 22.0,
                    )
                    dash_path.quadTo(ctrl1, pill_right_anchor)
                    dash_pen = QPen(
                        QColor(accent.red(), accent.green(), accent.blue(), 115),
                        1.6,
                        Qt.PenStyle.DashLine,
                    )
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(dash_pen)
                    painter.drawPath(dash_path)

            # 2b. Translucent glass pill background
            painter.setBrush(QBrush(QColor(15, 23, 42, 168)))
            painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 195), 1.5))
            painter.drawRoundedRect(pill_rect, 8.0, 8.0)

            painter.setPen(QColor(240, 249, 255, 240))
            painter.drawText(
                pill_rect.adjusted(10.0, 0.0, -10.0, 0.0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter),
                self._caption,
            )

            arrow_start = QPointF(pill_rect.center().x() + 18.0, pill_rect.bottom() + 2.0)
        else:
            arrow_start = QPointF(target_anchor.x() - 42.0, target_anchor.y() - 52.0)

        # 3. Smooth semi-transparent curved arrow pointing directly to the button
        curve_path = QPainterPath(arrow_start)
        ctrl_pt = QPointF(
            arrow_start.x() + (target_anchor.x() - arrow_start.x()) * 0.15,
            arrow_start.y() + (target_anchor.y() - arrow_start.y()) * 0.68,
        )
        curve_path.quadTo(ctrl_pt, target_anchor)

        # Outer soft glow along arrow shaft
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 60), 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(curve_path)

        # Crisp semi-transparent arrow shaft
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 205), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(curve_path)

        # Arrowhead at target_anchor
        dx = target_anchor.x() - ctrl_pt.x()
        dy = target_anchor.y() - ctrl_pt.y()
        angle = math.atan2(dy, dx)
        head_len = 11.0
        head_angle = math.pi / 6.0

        p1 = QPointF(
            target_anchor.x() - head_len * math.cos(angle - head_angle),
            target_anchor.y() - head_len * math.sin(angle - head_angle),
        )
        p2 = QPointF(
            target_anchor.x() - head_len * math.cos(angle + head_angle),
            target_anchor.y() - head_len * math.sin(angle + head_angle),
        )
        arrow_head = QPolygonF([target_anchor, p1, p2])
        painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 215)))
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 230), 1.2))
        painter.drawPolygon(arrow_head)


class SmartCoachSecretaryToast(QFrame):
    """Semi-transparent, floating Coach Assistant toast anchored to bottom-right."""

    def __init__(
        self,
        form: QWidget,
        *,
        open_control=None,
        open_adaptive=None,
        pointer_overlay: TransparentPointerOverlay | None = None,
    ):
        super().__init__(form)
        self.form = form
        self._open_control = open_control
        self._open_adaptive = open_adaptive
        self._pointer_overlay = pointer_overlay
        self._primary_callback = None
        self._detail_callback = None
        self._border_color = QColor("#38bdf8")
        self._hovered = False

        self.setObjectName("smartCoachSecretaryToast")
        self.setFixedWidth(408)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(15, 23, 42, 95))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QFrame#smartCoachSecretaryToast {
                background: transparent;
                border: none;
            }
            QFrame#smartCoachSecretaryToast QLabel {
                background: transparent;
                border: none;
                color: #f8fafc;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(15, 12, 15, 12)
        lay.setSpacing(7)

        # Header Row
        top = QHBoxLayout()
        top.setSpacing(6)
        self.lbl_title = QLabel("✨ Koç Asistanı")
        self.lbl_title.setStyleSheet("color: #bae6fd; font-weight: 800; font-size: 12.5px;")
        top.addWidget(self.lbl_title, 1)

        self.lbl_step_pill = QLabel("💡 Fark Ettiniz mi?")
        self.lbl_step_pill.setStyleSheet(
            "background: rgba(30, 58, 138, 175); color: #e0f2fe; font-size: 10px; font-weight: 700; "
            "padding: 2px 8px; border-radius: 5px; border: 1px solid rgba(125, 211, 252, 90);"
        )
        top.addWidget(self.lbl_step_pill)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Bu ipucunu kapat")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 165); color: #cbd5e1;
                border: 1px solid rgba(148, 163, 184, 90);
                border-radius: 5px; font-size: 11px; font-weight: 800; padding: 0px;
            }
            QPushButton:hover { background: rgba(51, 65, 85, 220); color: #ffffff; }
        """)
        self.btn_close.clicked.connect(self.hide_with_overlay)
        top.addWidget(self.btn_close)
        lay.addLayout(top)

        # Curiosity Hook Strip inside Toast
        self.lbl_workflow = QLabel("")
        self.lbl_workflow.setWordWrap(True)
        self.lbl_workflow.setStyleSheet(
            "background: rgba(30, 41, 59, 155); color: #fde68a; font-size: 10.5px; font-weight: 700; "
            "padding: 5px 9px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 75);"
        )
        lay.addWidget(self.lbl_workflow)

        # Main Curiosity Body
        self.lbl_body = QLabel("")
        self.lbl_body.setWordWrap(True)
        self.lbl_body.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_body.setStyleSheet("color: #f8fafc; font-size: 11.5px; line-height: 1.42;")
        lay.addWidget(self.lbl_body)

        # Minimal Action Row (optional 1-click curiosity button + subtle hint)
        bot = QHBoxLayout()
        bot.setSpacing(8)
        self.btn_action = QPushButton("")
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFixedHeight(27)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background: rgba(37, 99, 235, 210); color: #ffffff;
                border: 1px solid rgba(147, 197, 253, 120);
                border-radius: 6px; padding: 3px 12px; font-size: 11px; font-weight: 800;
            }
            QPushButton:hover { background: rgba(29, 78, 216, 245); }
        """)
        self.btn_action.clicked.connect(self._run_primary_action)
        bot.addWidget(self.btn_action)
        self.btn_detail = QPushButton('💬 Koça Sor')
        self.btn_detail.setToolTip('Bu uyarıdan ayrıntılı soru-cevap ekranına geç')
        self.btn_detail.setFixedHeight(27)
        self.btn_detail.clicked.connect(self._run_detail_action)
        self.btn_detail.hide()
        bot.addWidget(self.btn_detail)
        bot.addStretch(1)
        self.lbl_hint = QLabel("💧 Yarı şeffaf · Otomatik kapanır")
        self.lbl_hint.setStyleSheet("color: #94a3b8; font-size: 10px;")
        bot.addWidget(self.lbl_hint)
        lay.addLayout(bot)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_with_overlay)

        self.hide()

    def paintEvent(self, event) -> None:
        """Render a genuinely semi-transparent dark-glass card over the workspace."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg_alpha = 234 if self._hovered else 174  # ~68% opacity when idle -> table shows through!
        painter.setBrush(QBrush(QColor(15, 23, 42, bg_alpha)))

        pen_col = QColor(self._border_color)
        pen_col.setAlpha(215 if self._hovered else 180)
        painter.setPen(QPen(pen_col, 1.6))
        painter.drawRoundedRect(rect, 13.0, 13.0)

        # Subtle top glass reflection line
        hl_rect = QRectF(rect.left() + 12.0, rect.top() + 1.5, rect.width() - 24.0, 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 45)))
        painter.drawRoundedRect(hl_rect, 1.0, 1.0)

    def hide_with_overlay(self) -> None:
        if self._pointer_overlay is not None:
            self._pointer_overlay.hide()
        self.hide()

    def _run_primary_action(self) -> None:
        cb = self._primary_callback
        self.hide_with_overlay()
        if callable(cb):
            cb()

    def _run_detail_action(self) -> None:
        cb = self._detail_callback
        self.hide_with_overlay()
        if callable(cb):
            cb()

    def enterEvent(self, event) -> None:
        self._hovered = True
        if self._hide_timer.isActive():
            self._hide_timer.stop()
            self.lbl_hint.setText("📌 Okuma modu (fare ayrılınca kapanır)")
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.lbl_hint.setText("💧 Yarı şeffaf · Otomatik kapanır")
        self._hide_timer.start(2800)
        self.update()
        super().leaveEvent(event)

    def reposition(self) -> None:
        if self.parentWidget() is None:
            return
        pw = self.parentWidget().width()
        ph = self.parentWidget().height()
        self.adjustSize()
        tw = self.width()
        th = self.sizeHint().height()
        self.setFixedHeight(max(132, min(th, 315)))
        x = max(16, pw - tw - 22)
        y = max(16, ph - self.height() - 104)
        self.move(x, y)
        if self._pointer_overlay is not None and self._pointer_overlay.isVisible():
            self._pointer_overlay.sync_geometry()
            self._pointer_overlay.raise_()
        self.raise_()

    def show_toast(
        self,
        *,
        title: str,
        step_badge: str,
        workflow_html: str,
        body_html: str,
        action_text: str | None = None,
        action_cb=None,
        detail_cb=None,
        duration_ms: int = 7200,
        border_color: str = "#38bdf8",
        target_widget: QWidget | None = None,
        pointer_caption: str | None = None,
    ) -> None:
        self._border_color = QColor(border_color or "#38bdf8")
        self.lbl_title.setText(title)
        self.lbl_step_pill.setText(step_badge)
        self.lbl_workflow.setText(workflow_html)
        self.lbl_body.setText(body_html)
        self._primary_callback = action_cb
        self._detail_callback = detail_cb
        self.btn_detail.setVisible(callable(detail_cb))
        if action_text and callable(action_cb):
            self.btn_action.setText(action_text)
            self.btn_action.show()
        else:
            self.btn_action.hide()
        self.lbl_hint.setText("💧 Yarı şeffaf · Otomatik kapanır")
        self.reposition()
        self.show()

        if self._pointer_overlay is not None:
            if target_widget is not None:
                self._pointer_overlay.point_to(
                    target_widget,
                    toast_widget=self,
                    caption=pointer_caption or "",
                    color_hex=border_color,
                )
            else:
                self._pointer_overlay.hide()

        self.raise_()
        self._hide_timer.start(duration_ms)


class _BriefSignals(QObject):
    ready = pyqtSignal(int, int, object, object, object, object)


class _BriefJob(QRunnable):
    """Heavy SQLite and coaching queries execute on background thread for zero UI lag."""

    def __init__(self, serial: int, sid: int):
        super().__init__()
        self.serial = serial
        self.sid = sid
        self.signals = _BriefSignals()

    def run(self):
        try:
            from db import DB_PATH
            from services.student_workspace_v21 import read_workspace_report
            from services.live_student_summary_v3 import read_coach_glance
            from services.adaptive_coaching_v25 import engine
            uri = DB_PATH.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=4)) as con:
                con.execute("PRAGMA query_only=ON")
                report = read_workspace_report(con, self.sid)
                try:
                    coach = read_coach_glance(con, self.sid)
                except Exception:
                    coach = None
                try:
                    topics = engine.student_topics(con, self.sid)
                except Exception:
                    topics = []
            self.signals.ready.emit(self.serial, self.sid, report, coach, topics, None)
        except Exception:
            self.signals.ready.emit(self.serial, self.sid, None, None, None, "read_failed")


class SmartCoachSecretaryController(QObject):
    """Modular Coach Assistant controller hooking student & topic events non-invasively."""

    def __init__(
        self,
        form: QWidget,
        bottom_bar: QHBoxLayout,
        *,
        open_control=None,
        open_adaptive=None,
    ):
        super().__init__(form)
        self.form = form
        self._open_control = open_control
        self._open_adaptive = open_adaptive
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        val = self._settings.value(SETTINGS_KEY_ENABLED, "1")
        self._enabled = str(val).lower() not in ("0", "false", "no", "off")
        self._current_sid: int | None = None
        self._topic_meta: dict[tuple[str, str], dict] = {}
        self._open_hw_count: int = 0
        self._completed_hw_count: int = 0
        self._measured_count: int = 0
        self._hooked_tables: set[int] = set()
        self._suppress_checkbox_toast = False
        self._over_notified_for_sid: int | None = None

        self._proactive = ProactiveGate()
        mode = str(self._settings.value("smart_coach_proactive_mode", "balanced"))
        self._proactive_mode = mode if mode in VALID_MODES else "balanced"
        self._inbox = deque(maxlen=8)
        self._inbox_keys = set()
        self._read_serial = 0
        self._brief_jobs = {}
        self._db_stamp = None
        self._last_direct_input = 0.0
        self._pending_context: dict[str, object] = {}
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(45000)
        self._poll_timer.timeout.connect(self._poll_for_updates)
        self._poll_timer.start()

        self.pointer_overlay = TransparentPointerOverlay(form)
        self.toast = SmartCoachSecretaryToast(
            form,
            open_control=open_control,
            open_adaptive=open_adaptive,
            pointer_overlay=self.pointer_overlay,
        )

        # Toggle button in bottom bar so teacher can enable/disable anytime
        self.toggle_button = QPushButton()
        self.toggle_button.setFixedHeight(24)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle_enabled)
        self.toggle_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.toggle_button.customContextMenuRequested.connect(self._show_assistant_menu)
        self._update_toggle_button_style()
        self._refresh_assistant_tooltip()
        bottom_bar.addWidget(self.toggle_button)

        # "💬 Koça Sor" interactive coaching question button (V12.1)
        self.ask_button = QPushButton("💬 Koça Sor")
        self.ask_button.setFixedHeight(24)
        self.ask_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_button.setToolTip("Seçili öğrenci hakkında yerel kanıtlara dayalı soru sor")
        self.ask_button.setStyleSheet("""
            QPushButton {
                background: #f0fdf4; border: 1px solid #86efac; border-radius: 5px;
                padding: 2px 9px; font-size: 10.5px; font-weight: 700; color: #166534;
            }
            QPushButton:hover { background: #dcfce7; border-color: #22c55e; 
                color: #15191E;}
        """)
        self.ask_button.clicked.connect(lambda _checked=False: self.open_dialogue())
        bottom_bar.addWidget(self.ask_button)
        self._dialogue = None

        form.installEventFilter(self)
        QTimer.singleShot(450, self._ensure_table_hooks)

    def open_dialogue(self, insight=None) -> None:
        """Toggle or display the interactive Koça Sor in-app toast card."""
        from ui.coach_dialogue_v121 import CoachDialogueV121
        if self._dialogue is None:
            self._dialogue = CoachDialogueV121(
                self.form,
                lambda: self.form._secili_ogrenci_id() if hasattr(self.form, "_secili_ogrenci_id") else self._current_sid,
                open_learning=self._open_adaptive,
                open_control=self._open_control,
            )
        if insight is not None:
            self.toast.hide_with_overlay()
            if getattr(self._dialogue, '_compact', False):
                self._dialogue._toggle_compact()
            self._dialogue.show_notification_context(insight)
            self._dialogue.show()
            self._dialogue.raise_()
            return
        if self._dialogue.isVisible():
            if getattr(self._dialogue, "_compact", False):
                self._dialogue._toggle_compact()
            else:
                self._dialogue.hide()
        else:
            self.toast.hide_with_overlay()
            if getattr(self._dialogue, "_compact", False):
                self._dialogue._toggle_compact()
            self._dialogue.show()
            self._dialogue.raise_()

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool, *, show_feedback: bool = True) -> None:
        self._enabled = bool(enabled)
        self._settings.setValue(SETTINGS_KEY_ENABLED, "1" if self._enabled else "0")
        self._update_toggle_button_style()
        self._refresh_assistant_tooltip()
        if not self._enabled:
            self.toast.hide_with_overlay()
        elif show_feedback:
            if self._current_sid:
                self.on_student_changed(self._current_sid, force=True)
            else:
                self.toast.show_toast(
                    title="✨ Koç Asistanı Aktif",
                    step_badge="🧭 Merak Modu",
                    workflow_html="Öğrenci veya konu seçtiğinizde ilginç veri ipuçlarını yarı şeffaf oklarla gösterir.",
                    body_html=(
                        "Ekranınızı kapatmadan, öğrencinin geçmiş verilerindeki dikkat çekici "
                        "detayları ve hangi butonda ne bulacağınızı şeffaf oklarla işaret edeceğim."
                    ),
                    target_widget=self._resolve_target_widget("btnOgrenme"),
                    pointer_caption="✨ Burada: Adaptif Koçluk ve kazanım keşifleri",
                    duration_ms=4800,
                )

    def toggle_enabled(self) -> None:
        self.set_enabled(not self._enabled, show_feedback=True)

    def _update_toggle_button_style(self) -> None:
        if self._enabled:
            count = len(self._inbox) if hasattr(self, "_inbox") else 0
            suffix = f" ({count})" if count else ""
            self.toggle_button.setText(f"✨ Koç Asistanı: Açık{suffix}")
            self.toggle_button.setToolTip(
                "Koç Asistanı aktif: Öğrencinin verilerindeki ilginç detayları yarı şeffaf toast ve oklarla gösterir.\n"
                "Kapatmak için tıklayın; bildirim sıklığı ve geçmiş öneriler için sağ tıklayın."
            )
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background: #eff6ff; border: 1px solid #93c5fd; border-radius: 5px;
                    padding: 2px 8px; font-size: 10.5px; font-weight: 700; color: #1d4ed8;
                }
                QPushButton:hover { background: #dbeafe; border-color: #3b82f6; 
                color: #15191E;}
            """)
        else:
            self.toggle_button.setText("🔕 Koç Asistanı: Kapalı")
            self.toggle_button.setToolTip(
                "Koç Asistanı şu an sessiz modda.\n"
                "Açmak için tıklayın; ayarlar için sağ tıklayın."
            )
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 5px;
                    padding: 2px 8px; font-size: 10.5px; font-weight: 600; color: #64748b;
                }
                QPushButton:hover { background: #f1f5f9; color: #334155; }
            """)

    def _refresh_assistant_tooltip(self) -> None:
        """Expose inbox availability without opening a new UI element."""
        if not hasattr(self, 'toggle_button'):
            return
        count = len(self._inbox)
        original = str(self.toggle_button.toolTip()).split("\n📌", 1)[0]
        self.toggle_button.setToolTip(original + (f"\n📌 {count} öneri: sağ tıklayarak inceleyin." if count else ""))
        if self._enabled:
            suffix = f" ({count})" if count else ""
            self.toggle_button.setText(f"✨ Koç Asistanı: Açık{suffix}")
        else:
            self.toggle_button.setText("🔕 Koç Asistanı: Kapalı")

    def _show_assistant_menu(self, pos) -> None:
        menu = QMenu(self.toggle_button)
        menu.addSection("Bildirim sıklığı")
        for value, title in (
            ("quiet", "🔕 Sessiz (yalnızca gelen kutusu)"),
            ("balanced", "⚖️ Dengeli (önerilen)"),
            ("active", "✨ Daha fazla ipucu"),
        ):
            action = menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(self._proactive_mode == value)
            action.triggered.connect(lambda checked=False, mode=value: self._set_proactive_mode(mode))
        menu.addSeparator()
        menu.addSection("Seçili öğrencinin son önerileri")
        if not self._inbox:
            menu.addAction("Yeni öneri yok").setEnabled(False)
        for insight, source, key in reversed(self._inbox):
            title = str(insight.curiosity_hook).replace("\n", " ")[:95]
            action = menu.addAction(("• " + title)[:100])
            action.triggered.connect(lambda checked=False, entry=insight, src=source, saved=key: self._present_insight(entry, manual=True, source=src, key_override=saved))
        menu.exec(self.toggle_button.mapToGlobal(pos))

    def _set_proactive_mode(self, mode: str) -> None:
        if mode not in VALID_MODES:
            return
        self._proactive_mode = mode
        self._settings.setValue("smart_coach_proactive_mode", mode)
        self._update_toggle_button_style()
        self._refresh_assistant_tooltip()

    def _can_interrupt(self) -> bool:
        if not self.form.isVisible() or not self.form.isActiveWindow():
            return False
        if time.monotonic() - self._last_direct_input < 8.0:
            return False
        if self.toast.isVisible():
            return False
        if self._dialogue is not None and self._dialogue.isVisible():
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractItemView)):
            return False
        return True

    def _resolve_target_widget(self, target_key: str | None) -> QWidget | None:
        if not target_key:
            return None
        if target_key == "curriculum_coverage":
            return getattr(self.form, "_curriculum_scope_button_v237", None)
        if target_key == "btnOgrenme":
            return getattr(self.form, "btnOgrenme", None)
        if target_key == "btnKontrol":
            return getattr(self.form, "btnKontrol", None)
        if target_key == "toggle_360":
            ws = getattr(self.form, "_workspace_v21", None)
            return getattr(ws, "toggle_button", None) if ws is not None else None
        return getattr(self.form, target_key, None)

    def _resolve_action_callback(self, target_key: str | None):
        if target_key == "curriculum_coverage":
            button = getattr(self.form, "_curriculum_scope_button_v237", None)
            return button.click if button is not None else None
        if target_key == "btnKontrol":
            return self._open_control
        if target_key == "toggle_360":
            ws = getattr(self.form, "_workspace_v21", None)
            if ws is not None and hasattr(ws, "panel"):
                return lambda: ws.panel.set_Drawer_open(True) if hasattr(ws.panel, "set_Drawer_open") else ws.panel._toggle()
            return self._open_adaptive
        return self._open_adaptive

    def _present_insight(
        self,
        insight: AssistantInsight,
        *,
        manual: bool = False,
        source: str = "student",
        lesson: str = "",
        topic_name: str = "",
        key_override: str | None = None,
    ) -> None:
        sid = self._current_sid
        if not self._enabled or type(sid) is not int or sid <= 0:
            return
        context = dict(self._pending_context) if source == "student" else {}
        decision = attention_decision(insight, source=source, lesson=lesson, topic_name=topic_name, **context)
        key = key_override or decision.key
        if key not in self._inbox_keys:
            self._inbox.append((insight, source, key))
        else:
            # Keep the newest evidence for the same academic signal without
            # multiplying identical alerts in the teacher's inbox.
            self._inbox = deque((e for e in self._inbox if e[2] != key), maxlen=8)
            self._inbox.append((insight, source, key))
        self._inbox_keys = {k for _, _, k in self._inbox}
        self._refresh_assistant_tooltip()
        if not manual:
            if not decision.auto_eligible:
                return
            verdict = self._proactive.decide(
                student_id=sid,
                key=key,
                priority=decision.priority,
                mode=self._proactive_mode,
                interruptible=self._can_interrupt(),
            )
            if not verdict.show:
                return

        target_w = self._resolve_target_widget(insight.target_key)
        action_cb = self._resolve_action_callback(insight.target_key)
        self.toast.show_toast(
            title=insight.title,
            step_badge=insight.badge,
            workflow_html=(decision.brief_hook or insight.curiosity_hook) if not manual else insight.curiosity_hook,
            body_html=(decision.brief_body or insight.body_html) if not manual else insight.body_html,
            action_text=insight.action_text,
            action_cb=action_cb,
            duration_ms=insight.duration_ms,
            border_color=insight.border_color,
            target_widget=target_w,
            pointer_caption=insight.pointer_caption,
            detail_cb=lambda item=insight: self.open_dialogue(item),
        )

    def _poll_for_updates(self) -> None:
        """Poll SQLite database file/WAL modification stamp; reload only on changes."""
        if not self._enabled or not self._current_sid or not self.form.isVisible():
            return
        try:
            from db import DB_PATH
            stamp = database_stamp(DB_PATH)
        except Exception:
            return
        if self._db_stamp is None:
            self._db_stamp = stamp
            return
        if stamp != self._db_stamp:
            self._db_stamp = stamp
            self._request_briefing(self._current_sid)

    def _request_briefing(self, sid: int) -> None:
        if not self._enabled or sid != self._current_sid:
            return
        if self._brief_jobs:
            return
        self._read_serial += 1
        job = _BriefJob(self._read_serial, sid)
        self._brief_jobs[self._read_serial] = job
        job.signals.ready.connect(self._receive_briefing)
        QThreadPool.globalInstance().start(job)

    def _receive_briefing(self, serial, sid, report, coach, topics, error) -> None:
        self._brief_jobs.pop(serial, None)
        if not self._enabled:
            return
        if sid != self._current_sid or serial != self._read_serial:
            if self._current_sid is not None:
                QTimer.singleShot(0, lambda: self._request_briefing(self._current_sid))
            return
        if error or report is None:
            return
        s, c = report.student, report.control
        self._open_hw_count = int(c.open or 0)
        self._completed_hw_count = int(c.completed or 0)
        self._measured_count = int(coach.evidence_count if coach is not None else 0)
        self._topic_meta = {
            (
                str(t.get("lesson") or "").strip().casefold(),
                str(t.get("topic") or "").strip().casefold(),
            ): t
            for t in (topics or [])
        }
        insight = build_student_curiosity_insight(
            student_id=sid,
            student_name=s.student_name,
            open_hw=self._open_hw_count,
            completed_hw=self._completed_hw_count,
            overdue_hw=int(s.homework_overdue or 0),
            measured_count=self._measured_count,
            evidence_available=coach is not None,
            coach_priority=coach.priority if coach is not None else None,
            coach_next_step=coach.next_step if coach is not None else None,
            topics=topics or [],
        )
        self._pending_context = {
            "topics": tuple(topics or ()),
            "overdue_hw": int(s.homework_overdue or 0),
            "open_hw": self._open_hw_count,
            "completed_hw": self._completed_hw_count,
        }
        try:
            # Golden Balance:
            # In quiet mode: keep silent (inbox only, manual=False).
            # In balanced or active mode: greet teacher with primary student briefing (manual=True).
            auto_show = (self._proactive_mode != "quiet")
            self._present_insight(insight, manual=auto_show, source="student")
        finally:
            self._pending_context.clear()

    def eventFilter(self, obj, event):
        if obj is self.form:
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                if self.toast.isVisible():
                    self.toast.reposition()
                if self._dialogue is not None and self._dialogue.isVisible():
                    self._dialogue.reposition()
            elif event.type() == QEvent.Type.MouseButtonPress:
                if self._dialogue is not None and self._dialogue.isVisible():
                    self._dialogue.raise_()
        return super().eventFilter(obj, event)

    def _ensure_table_hooks(self) -> None:
        tables = getattr(self.form, "_ders_tablolari", None) or {}
        for lesson, table in tables.items():
            tid = id(table)
            if tid not in self._hooked_tables:
                self._hooked_tables.add(tid)
                table.itemChanged.connect(
                    lambda item, tbl=table, d=lesson: self._on_cell_checked(item, tbl, d)
                )

    def on_student_changed(self, sid: int | None, *, force: bool = False) -> None:
        self._ensure_table_hooks()
        if sid is None or sid <= 0:
            self._current_sid = None
            self._read_serial += 1
            self._inbox.clear()
            self._inbox_keys.clear()
            self._pending_context.clear()
            self._refresh_assistant_tooltip()
            self.toast.hide_with_overlay()
            return
        if sid == self._current_sid and not force:
            return
        self._current_sid = sid
        self._read_serial += 1
        self._inbox.clear()
        self._inbox_keys.clear()
        self._pending_context.clear()
        self._refresh_assistant_tooltip()
        self._db_stamp = None
        self.toast.hide_with_overlay()
        self._suppress_checkbox_toast = True
        QTimer.singleShot(350, self._EndSuppress)
        if not self._enabled:
            return
        QTimer.singleShot(180, lambda expected=sid: self._present_student_briefing(expected))

    def _EndSuppress(self) -> None:
        self._suppress_checkbox_toast = False

    def _present_student_briefing(self, expected_sid: int) -> None:
        if self._enabled and expected_sid == self._current_sid:
            self._request_briefing(expected_sid)

    def _on_cell_checked(self, item, table, ders: str) -> None:
        if not self._enabled or self._suppress_checkbox_toast or self._current_sid is None:
            return
        try:
            if item is None or item.column() == 0:
                return
            if item.checkState() != Qt.CheckState.Checked:
                return
            if not bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                return
            topic_item = table.item(item.row(), 0)
            topic_name = topic_item.text().strip() if topic_item is not None else ""
            if not topic_name:
                return
        except Exception:
            return

        self._last_direct_input = time.monotonic()
        meta = self._topic_meta.get((str(ders or "").strip().casefold(), topic_name.casefold()))
        verilen_tbl = getattr(self.form, "verilen", None)
        draft_rows = verilen_tbl.rowCount() if verilen_tbl is not None else 0

        insight = build_topic_curiosity_insight(
            lesson=ders,
            topic_name=topic_name,
            meta=meta,
            draft_rows=draft_rows,
            open_hw_count=self._open_hw_count,
        )
        if insight is not None:
            if insight.target_key == "toggle_360":
                if self._over_notified_for_sid == self._current_sid:
                    return
                self._over_notified_for_sid = self._current_sid
            self._present_insight(insight, manual=False, source="checkbox", lesson=ders, topic_name=topic_name)


# Clean aliases for modular imports
CoachAssistantToast = SmartCoachSecretaryToast
CoachAssistantController = SmartCoachSecretaryController
