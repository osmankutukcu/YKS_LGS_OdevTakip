"""V17 deneme result data safety regression tests; PyQt not required."""
import csv
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from services.trial_exam_import_v17 import (prepare, apply, parse_file,
                                              ExamImportError)


class ExamImportTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INT);
            CREATE TABLE denemeler(id INTEGER PRIMARY KEY,deneme_adi TEXT);
            CREATE TABLE deneme_sonuclari (id INTEGER PRIMARY KEY,
              deneme_id INT,ogrenci_id INT,ders_adi TEXT,dogru INT,yanlis INT,
              bos INT DEFAULT 0,net REAL DEFAULT 0);
            INSERT INTO ogrenci VALUES (1,'Ali','Veli',1);
            INSERT INTO ogrenci VALUES (2,'Osman','Fizik',1);
            INSERT INTO ogrenci VALUES (3,'Osman','Fizik',1);
            INSERT INTO ogrenci VALUES (4,'Eski','Mezun',0);
            INSERT INTO denemeler VALUES (5,'TYT 1');
            INSERT INTO deneme_sonuclari VALUES(9,5,4,'Matematik',20,10,5,17.5);
        ''')
        self.con.commit()
        self.subjects = ['Matematik','Türkçe']

    def tearDown(self): self.con.close()

    def p(self, data, **kwargs):return prepare(self.con,5,self.subjects,data, **kwargs)

    def test_add_keeps_inactive_student_results(self):
        result=self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':15,'yanlis':4}])
        self.assertFalse(result.errors)
        self.assertEqual(apply(self.con,5,result)['new'],1)
        self.assertEqual(self.con.execute('select count(*) from deneme_sonuclari').fetchone()[0],2)
        self.assertEqual(self.con.execute('select dogru from deneme_sonuclari where id=9').fetchone()[0],20)

    def test_update_only_matching_student_subject(self):
        self.con.execute("INSERT INTO deneme_sonuclari VALUES(10,5,1,'Matematik',11,4,0,10)")
        self.con.commit()
        prev=self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':16,'yanlis':4}])
        self.assertEqual(prev.counts['update'],1)
        apply(self.con,5,prev)
        self.assertEqual(self.con.execute('select dogru from deneme_sonuclari where id=10').fetchone()[0],16)
        self.assertEqual(self.con.execute('select dogru from deneme_sonuclari where id=9').fetchone()[0],20)

    def test_same_is_idempotent(self):
        v={'ogrenci_id':1,'ders':'Türkçe','dogru':22,'yanlis':8}
        apply(self.con,5,self.p([v])); result=self.p([v])
        self.assertEqual(result.counts['same'],1)
        self.assertEqual(apply(self.con,5,result)['same'],1)
        self.assertEqual(self.con.execute('select count(*) from deneme_sonuclari where ogrenci_id=1').fetchone()[0],1)

    def test_preserve_blank_when_omitted(self):
        result=self.p([{'ogrenci_id':4,'ders':'Matematik','dogru':11,'yanlis':4}])
        self.assertTrue(result.errors)  # inactive protection
        self.con.execute('UPDATE ogrenci SET aktif=1 WHERE id=4');self.con.commit()
        apply(self.con,5,self.p([{'ogrenci_id':4,'ders':'Matematik','dogru':11,'yanlis':4}]))
        self.assertEqual(self.con.execute('select bos from deneme_sonuclari where id=9').fetchone()[0],5)

    def test_failed_one_row_blocks_entire_batch(self):
        p=self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':10,'yanlis':5},
                  {'ogrenci_id':900,'ders':'Türkçe','dogru':2,'yanlis':1}])
        self.assertEqual(len(p.errors),1)
        with self.assertRaises(ExamImportError):apply(self.con,5,p)
        self.assertEqual(self.con.execute('select count(*) from deneme_sonuclari').fetchone()[0],1)

    def test_name_unique(self):
        p=self.p([{'ad_soyad':'Osman Fizik','ders':'Matematik','dogru':3,'yanlis':1}])
        self.assertEqual(len(p.errors),1)
        self.assertIn('eşsiz değil',p.errors[0])

    def test_name_matching(self):
        p=self.p([{'ad_soyad':'ALI VELİ','ders':'Matematik','dogru':3,'yanlis':1}])
        self.assertFalse(p.errors)
        self.assertEqual(p.changes[0].item.student_id,1)

    def test_name_id_mismatch(self):
        self.assertTrue(self.p([{'ogrenci_id':1,'ad_soyad':'Osman Fizik','ders':'Matematik','dogru':3,'yanlis':1}]).errors)

    def test_wrong_subject(self):
        self.assertTrue(self.p([{'ogrenci_id':1,'ders':'Fizik','dogru':3,'yanlis':1}]).errors)

    def test_duplicate_key(self):
        row={'ogrenci_id':1,'ders':'Matematik','dogru':3,'yanlis':1}
        self.assertTrue(self.p([row,row]).errors)

    def test_duplicate_db_rows_block(self):
        self.con.executemany('INSERT INTO deneme_sonuclari (deneme_id,ogrenci_id,ders_adi) VALUES(?,?,?)',
                             [(5,1,'Matematik'),(5,1,'Matematik')]);self.con.commit()
        self.assertTrue(self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':3,'yanlis':1}]).errors)

    def test_no_silent_invalid_zero(self):
        for d,y in [('',1),('2.5',3),('-1',0),(None,4),('201',0),('nan',2)]:
            self.assertTrue(self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':d,'yanlis':y}]).errors)

    def test_unknown_exam(self):
        with self.assertRaises(ExamImportError):prepare(self.con,99,self.subjects,[])

    def test_stale_preview_rejected_without_writes(self):
        p=self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':10,'yanlis':2}])
        self.con.execute('INSERT INTO deneme_sonuclari (deneme_id,ogrenci_id,ders_adi,dogru) VALUES(5,1,\'Matematik\',15)')
        self.con.commit()
        with self.assertRaises(ExamImportError):apply(self.con,5,p)
        self.assertEqual(self.con.execute('SELECT dogru FROM deneme_sonuclari WHERE ogrenci_id=1').fetchone()[0],15)

    def test_baseline_stale_screen(self):
        data={'ogrenci_id':1,'ders':'Matematik','dogru':3,'yanlis':1}
        self.con.execute('INSERT INTO deneme_sonuclari (deneme_id,ogrenci_id,ders_adi,dogru) VALUES(5,1,\'Matematik\',15)')
        self.con.commit()
        self.assertTrue(self.p([data],baseline={(1,'Matematik'):None}).errors)

    def test_late_error_rolls_back_all(self):
        p=self.p([{'ogrenci_id':1,'ders':'Matematik','dogru':10,'yanlis':1},
                  {'ogrenci_id':2,'ders':'Türkçe','dogru':20,'yanlis':5}])
        self.con.execute('INSERT INTO deneme_sonuclari (deneme_id,ogrenci_id,ders_adi,dogru) VALUES(5,2,\'Türkçe\',15)')
        self.con.commit()
        with self.assertRaises(ExamImportError):apply(self.con,5,p)
        self.assertEqual(self.con.execute('select count(*) from deneme_sonuclari where ogrenci_id=1').fetchone()[0],0)

    def test_csv_template_bom_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'data.csv'
            file.write_text('ogrenci_id,ad_soyad,ders,dogru,yanlis,bos\n1,Ali Veli,Matematik,24,4,2\n',encoding='utf-8-sig')
            parsed=parse_file(file)
            self.assertEqual(len(parsed),1)
            self.assertEqual(parsed[0]['dogru'],'24')
            self.assertFalse(self.p(parsed).errors)

    def test_semicolon_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'data.csv'
            file.write_text('Öğrenci ID;Ders;Doğru;Yanlış\n1;Matematik;23;4\n',encoding='utf-8-sig')
            self.assertFalse(self.p(parse_file(file)).errors)

    def test_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'data.tsv'
            file.write_text('ogrenci_id\tders\tdogru\tyanlis\n1\tMatematik\t20\t4\n',encoding='utf-8')
            self.assertFalse(self.p(parse_file(file)).errors)

    def test_xlsx_simple_shared_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'data.xlsx'
            with zipfile.ZipFile(file,'w') as arc:
                arc.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sonuclar" sheetId="1" r:id="rId1"/></sheets></workbook>''')
                arc.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
                arc.writestr('xl/sharedStrings.xml','''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>ogrenci_id</t></si><si><t>ders</t></si><si><t>dogru</t></si><si><t>yanlis</t></si><si><t>Matematik</t></si></sst>''')
                arc.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row><row r="2"><c r="A2"><v>1</v></c><c r="B2" t="s"><v>4</v></c><c r="C2"><v>20</v></c><c r="D2"><v>4</v></c></row></sheetData></worksheet>''')
            self.assertFalse(self.p(parse_file(file)).errors)

    def test_xlsx_formula_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'data.xlsx'
            with zipfile.ZipFile(file,'w') as arc:
                arc.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="s" sheetId="1" r:id="rId1"/></sheets></workbook>''')
                arc.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
                arc.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+2</f><v>3</v></c></row></sheetData></worksheet>''')
            with self.assertRaises(ExamImportError):parse_file(file)


if __name__ == '__main__':unittest.main()
