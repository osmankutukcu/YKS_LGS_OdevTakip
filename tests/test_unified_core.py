import importlib
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from utils.homework_status import is_completed, status_counts, mobile_status
from web_api.homework_store import set_single_line_done, set_headers_done
from web_api.auth import authorized

class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.tdir=tempfile.TemporaryDirectory()
        self.addCleanup(self.tdir.cleanup)
        self.path=Path(self.tdir.name)/'fake_student.db'
        with sqlite3.connect(self.path) as c:
            c.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER,ana_grup TEXT,alt_grup TEXT,veli_tel1 TEXT);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,verilis_tarihi TEXT,bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,ders TEXT,konu_id INTEGER,konu_ad TEXT,kitap_ad TEXT,
                saat_dk INTEGER,aciklama TEXT,durum TEXT,verilis_tarihi TEXT,tamamlanma_tarihi TEXT,
                UNIQUE(kume_id,ders,konu_id,kitap_ad));
            CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,odev_id INTEGER,kume_id INTEGER,ogrenci_id INTEGER,ders TEXT,konu TEXT,kitap TEXT,
                tarih TEXT,durum TEXT,tamamlanma_tarihi TEXT);
            CREATE TABLE kitap(ders TEXT,ad TEXT,UNIQUE(ders,ad));
            CREATE TABLE lgs_matematik(id INTEGER PRIMARY KEY,konu TEXT);
            INSERT INTO ogrenci(id,ad,soyad,aktif,ana_grup,alt_grup,veli_tel1) VALUES(1,'Ornek','Ogrenci',1,'Okul','8A','000');
            INSERT INTO lgs_matematik VALUES(1,'Cebir');
            INSERT INTO lgs_matematik VALUES(2,'Geometri');
            INSERT INTO odev_kume VALUES(1,1,'2026-10-10','2026-10-20');
            INSERT INTO odev VALUES(1,1,1,'lgs_matematik',1,'Cebir','Kitap',0,'','yapildi','2026-10-10',NULL);
            INSERT INTO odev_satir VALUES(1,1,1,1,'lgs_matematik','Cebir','Kitap','2026-10-10',' tamam ',NULL);
            ''')
        self.fake_db=types.ModuleType('db')
        self.fake_db.DB_PATH=self.path
        self.fake_db.get_conn=lambda:sqlite3.connect(self.path)
        self.db_patch=patch.dict(sys.modules,{'db':self.fake_db})
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.env_patch=patch.dict(os.environ,{'YKS_WEB_ACCESS_TOKEN':'the-test-token-123456789012345678901234567890'})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        sys.modules.pop('web_api.main',None)
        self.api=importlib.import_module('web_api.main')
        self.client=TestClient(self.api.app)
        self.headers={'x-access-key':os.environ['YKS_WEB_ACCESS_TOKEN']}

    def test_statuses(self):
        self.assertTrue(all(is_completed(x) for x in ['tamam','tamamlandı',' TAMAM ','yapildi','yapıldı','completed']))
        self.assertEqual(status_counts(['tamam','devam',' tamam '])['pending'],1)
        self.assertFalse(is_completed('Beklemede'))

    def test_api_blocks_anonymous_sensitive_read_and_write(self):
        for method,url in [('get','/api/students'),('get','/api/student/1/info'),('get','/api/dashboard'),
                           ('post','/api/homework/1/complete'),('get','/report'),('get','/docs')]:
            with self.subTest(method=method,url=url):
                self.assertEqual(getattr(self.client,method)(url).status_code,401)
                self.assertEqual(getattr(self.client,method)(url,headers={'x-access-key':'bad'}).status_code,401)
        self.assertEqual(self.client.get('/').status_code,200)

    def test_valid_key_reads(self):
        self.assertEqual(self.client.get('/api/students',headers=self.headers).status_code,200)
        self.assertTrue(authorized(self.headers['x-access-key']))

    def test_dashboard_normalized(self):
        result=self.client.get('/api/dashboard',headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        stats=result.json()
        self.assertEqual(stats['student_count'],1)
        self.assertEqual(stats['pending_tasks'],0)
        self.assertEqual(stats['success_rate'],100)

    def test_due_date_from_cluster(self):
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE odev_satir SET durum='devam' WHERE id=1")
        result=self.client.get('/api/homework',headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()[0]['due_date'],'2026-10-20')

    def test_line_completion_syncs_header(self):
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE odev SET durum='devam' WHERE id=1")
            changed=set_single_line_done(c,1,True)
            self.assertEqual(changed,1)
            self.assertEqual(c.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'yapildi')
            self.assertEqual(c.execute('SELECT durum FROM odev_satir WHERE id=1').fetchone()[0],'tamam')

    def test_bulk_syncs_both(self):
        result=self.client.post('/api/homework/status/bulk',headers=self.headers,
                                json={'homework_ids':[1],'status':'devam'})
        self.assertEqual(result.status_code,200,result.text)
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'devam')
            self.assertEqual(c.execute('SELECT durum FROM odev_satir WHERE id=1').fetchone()[0],'devam')

    def test_legacy_missing_link_can_be_safely_repaired(self):
        with sqlite3.connect(self.path) as c:
            c.execute('UPDATE odev_satir SET odev_id=NULL WHERE id=1')
        r=self.client.post('/api/homework/status/bulk',headers=self.headers,
                           json={'homework_ids':[1],'status':'devam'})
        self.assertEqual(r.status_code,200,r.text)
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute('SELECT odev_id FROM odev_satir WHERE id=1').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT durum FROM odev_satir WHERE id=1').fetchone()[0],'devam')

    def test_clusters_normalized_status(self):
        result=self.client.get('/api/student/1/clusters',headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()[0]['completed_items'],1)
        self.assertEqual(result.json()[0]['percent'],100)

    def test_create_homework_keeps_header_row_link(self):
        res=self.client.post('/api/homework',headers=self.headers,
                             json={'student_id':1,'lesson':'lgs_matematik','book':'Deneme Kitabi',
                                   'topics':['Cebir','Geometri'],'due_date':'2026-10-31'})
        self.assertEqual(res.status_code,200,res.text)
        with sqlite3.connect(self.path) as c:
            new_id=res.json()['kume_id']
            linked=c.execute('SELECT s.odev_id,s.kume_id,o.kume_id FROM odev_satir s JOIN odev o ON o.id=s.odev_id WHERE s.kume_id=?',(new_id,)).fetchall()
            self.assertEqual(len(linked),2)
            self.assertTrue(all(r[1]==r[2] for r in linked))
            self.assertEqual(c.execute('SELECT bitis_tarihi FROM odev_kume WHERE id=?',(new_id,)).fetchone()[0],'2026-10-31')

    def test_injection_invalid_table_rejected(self):
        result=self.client.get('/api/matrix/ogrenci',headers=self.headers)
        self.assertEqual(result.status_code,422)

    def test_empty_topic_does_not_create_cluster(self):
        before=sqlite3.connect(self.path).execute('SELECT count(*) FROM odev_kume').fetchone()[0]
        r=self.client.post('/api/homework',headers=self.headers,json={'student_id':1,'lesson':'lgs_matematik','book':'Kitap'})
        self.assertEqual(r.status_code,422)
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM odev_kume').fetchone()[0],before)

if __name__=='__main__': unittest.main()
