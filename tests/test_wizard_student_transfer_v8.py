"""V8 Sihirbaz ödev aktarımı ve öğrenci ID koruması.

Qt bulunmayan CI ortamında gerçek metotların AST gövdesini izole ederek
fake grid ile test eder; Windows grafik kabul testinin yerini tutmaz.
"""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.wizard_integrity_v8 import (
    normalized_identity, same_student, exact_task_key, find_exact_cell, valid_task
)
ROOT = Path(__file__).resolve().parents[1]


def compiled_class(path, class_name, methods):
    node = next(x for x in ast.parse(path.read_text('utf-8')).body
                if isinstance(x, ast.ClassDef) and x.name == class_name)
    chosen = []
    for name in methods:
        m = next((v for v in reversed(node.body) if isinstance(v, ast.FunctionDef) and v.name == name), None)
        if m is None:
            raise AssertionError(name)
        chosen.append(m)
    cls = ast.ClassDef(name='MethodsUnderTest', bases=[], keywords=[], body=chosen, decorator_list=[])
    mod = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    scope = {'db': None}
    exec(compile(mod, str(path), 'exec'), scope)
    return scope['MethodsUnderTest']


FORM = compiled_class(ROOT/'ui/homework_form.py', 'OdevTakipFormu', [
    '_wizard_transfer_tasks', '_sync_verilen_rows_from_table'
])
DIALOG = compiled_class(ROOT/'ui/smart_wizard_dialog.py', 'SmartWizardDialog', [
    '_load_students', '_get_current_oid', '_on_student_combo_changed'
])


class FakeQt:
    class ItemFlag:
        ItemIsUserCheckable = 2
    class CheckState:
        Unchecked = 0
        Checked = 2


class FakeMessage:
    shown = []
    @classmethod
    def warning(cls, *args): cls.shown.append(('warning', args[-1]))
    @classmethod
    def information(cls, *args): cls.shown.append(('information', args[-1]))


class FakeCell:
    def __init__(self, text='', *, flags=FakeQt.ItemFlag.ItemIsUserCheckable, state=0, color='#ffffff'):
        self.content = str(text)
        self._flags, self._state, self.color = flags, state, color
        self.owner = None
    def text(self): return self.content
    def setText(self, value): self.content = str(value)
    def flags(self): return self._flags
    def checkState(self): return self._state
    def setCheckState(self, value):
        self._state = value
        if self.owner:
            self.owner.pending = True
    def background(self): return types.SimpleNamespace(color=lambda: types.SimpleNamespace(name=lambda: self.color))


class FakeMatrix:
    def __init__(self, book='FİZİK1', topic='Elektrostatik', cell=None):
        self.book = FakeCell(book)
        self.topics = [FakeCell(topic), FakeCell('Elektrostatik Ek')]
        self.cells = [cell or FakeCell(), FakeCell()]
        for i in self.cells: i.owner = self
        self.pending = False
        self.parent = None
    def rowCount(self): return len(self.topics)
    def columnCount(self): return 2
    def horizontalHeaderItem(self, c): return self.book if c == 1 else None
    def item(self, r, c): return self.topics[r] if c == 0 else self.cells[r]
    def _checkbox_flush(self):
        if not self.pending: return
        self.pending = False
        host = self.parent
        for r, cell in enumerate(self.cells):
            key = exact_task_key('fizik', self.book.text(), self.topics[r].text())
            host.given.rows = [x for x in host.given.rows if exact_task_key(*(x[k] for k in ('ders','kitap','konu'))) != key]
            if cell.checkState() == FakeQt.CheckState.Checked:
                host.given.rows.append({'ders': 'fizik', 'kitap': self.book.text(),
                                        'konu': self.topics[r].text(), 'sure': '75', 'aciklama': ''})


class GivenTable:
    def __init__(self): self.rows = []
    def rowCount(self): return len(self.rows)
    def item(self, r, c):
        keys = ('ders','kitap','konu','sure','aciklama')
        row = self.rows[r]
        return types.SimpleNamespace(text=lambda: row[keys[c]], setText=lambda v: row.__setitem__(keys[c],str(v)))


