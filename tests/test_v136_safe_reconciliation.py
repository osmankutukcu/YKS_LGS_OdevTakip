"""V13.6 isolated reconciliation tests; only throwaway synthetic databases."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.homework_reconciliation_v136 import (
    ACKNOWLEDGEMENT, ReconciliationError, build_review_manifest, apply_to_new_copy)
from services.homework_integrity_v135 import audit_database
from tools.reconcile_homework_v136 import main as cli


def sample_db(path):
    c=sqlite3.connect(path)
    c.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,
                          ders TEXT,kitap_ad TEXT,konu_ad TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,
                   odev_id INTEGER,ders TEXT,kitap TEXT,konu TEXT,kitap_ad TEXT,konu_ad TEXT,
                   durum TEXT,silindi INTEGER);
        INSERT INTO ogrenci VALUES(1),(2);
        INSERT INTO odev_kume VALUES(11,1),(22,2),(23,1);
        INSERT INTO odev VALUES(100,1,11,'Fizik','Fizik A','İvme');
        INSERT INTO odev VALUES(101,1,11,'Fizik','Fizik A','İvme');
        INSERT INTO odev VALUES(102,1,11,'Fizik','Fizik B','İvme');
        INSERT INTO odev VALUES(103,1,11,'Fizik','Fizik A','Elektrostatik');
        INSERT INTO odev VALUES(104,2,22,'Fizik','Fizik A','İvme');
        INSERT INTO odev VALUES(105,1,23,'Fizik','Fizik A','İvme');
        INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,kitap,konu,kitap_ad,konu_ad,durum,silindi)
             VALUES(501,1,11,999,'Fizik','Fizik A','İvme','Fizik A','İvme','devam',0);
        INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,kitap,konu,kitap_ad,konu_ad,durum,silindi)
             VALUES(502,1,11,100,'Fizik','Fizik A','İvme','Fizik A','İvme','devam',0);
        INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,kitap,konu,kitap_ad,konu_ad,durum,silindi)
             VALUES(503,2,22,NULL,'Fizik','Fizik A','İvme','Fizik A','İvme','devam',0);
    ''')
    c.commit()
    c.close()


class TestSafeReconciliation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.db=self.root/'source.db'
        sample_db(self.db)
        self.output=self.root/'new.db'
        self.plan=build_review_manifest(self.db)
    def tearDown(self): self.tmp.cleanup()
    def apply(self,plan=None,**kwargs):
        return apply_to_new_copy(self.db,plan or self.plan,self.output,
                     approver=kwargs.get('approver','Test yönetici'),
                     acknowledgement=kwargs.get('acknowledgement',ACKNOWLEDGEMENT))
    def case(self,action='unlink',target=None,reason='Öğretmenin incelemesi sonucunda eski kayıt bağlantısı geçersiz.'):
        p=copy.deepcopy(self.plan)
        p['kayitlar'][0]['islem']=action
        p['kayitlar'][0]['yeni_odev_id']=target
        p['kayitlar'][0]['gerekce']=reason
        return p
    def test_review_contains_orphans_only(self):
        self.assertEqual(len(self.plan['kayitlar']),1)
        r=self.plan['kayitlar'][0]
        self.assertEqual((r['satir_id'],r['eski_odev_id']),(501,999))
        self.assertEqual(r['olasi_aday_idleri'],[101])
        self.assertEqual(r['islem'],'review')
        self.assertNotIn('ad', self.plan)
    def test_default_review_does_not_modify(self):
        old=self.db.read_bytes()
        with self.assertRaises(ReconciliationError): self.apply()
        self.assertEqual(old,self.db.read_bytes())
        self.assertFalse(self.output.exists())
    def test_approved_unlink_creates_only_copy(self):
        old=self.db.read_bytes()
        r=self.apply(self.case())
        self.assertEqual(old,self.db.read_bytes())
        self.assertTrue(self.output.exists())
        self.assertTrue(Path(str(self.output)+'.uzlastirma.json').is_file())
        self.assertFalse(r['source_modified'])
        with sqlite3.connect(self.output) as c:
            self.assertIsNone(c.execute('SELECT odev_id FROM odev_satir WHERE id=501').fetchone()[0])
            self.assertEqual(c.execute('SELECT odev_id FROM odev_satir WHERE id=502').fetchone()[0],100)
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertFalse(audit_database(c).findings)
    def test_approved_relink_valid_unused_id(self):
        r=self.apply(self.case('relink',101))
        with sqlite3.connect(self.output) as c:
            self.assertEqual(c.execute('SELECT odev_id FROM odev_satir WHERE id=501').fetchone()[0],101)
        self.assertEqual(r['changes'][0]['yeni_odev_id'],101)
    def test_relink_duplicate_existing_reference_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'zaten bağlı'):
            self.apply(self.case('relink',100))
        self.assertFalse(self.output.exists())
    def test_relink_other_student_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'farklı öğrenciye'):
            self.apply(self.case('relink',104))
    def test_relink_wrong_book_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'birebir değil'):
            self.apply(self.case('relink',102))
    def test_relink_wrong_topic_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'birebir değil'):
            self.apply(self.case('relink',103))
    def test_relink_wrong_group_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'farklı öğrenciye veya kümeye'):
            self.apply(self.case('relink',105))
    def test_relink_nonexistent_parent_rejected(self):
        with self.assertRaisesRegex(ReconciliationError,'mevcut değil'):
            self.apply(self.case('relink',777))
    def test_reject_weak_reason(self):
        with self.assertRaisesRegex(ReconciliationError,'gerekçe'):
            self.apply(self.case(reason='tamam'))
    def test_reject_missing_admin_approval(self):
        with self.assertRaisesRegex(ReconciliationError,'onay'):
            self.apply(self.case(),acknowledgement='')
    def test_reject_same_source_dest(self):
        with self.assertRaisesRegex(ReconciliationError,'Kaynak dosyanın'):
            apply_to_new_copy(self.db,self.case(),self.db,approver='Yetkili',acknowledgement=ACKNOWLEDGEMENT)
    def test_reject_existing_output(self):
        self.output.write_bytes(b'Keep me')
        with self.assertRaisesRegex(ReconciliationError,'zaten var'):
            self.apply(self.case())
        self.assertEqual(self.output.read_bytes(),b'Keep me')
    def test_reject_stale_row_hash(self):
        p=self.case()
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE odev_satir SET durum='tamam' WHERE id=501")
        with self.assertRaisesRegex(ReconciliationError,'değişmiş'):
            self.apply(p)
        self.assertFalse(self.output.exists())
    def test_reject_deleted_orphan(self):
        p=self.case()
        with sqlite3.connect(self.db) as c:
            c.execute('DELETE FROM odev_satir WHERE id=501')
        with self.assertRaises(ReconciliationError): self.apply(p)
    def test_reject_new_unreviewed_orphan(self):
        p=self.case()
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id) VALUES(700,1,11,888)")
        with self.assertRaisesRegex(ReconciliationError,'listesi değişmiş'):
            self.apply(p)
    def test_reject_forged_student_identity(self):
        p=self.case()
        p['kayitlar'][0]['ogrenci_id']=2
        with self.assertRaisesRegex(ReconciliationError,'değişmiş'):
            self.apply(p)
    def test_reject_duplicate_case_ids(self):
        p=self.case()
        p['kayitlar'].append(copy.deepcopy(p['kayitlar'][0]))
        with self.assertRaisesRegex(ReconciliationError,'tekrarlı'):
            self.apply(p)
    def test_reject_restored_parent(self):
        p=self.case()
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO odev(id,ogrenci_id,kume_id,ders,kitap_ad,konu_ad) VALUES(999,1,11,'Fizik','Fizik A','İvme')")
        with self.assertRaises(ReconciliationError): self.apply(p)
    def test_journal_has_just_ids_not_student_names(self):
        self.apply(self.case())
        text=Path(str(self.output)+'.uzlastirma.json').read_text()
        self.assertIn('eski_odev_id',text)
        self.assertNotIn('kitap_ad',text)
        self.assertNotIn('konu_ad',text)
    def test_cli_review_and_approved_copy(self):
        man=self.root/'review.json'
        self.assertEqual(cli(['review','--db',str(self.db),'--manifest',str(man)]),0)
        plan=json.loads(man.read_text())
        plan['kayitlar'][0]['islem']='unlink'
        plan['kayitlar'][0]['gerekce']='Yetkili gerekli kaynak karşılaştırmasını yaptı.'
        man.write_text(json.dumps(plan))
        self.assertEqual(cli(['apply','--db',str(self.db),'--manifest',str(man),
            '--output',str(self.output),'--approver','Yönetici', '--confirm',ACKNOWLEDGEMENT]),0)
        self.assertTrue(self.output.exists())

if __name__=='__main__': unittest.main()
