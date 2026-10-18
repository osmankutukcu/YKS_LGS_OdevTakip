"""Optional V24.2 student-scoped GUI refresh bridge on V24.1 SQLite probe.

This bridge never writes DB rows.  With a known student context, refresh is
issued only if that student's relevant records changed; otherwise we fall back
to V24.1 generic behavior.  No cross-device/cloud event delivery.
"""
from __future__ import annotations
import os
import weakref
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QApplication
from services.live_change_probe_v241 import DatabaseChangeProbe
from services.student_change_scope_v242 import StudentChangeRouter
from services.course_topic_scope_v243 import CourseTopicScope

_bridges = {}

class _Bridge(QObject):
    def __init__(self, path, application):
        super().__init__(application)
        self.probe = DatabaseChangeProbe(path)
        self.router = StudentChangeRouter()
        self.course_router = CourseTopicScope()
        self._subscribers = []  # (weak widget, weak callback, student field, course field)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._tick)
        self.probe.poll()  # baseline for cross-connection commits
        self.timer.start()
        application.aboutToQuit.connect(self.probe.close)

    def _student(self, widget, attribute):
        if not attribute or widget is None:return None
        try:
            value=getattr(widget, attribute, None)
            if callable(value):value=value()
            return value if type(value) is int and value > 0 else None
        except (RuntimeError,TypeError,ValueError,AttributeError):
            return None

    def _course(self, widget, attr):
        if not attr or widget is None:return None
        try:
            value=getattr(widget,attr,None)
            if callable(value):value=value()
            return value if isinstance(value,str) and value.strip() else None
        except (RuntimeError,TypeError,ValueError,AttributeError):return None

    def subscribe(self, widget, callback, student_attr=None, course_attr=None):
        self._subscribers.append((weakref.ref(widget),weakref.WeakMethod(callback),student_attr,course_attr))
        widget.destroyed.connect(self._cleanup)
        sid=self._student(widget,student_attr)
        if sid is not None and self.probe.connected and sid not in self.router._baseline:
            try:self.router.baseline(self.probe._connection,sid)
            except Exception:pass  # safely retry as unknown after commit
        course=self._course(widget,course_attr)
        if sid is not None and course and self.probe.connected:
            try:self.course_router.baseline(self.probe._connection,sid,course)
            except Exception:pass
        if not self.timer.isActive():self.timer.start()

    def _cleanup(self, *_):
        self._subscribers=[(w,cb,a,c) for w,cb,a,c in self._subscribers
                           if w() is not None and cb() is not None]

    def _visible(self, widget):
        if widget is None:return False
        try:return widget.isVisible()
        except RuntimeError:return False

    def _tick(self):
        self._cleanup()
        if not self._subscribers:
            self.timer.stop();self.probe.close()
            for path, bridge in list(_bridges.items()):
                if bridge is self:del _bridges[path]
            self.deleteLater();return
        visible=[(w(),cb(),attr,course) for w,cb,attr,course in self._subscribers
                 if cb() is not None and self._visible(w())]
        if not visible:return
        if not self.probe.poll():return
        student_ids={sid for widget,_,attr,_ in visible
                     if (sid:=self._student(widget,attr)) is not None}
        changed={}
        if student_ids:
            if self.probe.connected:
                changed=self.router.after_commit(self.probe._connection,student_ids)
            else:
                # Missing DB / probe error: don't incorrectly claim no change.
                changed={sid:True for sid in student_ids}
        for widget, callback, attr, course_attr in visible:
            sid=self._student(widget,attr)
            if attr and sid is not None and sid not in changed:continue
            if attr and sid is None:continue  # student not selected; never mix
            course=self._course(widget,course_attr)
            if course_attr and course and sid is not None and self.probe.connected:
                decision=self.course_router.on_commit(self.probe._connection,changed[sid],course)
                if not decision.refresh:continue
            try:callback()
            except (RuntimeError,OSError,ValueError) as exc:
                print('Optional read-only refresh skipped:',type(exc).__name__)

def install_live_updates(widget, callback, *, student_attr=None, course_attr=None):
    """Attach optional refresh; student_attr names a widget field or 0-arg method."""
    if os.environ.get('YKS_LIVE_CHANGE_EVENTS','1').strip().lower() in ('0','false','off'):
        return False
    app=QApplication.instance()
    if app is None:return False
    from db import DB_PATH
    key=str(Path(DB_PATH).expanduser().resolve())
    bridge=_bridges.get(key)
    if bridge is None:
        bridge=_Bridge(key,app);_bridges[key]=bridge
    bridge.subscribe(widget,callback,student_attr,course_attr)
    return True
