"""tests/test_routine_homework.py

Paragraf ve Problemler hızlı rutin ödev yardımcısı ve arayüz şeridi testleri.
"""
import pytest
from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt
from services.routine_homework_helper import (
    load_routine_defaults, save_routine_defaults, generate_routine_tasks
)
from ui.routine_homework_bar import RoutineHomeworkBar

app = QApplication.instance() or QApplication([])


def test_load_and_save_routine_defaults(tmp_path, monkeypatch):
    test_file = tmp_path / "routine_test.json"
    import services.routine_homework_helper as mod
    monkeypatch.setattr(mod, "_get_routine_settings_file", lambda: test_file)

    # Initial default
    prefs = load_routine_defaults("paragraf")
    assert prefs["soru"] == 20
    assert prefs["sure"] == 25

    # Save custom
    save_routine_defaults("paragraf", soru=25, sure=30, gun=7)
    loaded = load_routine_defaults("paragraf")
    assert loaded["soru"] == 25
    assert loaded["sure"] == 30
    assert loaded["gun"] == 7

    # Distinct for problemler
    save_routine_defaults("problemler", soru=18, sure=35, gun=5)
    loaded_p = load_routine_defaults("problemler")
    assert loaded_p["soru"] == 18
    assert loaded_p["sure"] == 35
    assert loaded_p["gun"] == 5


def test_generate_routine_tasks_single_book():
    # Setup mock table with 10 rows and 2 columns (0: Konu, 1: Book1)
    table = QTableWidget(10, 2)
    table.setHorizontalHeaderLabels(["Konu", "345 Problemler"])
    for r in range(10):
        table.setItem(r, 0, QTableWidgetItem(f"PROBLEMLER-{r+1}"))
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        table.setItem(r, 1, item)

    # Mark row 0 as checked, row 1 as locked
    table.item(0, 1).setCheckState(Qt.CheckState.Checked)
    table.item(1, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)  # Not checkable

    tasks = generate_routine_tasks(
        lesson="problemler",
        books=["345 Problemler"],
        selected_book_mode="345 Problemler",
        days_count=7,
        questions_per_day=15,
        duration_minutes=30,
        table=table
    )

    # Model 1: 1 Satır = 1 Hafta (Yalnızca 1 görev ve 1 satır tüketilir)
    assert len(tasks) == 1
    # Satır 0 ve 1 dolu/kilitli olduğu için satır 2'den (PROBLEMLER-3) başlar
    assert tasks[0]["konu"] == "PROBLEMLER-3"
    assert tasks[0]["kitap"] == "345 Problemler"
    assert tasks[0]["dk"] == 210  # 7 gün * 30 dk
    assert tasks[0]["_row"] == 2
    assert "105 Soru / 210 dk" in tasks[0]["aciklama"]
    assert "Günde 15" in tasks[0]["aciklama"]


def test_generate_routine_tasks_alternating_multiple_books():
    # Setup table with 2 books: BookA and BookB
    table = QTableWidget(10, 3)
    table.setHorizontalHeaderLabels(["Konu", "BookA", "BookB"])
    for r in range(10):
        table.setItem(r, 0, QTableWidgetItem(f"PARAGRAF-{r+1}"))
        for c in (1, 2):
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            table.setItem(r, c, item)

    tasks = generate_routine_tasks(
        lesson="paragraf",
        books=["BookA", "BookB"],
        selected_book_mode="__ALL_ALTERNATING__",
        days_count=7,
        questions_per_day=20,
        duration_minutes=25,
        table=table
    )

    # Model 1 Dönüşümlü: 2 kitap için 2 görev ama AYNI HAFTAYA (Satır 0)
    assert len(tasks) == 2
    assert tasks[0]["kitap"] == "BookA"
    assert tasks[0]["_row"] == 0
    assert tasks[0]["dk"] == 100  # 4 gün * 25 dk
    assert "80 Soru / 100 dk" in tasks[0]["aciklama"]

    assert tasks[1]["kitap"] == "BookB"
    assert tasks[1]["_row"] == 0
    assert tasks[1]["dk"] == 75   # 3 gün * 25 dk
    assert "60 Soru / 75 dk" in tasks[1]["aciklama"]


def test_routine_bar_widget(tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    import services.routine_homework_helper as mod
    monkeypatch.setattr(mod, "_get_routine_settings_file", lambda: tmp_path / "routine.json")
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kw: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kw: None)
    table = QTableWidget(10, 2)
    table.setHorizontalHeaderLabels(["Konu", "Limit Paragraf"])
    for r in range(10):
        table.setItem(r, 0, QTableWidgetItem(f"PARAGRAF-{r+1}"))
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        table.setItem(r, 1, item)

    class DummyParent:
        def __init__(self):
            self.transferred = []
        def _wizard_transfer_tasks(self, tasks, *, expected_student_id):
            self.transferred = tasks
            return {"added": len(tasks)}

    parent = DummyParent()
    bar = RoutineHomeworkBar(
        ogr_id=42,
        ders="paragraf",
        books=["Limit Paragraf"],
        table=table,
        parent_form=parent
    )

    assert bar.sp_soru.value() > 0
    assert bar.sp_sure.value() > 0
    assert bar.cmb_book.count() >= 1

    # Track notifications
    notifs = []
    bar._notify = lambda msg, kind="success": notifs.append((msg, kind))

    # Direct 1-click test (7 gün varsayılan)
    bar.btn_assign.click()
    assert len(parent.transferred) == 1
    assert parent.transferred[0]["ders"] == "paragraf"
    assert parent.transferred[0]["kitap"] == "Limit Paragraf"
    assert parent.transferred[0]["konu"] == "PARAGRAF-1"
    assert parent.transferred[0]["dk"] == 175  # 7 * 25 dk
    assert len(notifs) == 1
    assert "rutini eklendi" in notifs[0][0]
    assert notifs[0][1] == "success"

    # Set to 5 days
    bar._set_days_and_assign(5)
    assert len(parent.transferred) == 1
    assert parent.transferred[0]["dk"] == 125  # 5 * 25 dk
    assert "5 Gün" in bar.btn_assign.text()
    assert len(notifs) == 2



