"""V13.4: targeted checks around draft / saved status and exact-cell flows.
Uses mock Qt so it is safe in headless CI; not a substitute for real desktop UX tests.
"""
import ast
import contextlib
import types
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'ui' / 'homework_form.py').read_text('utf-8')
TREE = ast.parse(SOURCE)
FORM = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'OdevTakipFormu')


def isolate(*methods):
    selected=[]
    for name in methods:
        matches=[n for n in FORM.body if isinstance(n,ast.FunctionDef) and n.name==name]
        assert matches, name
        selected.append(matches[-1])
    node=ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='Form',bases=[],keywords=[],body=selected,decorator_list=[])],type_ignores=[]))
    env={}
    exec(compile(node,str(ROOT/'ui/homework_form.py'),'exec'),env)
    return env['Form'],env


class QtFake:
    class ItemFlag:
        ItemIsUserCheckable=2
        ItemIsEnabled=4
        ItemIsSelectable=8
        ItemIsEditable=16
    class CheckState:
        Unchecked=0
        Checked=2
    class GlobalColor:
        transparent='transparent'
    class ItemDataRole:
        UserRole=32


class TextCell:
    def __init__(self, value='',flags=QtFake.ItemFlag.ItemIsUserCheckable|QtFake.ItemFlag.ItemIsEnabled,state=0):
        self.value=str(value)
        self._flags=flags
        self.state=state
        self.color=None
        self.extras={}
    def text(self):return self.value
    def setText(self,t):self.value=str(t)
    def flags(self):return self._flags
    def setFlags(self,f):self._flags=f
    def setCheckState(self,x):self.state=x
    def checkState(self):return self.state
    def setBackground(self,c):self.color=c
    def setToolTip(self,text):self.tip=text
    def setData(self,key,value):self.extras[key]=value
    def data(self,key):return self.extras.get(key)


class FakeGrid:
    def __init__(self, topic='Elektrostatik', book='Fizik 1', duplicates=False):
        self.topics=[TextCell(topic),TextCell('Elektrostatik Ek')]
        if duplicates:self.topics.append(TextCell(topic))
        self.cells=[TextCell() for _ in self.topics]
        self.book=TextCell(book)
        self.signals=[]
    def rowCount(self):return len(self.topics)
    def columnCount(self):return 2
    def item(self,r,c):return self.topics[r] if c==0 else self.cells[r]
    def horizontalHeaderItem(self,c):return self.book if c==1 else None
    def blockSignals(self,x):self.signals.append(x)


class FakeGiven:
    def __init__(self,rows): self.rows=[list(r) for r in rows];self.sort=True
    def rowCount(self):return len(self.rows)
    def item(self,r,c):return self.rows[r][c]
    def isSortingEnabled(self):return self.sort
    def setSortingEnabled(self,x):self.sort=x
    def blockSignals(self,x):pass
    def removeRow(self,i):self.rows.pop(i)
    def insertRow(self,i):self.rows.insert(i,[None]*5)
    def setItem(self,r,c,x):self.rows[r][c]=x


def given_row(topic='Elektrostatik'):
    return [TextCell('fizik'),TextCell('Fizik 1'),TextCell(topic),TextCell('45'),TextCell('')]


class FakeMessage:
    calls=[]
    @classmethod
    def warning(cls,*args):cls.calls.append(('warn',args[-1]))
    @classmethod
    def information(cls,*args):cls.calls.append(('info',args[-1]))


class FakeConn:
    def execute(self,sql,args=()):return types.SimpleNamespace(fetchall=lambda:[])


class TestV134AST(unittest.TestCase):
    def test_single_active_checkbox_handler(self):
        self.assertEqual(len([x for x in FORM.body if isinstance(x,ast.FunctionDef) and x.name=='_tik_degisti']),1)
    def test_save_no_longer_matches_topic_using_substring(self):
        m=next(x for x in FORM.body if isinstance(x,ast.FunctionDef) and x.name=='_kaydet_kume')
        body=ast.unparse(m)
        self.assertIn('unique_exact_cell',body)
        self.assertNotIn('hedef_satir',body)
        self.assertIn('same_student',body)
        self.assertIn('self._mute_table(table)',body)
    def test_status_paths_exact_and_never_unlock_recorded_tasks(self):
        for name in ('_odev_kayit_sonucu_tamamlanan','_uygula_aktar_listesi'):
            body=ast.unparse(next(x for x in FORM.body if isinstance(x,ast.FunctionDef) and x.name==name))
            self.assertNotIn('hedef_satir',body)
        body=ast.unparse(next(x for x in FORM.body if isinstance(x,ast.FunctionDef) and x.name=='_uygula_aktar_listesi'))
        self.assertIn('_wizard_transfer_tasks',body)
        self.assertNotIn('ItemIsUserCheckable',body)
    def test_status_refresh_has_student_gate_and_draft_protection(self):
        body=ast.unparse(next(x for x in FORM.body if isinstance(x,ast.FunctionDef) and x.name=='_senkronize_odev_durumlari'))
        self.assertIn('same_student',body)
        self.assertIn('draft_keys',body)


