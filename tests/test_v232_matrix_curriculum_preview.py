"""V23.2 bridge regression: old checkbox/write path is never touched."""
import sqlite3
import unittest
from pathlib import Path

from services.curriculum_v232 import inspect_matrix_topics


def build_db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY, ad TEXT);
      INSERT INTO ders_tanimlari VALUES('fizik','Fizik');
      CREATE TABLE fizik(id INTEGER PRIMARY KEY, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
      INSERT INTO fizik VALUES (1,'Elektrik',20,30),(2,'Hareket',30,30),(3,'Dalgalar',20,20);
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ana_grup TEXT, alt_grup TEXT);
      INSERT INTO ogrenci VALUES(1,'YKS','12-say'),(2,'YKS','12-ea');
      CREATE TABLE grup_konu_duzen(id INTEGER PRIMARY KEY,ana_grup TEXT,alt_grup TEXT,
        ders TEXT,konu TEXT,ort_soru INTEGER,ort_sure INTEGER);
      INSERT INTO grup_konu_duzen VALUES(1,'YKS','12-say','fizik','Elektrik',40,40),
        (2,'YKS','12-say','fizik','Özel Grup Konusu',20,15);
      CREATE TABLE ogrenci_konu_duzen(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
        ders TEXT,konu TEXT,ort_soru INTEGER,ort_sure INTEGER);
      INSERT INTO ogrenci_konu_duzen VALUES(1,1,'fizik','Kişisel Konu',15,15);
      CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,
        konu_id INTEGER,konu_ad TEXT,kitap_ad TEXT,durum TEXT);
      INSERT INTO odev VALUES(1,1,'fizik',1,'Elektrik','Test','devam');
    ''')
    return db


class MatrixBridgeTests(unittest.TestCase):
    def setUp(self):
        self.con = build_db()
        self.baseline = self.rows()

    def tearDown(self):
        self.con.close()

    def rows(self):
        return list(self.con.execute('SELECT id,konu FROM fizik ORDER BY id'))

    def test_scoped_only_topics_remain_preview_only(self):
        review = inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=self.baseline)
        self.assertEqual(2,review.scoped_only_count)
        for topic in review.rows:
            if topic.title in ('Özel Grup Konusu','Kişisel Konu'):
                self.assertIsNone(topic.legacy_general_id)
                self.assertEqual('Yalnızca önizleme',topic.status)

    def test_same_name_override_cannot_borrow_general_id(self):
        review = inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=self.baseline)
        electric = next(t for t in review.rows if t.title=='Elektrik')
        self.assertEqual('Grup', electric.source)
        self.assertEqual(1,electric.legacy_general_id)
        self.assertEqual('Kapsam farklı – yalnızca önizleme',electric.status)
        self.assertIn('kimliği bu ID değildir', electric.details)

    def test_general_row_preserves_same_numeric_id(self):
        review = inspect_matrix_topics(self.con,lesson='fizik',student_id=2,general_rows=self.baseline)
        movement=next(t for t in review.rows if t.title=='Hareket')
        self.assertEqual('Genel matriste kullanılabilir',movement.status)
        self.assertEqual(2,movement.legacy_general_id)

    def test_two_students_have_isolated_results(self):
        first=inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=self.baseline)
        second=inspect_matrix_topics(self.con,lesson='fizik',student_id=2,general_rows=self.baseline)
        self.assertIn('Kişisel Konu',[t.title for t in first.rows])
        self.assertNotIn('Kişisel Konu',[t.title for t in second.rows])
        self.assertNotIn('Özel Grup Konusu',[t.title for t in second.rows])

    def test_database_not_changed(self):
        before=list(self.con.iterdump())
        for i in (1,2,1):
            inspect_matrix_topics(self.con,lesson='fizik',student_id=i,general_rows=self.baseline)
        self.assertEqual(before,list(self.con.iterdump()))

    def test_bad_student_fails_closed(self):
        with self.assertRaises(Exception):
            inspect_matrix_topics(self.con,lesson='fizik',student_id=999,general_rows=self.baseline)

    def test_invalid_row_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=[{'id':None,'konu':'X'}])

    def test_general_mismatch_warning_no_data_mutation(self):
        before=list(self.con.iterdump())
        review=inspect_matrix_topics(self.con,lesson='fizik',student_id=1,
                                      general_rows=[{'id':1,'konu':'Eski Ad'}])
        self.assertTrue(any('uyuşmuyor' in w for w in review.warnings))
        self.assertEqual(before,list(self.con.iterdump()))

    def test_duplicate_general_keeps_old_matrix_intact(self):
        self.con.execute("INSERT INTO fizik VALUES(5,'hareket',9,9)")
        before=list(self.con.iterdump())
        rows=self.rows()
        review=inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=rows)
        self.assertTrue(any('çakışıyor' in w for w in review.warnings))
        self.assertEqual(before,list(self.con.iterdump()))

    def test_legacy_odev_record_not_touched(self):
        before=self.con.execute('SELECT * FROM odev').fetchall()[0]
        inspect_matrix_topics(self.con,lesson='fizik',student_id=1,general_rows=self.baseline)
        after=self.con.execute('SELECT * FROM odev').fetchall()[0]
        self.assertEqual(tuple(before), tuple(after))

    def test_main_form_only_hooked_after_old_table_data_is_loaded(self):
        src = (Path(__file__).resolve().parents[1] / 'ui/homework_form.py').read_text()
        pos=src.index('from ui.curriculum_matrix_preview_v232 import install_curriculum_preview_navigation')
        self.assertLess(pos, src.index('self.tabs = QTabWidget()'))
        block=src[src.index('def _ders_tab_olustur'):src.index('\n    def _flash_cell(self', src.index('def _ders_tab_olustur'))]
        self.assertNotIn('v232',block)
        self.assertIn('return container, table',block)

    def test_main_form_does_not_replace_old_topic_id_role(self):
        src=(Path(__file__).resolve().parents[1] / 'ui/homework_form.py').read_text()
        block=src[src.index('def _ders_tab_olustur'):src.index('\n    def _flash_cell(self', src.index('def _ders_tab_olustur'))]
        self.assertIn('it.setData(Qt.ItemDataRole.UserRole, int(k["id"]))',block)
        self.assertIn('SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?',block)
        self.assertIn('self._tik_degisti(it, table, ders)',block)

if __name__=='__main__':
    unittest.main()

# Regression of low-resolution and current-student safety in optional Qt layer.
def test_dialog_stays_modal_to_prevent_student_change():
    text=(Path(__file__).resolve().parents[1] / 'ui/curriculum_matrix_preview_v232.py').read_text()
    assert 'self.setModal(True)' in text
    assert 'dialog.exec()' in text
    assert "student_id != loaded_id" in text
    assert 'availableGeometry()' in text


def test_bridge_is_separate_from_checkbox_writes():
    text=(Path(__file__).resolve().parents[1] / 'services/curriculum_v232/bridge.py').read_text()
    import ast
    tree=ast.parse(text)
    # Real service does not use any SQL modification statements or open a write connection.
    assert not any(s in text.upper() for s in ('INSERT INTO ', 'UPDATE ODEV ', 'DELETE FROM ', 'CREATE TABLE '))
    assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                   and node.func.attr in ('commit','executemany') for node in ast.walk(tree))
