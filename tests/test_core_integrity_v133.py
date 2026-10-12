"""V13.3 core regressions; no Qt dependency or writes to real student data."""
import ast
import sqlite3
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.homework_integrity_v133 import student_completed_task, unique_exact_cell
from tests.test_wizard_student_transfer_v8 import FakeMatrix, FakeCell

ROOT=Path(__file__).resolve().parents[1]
FORM=ROOT/'ui/homework_form.py'


def get_method(klass, name, occurrence=0):
    tree=ast.parse(FORM.read_text('utf-8'))
    nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==klass]
    methods=[m for m in nodes[occurrence].body if isinstance(m,ast.FunctionDef) and m.name==name]
    assert methods, (klass,name)
    chosen=methods[-1]
    c=ast.ClassDef(name='Isolated',bases=[],keywords=[],body=[chosen],decorator_list=[])
    mod=ast.fix_missing_locations(ast.Module(body=[c],type_ignores=[]))
    scope={'db':None}
    exec(compile(mod,str(FORM),'exec'),scope)
    return scope['Isolated']


class TestScopedCompletion(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.execute('CREATE TABLE odev (ogrenci_id INTEGER,ders TEXT,kitap_ad TEXT,konu_ad TEXT,durum TEXT,silindi INTEGER DEFAULT 0)')
        self.con.execute('CREATE TABLE odev_satir (ogrenci_id INTEGER,ders TEXT,kitap TEXT,konu TEXT,durum TEXT,silindi INTEGER DEFAULT 0)')
        self.con.execute("INSERT INTO odev VALUES(2,'FİZİK','Fizik1','İvme','tamam',0)")
    def tearDown(self):self.con.close()
    def done(self,student=18,topic='İvme'):return student_completed_task(self.con,student,'fizik','Fizik1',topic)
    def test_alice_history_not_osman(self):
        self.assertTrue(self.done(2))
        self.assertFalse(self.done(18))
    def test_student_owns_completion_when_recorded(self):
        self.con.execute("INSERT INTO odev VALUES(18,'fizik','Fizik1','İvme','yapildi',0)")
        self.assertTrue(self.done(18))
    def test_incomplete_not_done(self):
        self.con.execute("INSERT INTO odev VALUES(18,'fizik','Fizik1','İvme','devam',0)")
        self.assertFalse(self.done(18))
    def test_soft_deleted_not_done(self):
        self.con.execute("INSERT INTO odev VALUES(18,'fizik','Fizik1','İvme','tamam',1)")
        self.assertFalse(self.done(18))
    def test_old_secondary_table_is_student_scoped(self):
        self.con.execute("INSERT INTO odev_satir VALUES(18,'fizik','Fizik1','İvme','bitti',0)")
        self.assertTrue(self.done(18))
        self.assertFalse(self.done(6))
    def test_soft_deleted_secondary_not_done(self):
        self.con.execute("INSERT INTO odev_satir VALUES(18,'fizik','Fizik1','İvme','tamam',1)")
        self.assertFalse(self.done(18))
    def test_no_student_does_not_match(self):
        for sid in (None,False,0,-1,'garbage'):
            self.assertFalse(self.done(sid))
    def test_similar_topic_is_not_equal(self):
        self.assertFalse(self.done(2,'İvme Ek'))
    def test_turkish_i_normalization(self):
        self.assertTrue(self.done(2))
    def test_incomplete_schema_skipped(self):
        self.con.execute('DROP TABLE odev_satir')
        self.assertFalse(self.done(18))
    def test_panel_methods_use_current_student(self):
        for panel_index in (0,1):
            with self.subTest(panel=panel_index):
                panel_cls=get_method('OneriPaneli','_is_globally_done',panel_index)
                # The shared method is self-scoped even when the caller supplied a different student.
                panel=panel_cls()
                panel._get_host=lambda:types.SimpleNamespace(_secili_ogrenci_id=lambda:18)
                panel_cls._is_globally_done.__globals__['db']=types.SimpleNamespace(get_conn=lambda:self.con)
                self.assertFalse(panel._is_globally_done(2,'fizik','Fizik1','İvme'))
                self.assertFalse(panel._is_globally_done(18,'fizik','Fizik1','İvme'))
                self.con.execute("INSERT INTO odev VALUES(18,'fizik','Fizik1','İvme','tamam',0)")
                self.assertTrue(panel._is_globally_done(18,'fizik','Fizik1','İvme'))
                self.con.execute("DELETE FROM odev WHERE ogrenci_id=18")


class TestUniqueCells(unittest.TestCase):
    def test_unique_exact_match(self):
        m=FakeMatrix(book='FİZİK1',topic='Elektrostatik')
        t,r,c=unique_exact_cell({'fizik':m},'fizik','FİZİK1','Elektrostatik')
        self.assertIs(t,m)
        self.assertEqual((r,c),(0,1))
    def test_partial_topics_rejected(self):
        self.assertIsNone(unique_exact_cell({'fizik':FakeMatrix()},'fizik','FİZİK1','Elektro')[0])
    def test_duplicate_lesson_alias_rejected(self):
        m=FakeMatrix()
        self.assertIsNone(unique_exact_cell({'fizik':m,'FİZİK':FakeMatrix()},'fizik','FİZİK1','Elektrostatik')[0])
    def test_duplicate_topic_rejected(self):
        m=FakeMatrix()
        m.topics[1]=FakeCell('Elektrostatik')
        self.assertIsNone(unique_exact_cell({'fizik':m},'fizik','FİZİK1','Elektrostatik')[0])
    def test_duplicate_book_rejected(self):
        m=FakeMatrix()
        original=m.horizontalHeaderItem
        m.columnCount=lambda:3
        m.horizontalHeaderItem=lambda c: FakeCell('FİZİK1') if c==2 else original(c)
        self.assertIsNone(unique_exact_cell({'fizik':m},'fizik','FİZİK1','Elektrostatik')[0])
    def test_main_form_uses_unique_match(self):
        cls=get_method('OdevTakipFormu','_hucre_bul')
        form=cls()
        form._ders_tablolari={'fizik':FakeMatrix()}
        self.assertIsNone(form._hucre_bul('fizik','FİZİK1','Elektro')[0])
        self.assertIsNotNone(form._hucre_bul('fizik','FİZİK1','Elektrostatik')[0])
    def test_single_active_tik_method(self):
        tree=ast.parse(FORM.read_text('utf-8'))
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='OdevTakipFormu')
        self.assertEqual(len([x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_tik_degisti']),1)

    def test_cross_student_group_guard_exists(self):
        tree=ast.parse(FORM.read_text('utf-8'))
        node=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='OdevTakipFormu')
        text=ast.unparse(node)
        self.assertIn('SELECT id FROM odev_kume WHERE id=? AND ogrenci_id=?',text)
        self.assertIn('Seçilen ödev kümesi bu öğrenciye ait değil',text)

if __name__=='__main__': unittest.main()