class TestV134Behavior(unittest.TestCase):
    def setUp(self):
        self.fakepy=types.ModuleType('PyQt6');self.fakepy.__path__=[]
        self.fakecore=types.ModuleType('PyQt6.QtCore');self.fakecore.Qt=QtFake
        self.fakewidgets=types.ModuleType('PyQt6.QtWidgets')
        self.fakewidgets.QTableWidgetItem=TextCell
        self.fakewidgets.QMessageBox=FakeMessage
        self.fakegui=types.ModuleType('PyQt6.QtGui');self.fakegui.QColor=lambda s:s
        self.patcher=patch.dict(sys.modules,{'PyQt6':self.fakepy,'PyQt6.QtCore':self.fakecore,
                                            'PyQt6.QtWidgets':self.fakewidgets,
                                            'PyQt6.QtGui':self.fakegui})
        self.patcher.start();FakeMessage.calls.clear()
    def tearDown(self):self.patcher.stop()

    def test_repeated_right_rows_all_removed_after_uncheck(self):
        cls,env=isolate('_tik_degisti')
        env.update({'Qt':QtFake,'QTableWidgetItem':TextCell})
        g=FakeGrid();g.cells[0].state=0
        obj=cls();obj.verilen=FakeGiven([given_row(),given_row(),given_row('Elektrostatik Ek')]);obj._in_verilen_update=False
        obj._tahmini_sure=lambda *_:45;obj._get_default_sure=lambda:45
        obj._toplam_sure_guncelle=lambda:None
        obj._sync_verilen_rows_from_table=lambda:setattr(obj,'synced',True)
        # V8 exact name normalization uses Turkish case conversion.
        class Active(TextCell):
            def row(self):return 0
            def column(self):return 1
        cell=Active(state=0)
        cls._tik_degisti(obj,cell,g,'fizik')
        self.assertEqual(obj.verilen.rowCount(),1)
        self.assertEqual(obj.verilen.item(0,2).text(),'Elektrostatik Ek')
        self.assertTrue(obj.synced)

    def test_legacy_return_path_fails_closed_on_student(self):
        cls,_=isolate('_uygula_aktar_listesi')
        obj=cls();obj._secili_ogrenci_id=lambda:18
        captured=[]
        obj._wizard_transfer_tasks=lambda tasks,expected_student_id: captured.append((tasks,expected_student_id)) or {'added':1}
        ret=obj._uygula_aktar_listesi([{'ders':'fizik','kitap':'Fizik 1','konu':'Elektrostatik'}])
        self.assertEqual(ret['added'],1)
        self.assertEqual(captured[0][1],18)
        self.assertEqual(len(captured[0][0]),1)

    def test_completion_marks_only_exact_cell_and_mutes_signals(self):
        cls,env=isolate('_odev_kayit_sonucu_tamamlanan')
        env['OVERDUE_FLAG_ROLE']=44;env['OVERDUE_DAYS_ROLE']=45
        obj=cls();obj._secili_ogrenci_id=lambda:18;obj._loaded_student_id=18
        obj._ders_tablolari={'fizik':FakeGrid()}
        @contextlib.contextmanager
        def mute(table):
            table.blockSignals(True)
            try:yield
            finally:table.blockSignals(False)
        obj._mute_table=mute
        obj._odev_kayit_sonucu_tamamlanan([{'ders':'fizik','kitap':'Fizik 1','konu':'Elektrostatik'}])
        g=obj._ders_tablolari['fizik']
        self.assertEqual(g.cells[0].checkState(),2)
        self.assertEqual(g.cells[1].checkState(),0)
        self.assertEqual(g.signals,[True,False])
        self.assertFalse(g.cells[0].flags() & QtFake.ItemFlag.ItemIsUserCheckable)

    def test_completion_rejects_ambiguous_and_wrong_student(self):
        cls,env=isolate('_odev_kayit_sonucu_tamamlanan')
        env['OVERDUE_FLAG_ROLE']=44;env['OVERDUE_DAYS_ROLE']=45
        obj=cls();obj._secili_ogrenci_id=lambda:18;obj._loaded_student_id=2
        obj._ders_tablolari={'fizik':FakeGrid()}
        obj._odev_kayit_sonucu_tamamlanan([{'ders':'fizik','kitap':'Fizik 1','konu':'Elektrostatik'}])
        self.assertEqual(obj._ders_tablolari['fizik'].cells[0].checkState(),0)
        obj._loaded_student_id=18;obj._ders_tablolari={'fizik':FakeGrid(duplicates=True)}
        obj._odev_kayit_sonucu_tamamlanan([{'ders':'fizik','kitap':'Fizik 1','konu':'Elektrostatik'}])
        self.assertEqual(obj._ders_tablolari['fizik'].cells[0].checkState(),0)

    def test_status_refresh_does_not_clear_pending_checkbox(self):
        cls,env=isolate('_senkronize_odev_durumlari')
        env.update({'db':types.SimpleNamespace(get_conn=lambda:FakeConn()),
                    'OVERDUE_FLAG_ROLE':44,'OVERDUE_DAYS_ROLE':45})
        obj=cls();obj._secili_ogrenci_id=lambda:18;obj._loaded_student_id=18
        obj.verilen=FakeGiven([given_row()])
        obj._vtext=lambda r,c:obj.verilen.item(r,c).text()
        grid=FakeGrid();grid.cells[0].state=2
        obj._ders_tablolari={'fizik':grid}
        @contextlib.contextmanager
        def mute(t):yield
        obj._mute_table=mute
        # FakeQt uses no unavailable Qt methods; row 0 contains a matching unsaved task.
        obj._senkronize_odev_durumlari()
        self.assertEqual(grid.cells[0].checkState(),2)
        self.assertEqual(grid.cells[1].checkState(),0)

    def test_status_refresh_does_not_mutate_different_student(self):
        cls,env=isolate('_senkronize_odev_durumlari')
        env['db']=types.SimpleNamespace(get_conn=lambda: (_ for _ in ()).throw(AssertionError('must not access DB')))
        obj=cls();obj._secili_ogrenci_id=lambda:18;obj._loaded_student_id=2
        obj._senkronize_odev_durumlari()


if __name__=='__main__':unittest.main()
