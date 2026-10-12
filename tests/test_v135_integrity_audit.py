"""V13.5 audit regressions: synthetic fixtures only, no Qt or real student records."""
from __future__ import annotations
import ast
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.homework_integrity_v135 import audit_database, audit_draft_matrix

ROOT = Path(__file__).resolve().parents[1]


def fake_db(path):
    con = sqlite3.connect(path)
    con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER,
                          ders TEXT,kitap_ad TEXT,konu_ad TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER,
                                 odev_id INTEGER,ders TEXT,kitap TEXT,konu TEXT);
        INSERT INTO ogrenci(id) VALUES(1),(2);
        INSERT INTO odev_kume(id,ogrenci_id) VALUES(100,1),(200,2);
        INSERT INTO odev(id,ogrenci_id,kume_id,ders,kitap_ad,konu_ad)
             VALUES(300,1,100,'Fizik','Kitap A','İvme');
        INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,kitap,konu)
             VALUES(400,1,100,300,'Fizik','Kitap A','İvme');
    ''')
    con.commit()
    return con


def codes(r):
    return {f.code: f for f in r.findings}


class TestReadOnlyDatabaseAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'sample.db'
        self.con = fake_db(self.path)
    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()
    def test_healthy_database_has_no_errors(self):
        self.assertFalse(audit_database(self.con).findings)
    def test_linked_homework_missing(self):
        self.con.execute("UPDATE odev_satir SET odev_id=999 WHERE id=400")
        report=codes(audit_database(self.con))
        self.assertEqual(report['MISSING_LINKED_HOMEWORK'].count,1)
        self.assertEqual(report['MISSING_LINKED_HOMEWORK'].references,('400',))
    def test_unlinked_legacy_row_not_an_error(self):
        self.con.execute("UPDATE odev_satir SET odev_id=NULL WHERE id=400")
        self.assertNotIn('MISSING_LINKED_HOMEWORK', codes(audit_database(self.con)))
    def test_group_mismatch_detected(self):
        self.con.execute("UPDATE odev SET ogrenci_id=2 WHERE id=300")
        self.assertIn('STUDENT_GROUP_MISMATCH_ODEV', codes(audit_database(self.con)))
    def test_secondary_group_mismatch_detected(self):
        self.con.execute("UPDATE odev_satir SET ogrenci_id=2 WHERE id=400")
        self.assertIn('STUDENT_GROUP_MISMATCH_ODEV_SATIR', codes(audit_database(self.con)))
    def test_linked_student_mismatch_detected(self):
        self.con.execute("UPDATE odev_satir SET ogrenci_id=2 WHERE id=400")
        self.assertIn('LINKED_HOMEWORK_STUDENT_MISMATCH', codes(audit_database(self.con)))
    def test_missing_group_detected(self):
        self.con.execute('UPDATE odev SET kume_id=777 WHERE id=300')
        self.assertIn('MISSING_GROUP_ODEV', codes(audit_database(self.con)))
    def test_missing_student_detected(self):
        self.con.execute('UPDATE odev SET ogrenci_id=777 WHERE id=300')
        self.assertIn('MISSING_STUDENT_ODEV', codes(audit_database(self.con)))
    def test_ro_db_does_not_change_a_byte(self):
        self.con.close()
        before=self.path.read_bytes()
        from importlib.util import spec_from_file_location
        # The module itself does not import Qt; test using SQLite mode=ro.
        ro=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        ro.execute('PRAGMA query_only=ON')
        self.assertFalse(audit_database(ro).findings)
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute('DELETE FROM ogrenci')
        ro.close()
        self.assertEqual(before,self.path.read_bytes())
        self.con=sqlite3.connect(self.path)
    def test_no_rows_equalization(self):
        self.con.execute("INSERT INTO odev_satir VALUES(401,1,100,NULL,'Fizik','Kitap A','İvme')")
        self.assertFalse(audit_database(self.con).findings)
    def test_missing_schema_reports_no_crash(self):
        self.con.execute('DROP TABLE odev')
        self.assertIn('MISSING_TABLE', codes(audit_database(self.con)))
    def test_missing_link_column_legacy(self):
        self.con.execute('ALTER TABLE odev_satir RENAME TO old_satir')
        self.con.execute('CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER)')
        report=audit_database(self.con)
        self.assertNotIn('MISSING_LINKED_HOMEWORK', codes(report))
        self.assertTrue(any('odev_id' in n for n in report.notes))
    def test_samples_capped(self):
        self.con.execute("UPDATE odev_satir SET odev_id=999 WHERE id=400")
        for idx in range(401,440):
            self.con.execute('INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id) VALUES(?,?,?,?)',(idx,1,100,999))
        f=codes(audit_database(self.con,sample_limit=3))['MISSING_LINKED_HOMEWORK']
        self.assertEqual(f.count,40)
        self.assertEqual(len(f.references),3)


CELL = dict(ders='Fizik',kitap='Kitap A',konu='İvme',checked=True,locked=False)
TASK = dict(ders='Fizik',kitap='Kitap A',konu='İvme')

class TestDraftMatrixAudit(unittest.TestCase):
    def run_audit(self,cells=None,tasks=None,selected=1,loaded=1):
        return audit_draft_matrix(cells if cells is not None else [CELL],
                                  tasks if tasks is not None else [TASK],
                                  selected_student=selected,loaded_student=loaded)
    def test_matching_draft_is_clear(self):self.assertFalse(self.run_audit().findings)
    def test_selected_student_mismatch_aborts(self):
        result=self.run_audit(selected=2,loaded=1)
        self.assertEqual(set(codes(result)),{'STUDENT_CONTEXT_MISMATCH'})
    def test_missing_loaded_student_aborts(self):
        self.assertIn('STUDENT_CONTEXT_MISMATCH',codes(self.run_audit(loaded=None)))
    def test_checked_without_right_task(self):
        self.assertIn('CHECKED_WITHOUT_DRAFT',codes(self.run_audit(tasks=[])))
    def test_right_task_without_check(self):
        self.assertIn('DRAFT_WITHOUT_CHECK',codes(self.run_audit(cells=[{**CELL,'checked':False}])))
    def test_similar_topic_not_a_match(self):
        row={**TASK,'konu':'İvme Ek'}
        result=codes(self.run_audit(tasks=[row]))
        self.assertIn('CHECKED_WITHOUT_DRAFT',result)
        self.assertIn('DRAFT_WITHOUT_CHECK',result)
    def test_locked_cell_is_not_missing_right_task(self):
        self.assertFalse(self.run_audit(cells=[{**CELL,'locked':True}],tasks=[]).findings)
    def test_task_linked_to_saved_cell_not_auto_flagged(self):
        self.assertFalse(self.run_audit(cells=[{**CELL,'locked':True}],tasks=[TASK]).findings)
    def test_duplicates_in_right_table(self):
        self.assertEqual(codes(self.run_audit(tasks=[TASK,TASK]))['DUPLICATE_DRAFT_ROWS'].count,1)
    def test_duplicate_cells_ambiguous(self):
        result=codes(self.run_audit(cells=[CELL,CELL]))
        self.assertIn('AMBIGUOUS_MATRIX_KEY',result)
        self.assertNotIn('CHECKED_WITHOUT_DRAFT',result)
    def test_turkish_letter_case_matching(self):
        self.assertFalse(self.run_audit(cells=[{**CELL,'ders':'FİZİK'}],
                                        tasks=[{**TASK,'ders':'fizik'}]).findings)
    def test_whitespace_normalized(self):
        self.assertFalse(self.run_audit(cells=[{**CELL,'konu':'  İvme  '}]).findings)
    def test_no_automatic_fix_functions_present(self):
        p=(ROOT/'services/homework_integrity_v135.py').read_text('utf8')
        tree=ast.parse(p)
        methods={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse({'commit','rollback','executemany'}&methods)


class TestUIWiring(unittest.TestCase):
    def test_main_form_integrated_with_button(self):
        source=(ROOT/'ui/homework_form.py').read_text('utf8')
        self.assertIn('self.btnVeriDenetimi = QPushButton',source)
        self.assertIn('self.btnVeriDenetimi.clicked.connect(self._open_integrity_v135)',source)
        self.assertIn('def _open_integrity_v135(self):',source)
    def test_dialog_is_read_only_and_manual(self):
        s=(ROOT/'ui/homework_integrity_dialog_v135.py').read_text('utf8')
        self.assertIn('PRAGMA query_only=ON',s)
        self.assertIn('self.content.setReadOnly(True)',s)
        self.assertNotIn('UPDATE odev',s)
        self.assertNotIn('DELETE FROM',s)

if __name__=='__main__': unittest.main()

class TestV135CLI(unittest.TestCase):
    def test_readonly_cli_works_on_synthetic(self):
        from tools.audit_homework_v135 import run
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.db'
            con=fake_db(path)
            con.close()
            before=path.read_bytes()
            self.assertFalse(run(path).findings)
            self.assertEqual(before,path.read_bytes())

class TestSnapshotAdapterHeadless(unittest.TestCase):
    def _snapshot(self):
        path=ROOT/'ui/homework_integrity_dialog_v135.py'
        node=next(n for n in ast.parse(path.read_text('utf8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='snapshot_form')
        namespace={}
        class FakeQt:
            class CheckState: Checked=2
            class ItemFlag: ItemIsUserCheckable=2
        namespace['Qt']=FakeQt
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),namespace)
        return namespace['snapshot_form']

    def test_visible_drafts_collected_from_form(self):
        from tests.test_v134_homework_lifecycle import FakeGrid,FakeGiven,given_row
        grid=FakeGrid(topic='İvme',book='Fizik A');grid.cells[0].state=2
        obj=type('MockForm',(),{})()
        obj._ders_tablolari={'fizik':grid}
        obj.verilen=FakeGiven([given_row('İvme')])
        cells,rows=self._snapshot()(obj)
        self.assertEqual(cells[0]['checked'],True)
        self.assertEqual(cells[0]['konu'],'İvme')
        self.assertEqual(len(rows),1)

    def test_locked_saved_cells_are_marked_locked(self):
        from tests.test_v134_homework_lifecycle import FakeGrid
        grid=FakeGrid(topic='İvme',book='Fizik A')
        grid.cells[0].setFlags(4)
        obj=type('MockForm',(),{})()
        obj._ders_tablolari={'fizik':grid}
        obj.verilen=None
        cells,_=self._snapshot()(obj)
        self.assertTrue(cells[0]['locked'])
