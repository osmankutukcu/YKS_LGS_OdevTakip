"""V3.5.8 UI perf yaması: Qt'ye ihtiyaç duymayan işlev/regresyon testleri.
Gerçek Windows PyQt6 GUI kabul testinin yerini tutmaz.
"""
import ast
import random
import unittest
from pathlib import Path

from utils.checkbox_dispatch import PendingCheckboxChanges


SRC = Path(__file__).resolve().parents[1] / 'ui' / 'homework_form.py'


class TestPendingChanges(unittest.TestCase):
    def test_initially_empty(self):
        q = PendingCheckboxChanges()
        self.assertFalse(q)
        self.assertEqual(q.drain(), ())

    def test_one_cell(self):
        q = PendingCheckboxChanges()
        q.push(1, 2)
        self.assertTrue(q)
        self.assertEqual(q.drain(), ((1, 2),))
        self.assertFalse(q)

    def test_unique_last_cell(self):
        q = PendingCheckboxChanges()
        for _ in range(500):
            q.push(3, 4)
        self.assertEqual(len(q), 1)
        self.assertEqual(q.drain(), ((3, 4),))

    def test_first_seen_order_different_cells(self):
        q = PendingCheckboxChanges()
        for cell in [(2, 5), (1, 6), (2, 5), (3, 7), (1, 6)]:
            q.push(*cell)
        self.assertEqual(q.drain(), ((2, 5), (1, 6), (3, 7)))

    def test_late_changes_do_not_disappear(self):
        q = PendingCheckboxChanges()
        q.push(1, 1)
        first = q.drain()
        q.push(2, 1)
        self.assertEqual(first, ((1, 1),))
        self.assertEqual(q.drain(), ((2, 1),))

    def test_tenants_and_lessons_separate_queues(self):
        a, b = PendingCheckboxChanges(), PendingCheckboxChanges()
        a.push(2, 1)
        b.push(2, 1)
        a.push(3, 1)
        self.assertEqual(a.drain(), ((2, 1), (3, 1)))
        self.assertEqual(b.drain(), ((2, 1),))

    def test_terminal_checked_state_same_as_sequential(self):
        random.seed(154)
        for _ in range(70):
            terminal = {(r, c): False for r in range(20) for c in range(1, 6)}
            q = PendingCheckboxChanges()
            seq = []
            for _ in range(300):
                k = (random.randrange(20), random.randrange(1, 6))
                terminal[k] = not terminal[k]
                seq.append((k, terminal[k]))
                q.push(*k)
            # İşaret/geri alma nihai durumları eski sırayla işlendiğinde
            # oluşan sonuç, tekil son durumlarla aynıdır.
            expected = {}
            for k, state in seq:
                expected[k] = state
            actual = {k: terminal[k] for k in q.drain()}
            self.assertEqual(actual, {k: expected[k] for k in actual})


class TestCodeBehaviorGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SRC.read_text('utf-8')
        cls.tree = ast.parse(cls.src)
        cls.form = next(n for n in cls.tree.body if isinstance(n, ast.ClassDef) and n.name == 'OdevTakipFormu')

    def method(self, name):
        return [n for n in self.form.body if isinstance(n, ast.FunctionDef) and n.name == name][-1]

    def test_tik_method_still_present(self):
        n = self.method('_tik_degisti')
        s = ast.get_source_segment(self.src, n)
        self.assertIn('self._tahmini_sure(', s)
        self.assertIn('self.verilen.insertRow(', s)
        self.assertIn('self.verilen.removeRow(', s)
        self.assertIn('self._toplam_sure_guncelle()', s)

    def test_duration_formula_unchanged(self):
        n = self.method('_tahmini_sure')
        s = ast.get_source_segment(self.src, n)
        self.assertIn('konu_helper.get_active_list', s)
        self.assertIn('return self._get_default_sure()', s)

    def test_each_table_owns_timer(self):
        src = ast.get_source_segment(self.src, self.method('_ders_tab_olustur'))
        self.assertIn('ic_timer = QtCore.QTimer(table)', src)
        self.assertIn('ic_timer.setInterval(0)', src)
        self.assertIn('ic_timer.timeout.connect(_ic_flush)', src)
        self.assertIn('table._checkbox_flush = _ic_flush', src)
        self.assertNotIn('self._ic_timer', src)
        self.assertNotIn('self._ic_queue', src)

    def test_lock_rules_remain(self):
        src = ast.get_source_segment(self.src, self.method('_ders_tab_olustur'))
        self.assertIn('ItemIsUserCheckable', src)
        self.assertIn('_is_locked_index', src)
        self.assertIn('LOCKED_COLORS', src)

    def test_flash_does_not_cover_check(self):
        src = ast.get_source_segment(self.src, self.method('_ders_tab_olustur'))
        flash = src.split('# 3. Flash efekti',1)[1].split('def _toggle',1)[0]
        self.assertNotIn('setBrush(QColor("#93C5FD"))', flash)
        self.assertIn('QColor("#2563EB")', flash)

    def test_save_flushes_queued_toggles(self):
        src = ast.get_source_segment(self.src, self.method('_kaydet_kume'))
        self.assertIn('self._flush_checkbox_queues()', src)

    def test_style_updates_short_circuit(self):
        src = ast.get_source_segment(self.src, self.method('_set_style_if_changed'))
        self.assertIn('if widget.styleSheet() != style:', src)


if __name__ == '__main__':
    unittest.main()