class Host(FORM):
    def __init__(self, student=18, loaded=18, cell=None):
        self.student = student
        self._loaded_student_id = loaded
        self.given = GivenTable()
        self.verilen = self.given
        self._in_verilen_update = False
        self.matrix = FakeMatrix(cell=cell)
        self.matrix.parent = self
        self._ders_tablolari = {'fizik': self.matrix}
        self.total_updates = 0
    def _secili_ogrenci_id(self): return self.student
    def _flush_checkbox_queues(self): self.matrix._checkbox_flush()
    def _vtext(self, r, c): return self.verilen.item(r,c).text()
    def _toplam_sure_guncelle(self): self.total_updates += 1


def task(ders='fizik', kitap='FİZİK1', konu='Elektrostatik', dk=45, reason='Tekrar'):
    return {'ders': ders, 'kitap': kitap, 'konu': konu, 'dk': dk, 'reason': reason}


class Combo:
    def __init__(self): self.rows=[]; self.idx=-1; self.block=False
    def blockSignals(self, value): old=self.block; self.block=value; return old
    def clear(self): self.rows=[];self.idx=-1
    def addItem(self, text, data): self.rows.append((text,data));self.idx = 0 if self.idx < 0 else self.idx
    def setCurrentIndex(self,i): self.idx=i
    def currentData(self): return self.rows[self.idx][1] if self.idx >= 0 else None
    def currentText(self): return self.rows[self.idx][0] if self.idx >= 0 else ''


class Conn:
    rows = [dict(id=2, ad='Ali',soyad='Veli',aktif=1),dict(id=18,ad='Osman',soyad='Fizik',aktif=1)]
    def execute(self, sql, args=()):
        if 'aktif=1' in sql: return types.SimpleNamespace(fetchall=lambda: self.rows)
        return types.SimpleNamespace(fetchone=lambda: next((r for r in self.rows if r['id']==args[0]),None))
    def close(self): pass


class StudentDialog(DIALOG):
    def __init__(self, sid):
        self.fixed_student_id = sid
        self.ogrenci_id = sid
        self._student_scope_error = None
        self.cmbStudent = Combo()
    def _run_analysis(self): pass


class TestWizardIdentity(unittest.TestCase):
    def test_ids_equal_str_int(self): self.assertTrue(same_student('018',18))
    def test_empty_id_rejected(self):
        for bad in ('x',None,0,-1,False): self.assertIsNone(normalized_identity(bad))
    def test_selected_student_not_first(self):
        with patch.dict(sys.modules, {}):
            # Method global db injected after compilation
            DIALOG._load_students.__globals__['db'] = types.SimpleNamespace(get_conn=Conn)
            dlg = StudentDialog(18)
            dlg._load_students()
            self.assertEqual(dlg.cmbStudent.currentText(), 'Osman Fizik')
            self.assertEqual(dlg._get_current_oid(), 18)
            self.assertEqual(len(dlg.cmbStudent.rows), 1)
    def test_missing_id_never_falls_back_to_ali(self):
        DIALOG._load_students.__globals__['db'] = types.SimpleNamespace(get_conn=Conn)
        dlg = StudentDialog(50)
        dlg._load_students()
        self.assertIsNone(dlg._get_current_oid())
        self.assertIn('bulunamadı',dlg.cmbStudent.currentText())
    def test_wrong_combo_id_refused(self):
        DIALOG._load_students.__globals__['db'] = types.SimpleNamespace(get_conn=Conn)
        dlg = StudentDialog(18)
        dlg._load_students()
        dlg.cmbStudent.rows = [('Ali Veli',2)]
        self.assertIsNone(dlg._get_current_oid())


class TestExactMatch(unittest.TestCase):
    def test_no_partial_topic(self):
        self.assertIsNone(find_exact_cell({'fizik': FakeMatrix()}, 'fizik','FİZİK1','Elektro')[0])
    def test_casefold_and_whitespace(self):
        t, r, c = find_exact_cell({'fizik':FakeMatrix()},' FİZİK ', ' fizİk1 ', ' Elektrostatik ')
        self.assertIsNotNone(t)
        self.assertEqual((r,c),(0,1))
    def test_incomplete_task_rejected(self): self.assertFalse(valid_task(task(kitap='')))


class TestTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_pyqt6 = sys.modules.get('PyQt6')
        cls._orig_pyqt6_core = sys.modules.get('PyQt6.QtCore')
        fakeqt_module = types.ModuleType('PyQt6.QtCore')
        fakeqt_module.Qt = FakeQt
        sys.modules['PyQt6'] = types.ModuleType('PyQt6')
        sys.modules['PyQt6.QtCore'] = fakeqt_module
        FORM._wizard_transfer_tasks.__globals__['QMessageBox'] = FakeMessage

    @classmethod
    def tearDownClass(cls):
        if cls._orig_pyqt6 is not None:
            sys.modules['PyQt6'] = cls._orig_pyqt6
        else:
            sys.modules.pop('PyQt6', None)
        if cls._orig_pyqt6_core is not None:
            sys.modules['PyQt6.QtCore'] = cls._orig_pyqt6_core
        else:
            sys.modules.pop('PyQt6.QtCore', None)

    def setUp(self): FakeMessage.shown.clear()
    def test_normal_manual_round_trip(self):
        h=Host()
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],1)
        self.assertEqual(h.verilen.rowCount(),1)
        self.assertEqual(h.given.rows[0]['sure'],'45')
        self.assertEqual(h.given.rows[0]['aciklama'],'Tekrar')
        self.assertEqual(len(h._verilen_rows),1)
        # Öğretmen daha sonra aynı kutuya normal tıkladığında verilen ödev de kalkar
        h.matrix.cells[0].setCheckState(FakeQt.CheckState.Unchecked)
        h.matrix._checkbox_flush()
        h._sync_verilen_rows_from_table()
        self.assertEqual(h.verilen.rowCount(),0)
        self.assertEqual(h._verilen_rows,[])
        self.assertTrue(h.matrix.cells[0].flags() & FakeQt.ItemFlag.ItemIsUserCheckable)
    def test_transfer_different_student_aborts(self):
        h=Host(student=18,loaded=18)
        result=h._wizard_transfer_tasks([task()],expected_student_id=2)
        self.assertEqual(result['added'],0)
        self.assertEqual(h.matrix.cells[0].checkState(),0)
    def test_stale_grid_aborts(self):
        h=Host(student=18,loaded=2)
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],0)
    def test_unmatched_does_not_add_or_tick(self):
        h=Host()
        result=h._wizard_transfer_tasks([task(konu='Elektro')],expected_student_id=18)
        self.assertEqual(result['skipped'],1)
        self.assertEqual(h.verilen.rowCount(),0)
    def test_protected_history_not_unlocked(self):
        h=Host(cell=FakeCell(flags=0,state=2,color='#a5d6a7'))
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],0)
        self.assertEqual(h.matrix.cells[0].checkState(),2)
    def test_fake_locked_color_not_unlocked(self):
        h=Host(cell=FakeCell(flags=2,state=0,color='#fff59d'))
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],0)
    def test_duplicate_tasks_once(self):
        h=Host()
        result=h._wizard_transfer_tasks([task(),task()],expected_student_id=18)
        self.assertEqual(result['added'],1)
        self.assertEqual(h.verilen.rowCount(),1)
        self.assertEqual(result['skipped'],1)
    def test_duplicate_existing_table_unchanged(self):
        h=Host()
        h.given.rows.append({'ders':'fizik','kitap':'FİZİK1','konu':'Elektrostatik','sure':'90','aciklama':'Mevcut'})
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],0)
        self.assertEqual(h.given.rows[0]['sure'],'90')
    def test_nonpositive_duration_keeps_manual_default(self):
        h=Host()
        result=h._wizard_transfer_tasks([task(dk=0)],expected_student_id=18)
        self.assertEqual(result['added'],1)
        self.assertEqual(h.given.rows[0]['sure'],'75')
    def test_sync_failure_reverts_checkbox(self):
        h=Host()
        h.matrix._checkbox_flush = lambda: None
        result=h._wizard_transfer_tasks([task()],expected_student_id=18)
        self.assertEqual(result['added'],0)
        self.assertEqual(h.matrix.cells[0].checkState(),0)
        self.assertEqual(h.verilen.rowCount(),0)


if __name__=='__main__': unittest.main()
