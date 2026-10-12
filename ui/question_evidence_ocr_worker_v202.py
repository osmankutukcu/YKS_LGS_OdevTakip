"""V20.2 UI-only background file parsing; no SQLite access in worker thread."""
from __future__ import annotations
from PyQt6.QtCore import QThread, pyqtSignal
from services.question_evidence_v19 import parse_analysis_file


ACTIVE_READERS = set()  # Keep QThreads alive even if their dialog closes.


class ReportReadWorker(QThread):
    report_ready = pyqtSignal(object, object)

    def __init__(self, path: str, student_id: int, exam_id: int, parent=None):
        super().__init__(parent)
        self.path = path
        self.student_id = student_id
        self.exam_id = exam_id

    def run(self):
        try:
            report = parse_analysis_file(self.path, student_id=self.student_id,
                                         exam_id=self.exam_id, allow_ocr=True)
        except Exception as exc:
            # Error is shown in the main thread; no DB changes.
            self.report_ready.emit(None, str(exc))
        else:
            self.report_ready.emit(report, None)
