"""V3.5.3: Yalnızca sentetik öğrenci verileriyle yapılan kararlılık regresyon testleri."""
import sqlite3
import unittest
from unittest.mock import patch

from tests.test_unified_core import UnifiedTests
from web_api.homework_store import set_single_line_done, set_headers_done


class StabilityRegressions(unittest.TestCase):
    def setUp(self):
        # Mevcut bütünleşik testlerin sahte veritabanı + API kurulumunu paylaş.
        UnifiedTests.setUp(self)

    def test_parent_is_complete_only_after_every_child(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE odev_satir SET durum='devam' WHERE id=1")
            con.execute("INSERT INTO odev_satir (id,odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum) "
                        "VALUES (2,1,1,1,'lgs_matematik','Cebir','Kitap','2026-10-10','devam')")
            set_single_line_done(con, 1, True)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0], 'devam')
            set_single_line_done(con, 2, True)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0], 'yapildi')
            set_single_line_done(con, 1, False)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0], 'devam')

    def test_legacy_link_not_guessed_across_different_lessons(self):
        with sqlite3.connect(self.path) as con:
            con.execute('UPDATE odev_satir SET odev_id=NULL WHERE id=1')
            con.execute("INSERT INTO odev VALUES(2,1,1,'fizik',1,'Cebir','Kitap',0,'','devam','2026-10-10',NULL)")
            con.execute("INSERT INTO odev_satir (id,odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum) "
                        "VALUES (2,NULL,1,1,'fizik','Cebir','Kitap','2026-10-10','devam')")
            set_headers_done(con, [2], True)
            self.assertIsNone(con.execute('SELECT odev_id FROM odev_satir WHERE id=1').fetchone()[0])
            self.assertEqual(con.execute('SELECT odev_id FROM odev_satir WHERE id=2').fetchone()[0], 2)

    def test_wrong_student_fk_never_modifies_another_student_header(self):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO ogrenci VALUES(2,'Test','Ogrenci',1,'Okul','8B','000')")
            con.execute("INSERT INTO odev VALUES(2,1,2,'lgs_matematik',2,'Cebir','Kitap',0,'','devam','2026-10-10',NULL)")
            con.execute('UPDATE odev_satir SET odev_id=2, durum=? WHERE id=1', ('devam',))
            set_single_line_done(con, 1, True)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=2').fetchone()[0], 'devam')

    def test_blank_topic_list_cannot_create_orphan_cluster(self):
        for topics in (['', '   '], []):
            res = self.client.post('/api/homework', headers=self.headers,
                                   json={'student_id':1,'lesson':'lgs_matematik','book':'Kitap','topics':topics})
            self.assertEqual(res.status_code,422)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM odev_kume').fetchone()[0],1)

    def test_unknown_student_cannot_create_orphan_cluster(self):
        response = self.client.post('/api/homework', headers=self.headers,
                                    json={'student_id':999,'lesson':'lgs_matematik','book':'Kitap','topics':['Cebir']})
        self.assertEqual(response.status_code,422)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM odev_kume').fetchone()[0],1)

    def test_whatsapp_summary_returns_actual_text(self):
        res = self.client.post('/api/student/1/whatsapp', headers=self.headers)
        self.assertEqual(res.status_code,200,res.text)
        body=res.json()
        self.assertIn('Ödev Özeti',body['text'])
        self.assertIn('Cebir',body['text'])
        self.assertIn('Ornek',body['text'])

    def test_homework_limit_after_many_completed(self):
        with sqlite3.connect(self.path) as con:
            con.executemany('''INSERT INTO odev_satir(odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum)
                            VALUES(?,?,?,?,?,?,?,?)''',
                            [(1,1,1,'lgs_matematik','Cebir','Kitap','2026-10-10','tamam') for _ in range(400)])
            con.execute("UPDATE odev_satir SET durum='devam' WHERE id=1")
        r = self.client.get('/api/homework?limit=1',headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual([x['id'] for x in r.json()],[1])

    def test_read_endpoints_close_sqlite_connections(self):
        closes=[]
        opens=[]
        class TrackingConnection(sqlite3.Connection):
            def close(self):
                closes.append(id(self))
                return super().close()
        def make():
            connection = sqlite3.connect(self.path, factory=TrackingConnection)
            opens.append(id(connection))
            return connection
        with patch.object(self.fake_db,'get_conn',make):
            for url in ['/api/students','/api/student/1/info','/api/student/1/tracking',
                        '/api/student/1/suggestions','/api/student/1/clusters','/api/matrix/lgs_matematik',
                        '/api/books/lgs_matematik','/api/student/1/whatsapp']:
                with self.subTest(url=url):
                    result = self.client.get(url,headers=self.headers) if not url.endswith('whatsapp') else self.client.post(url,headers=self.headers)
                    self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(len(opens),len(closes))
        self.assertEqual(set(opens),set(closes))

    def test_whatsapp_pending_filter_scans_past_newest_fifty(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE odev SET durum='devam' WHERE id=1")
            for index in range(2, 72):
                con.execute("""INSERT INTO odev(id,kume_id,ogrenci_id,ders,konu_id,konu_ad,kitap_ad,
                            saat_dk,aciklama,durum,verilis_tarihi,tamamlanma_tarihi)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (index,1,1,'lgs_matematik',index,f'Konu {index}','Kitap',0,'','yapildi','2026-10-10',None))
        r=self.client.post('/api/student/1/whatsapp?status=Yapılmayanlar',headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('Cebir',r.json()['text'])
        self.assertNotIn('Konu 71',r.json()['text'])
        self.assertIn('0/1',r.json()['text'])

    def test_legacy_schema_without_line_header_id_updates_consistently(self):
        with sqlite3.connect(':memory:') as con:
            con.executescript("""
                CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
                    ders TEXT,konu_ad TEXT,kitap_ad TEXT,durum TEXT,tamamlanma_tarihi TEXT);
                CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
                    ders TEXT,konu TEXT,kitap TEXT,durum TEXT,tamamlanma_tarihi TEXT);
                INSERT INTO odev VALUES(1,1,1,'fizik','Hareket','Test','devam',NULL);
                INSERT INTO odev VALUES(2,1,1,'kimya','Hareket','Test','devam',NULL);
                INSERT INTO odev_satir VALUES(1,1,1,'fizik','Hareket','Test','devam',NULL);
                INSERT INTO odev_satir VALUES(2,1,1,'fizik','Hareket','Test','devam',NULL);
                INSERT INTO odev_satir VALUES(3,1,1,'kimya','Hareket','Test','devam',NULL);
            """)
            set_single_line_done(con,1,True)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'devam')
            set_single_line_done(con,2,True)
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'yapildi')
            set_headers_done(con,[1],False)
            self.assertEqual([r[0] for r in con.execute('SELECT durum FROM odev_satir WHERE id IN (1,2)')],
                             ['devam','devam'])
            self.assertEqual(con.execute('SELECT durum FROM odev_satir WHERE id=3').fetchone()[0],'devam')

    def test_status_counter_accepts_streaming_generator(self):
        from utils.homework_status import status_counts
        seen=[]
        def records():
            for value in ('tamam', 'devam', '  tamamlandı  '):
                seen.append(value)
                yield value
        self.assertEqual(status_counts(records()),
                         {'total':3,'completed':2,'pending':1,'success_rate':67})
        self.assertEqual(len(seen),3)

    def test_allowed_cors_preflight_cannot_bypass_real_api_auth(self):
        import importlib, sys
        from fastapi.testclient import TestClient
        with patch.dict('os.environ',{'YKS_WEB_ALLOWED_ORIGINS':'https://test-frontend.invalid'}):
            sys.modules.pop('web_api.main',None)
            fresh=importlib.import_module('web_api.main')
            client=TestClient(fresh.app)
            head={'Origin':'https://test-frontend.invalid',
                  'Access-Control-Request-Method':'GET',
                  'Access-Control-Request-Headers':'X-Access-Key'}
            r=client.options('/api/students',headers=head)
            self.assertIn(r.status_code,(200,204),r.text)
            self.assertEqual(r.headers.get('access-control-allow-origin'), 'https://test-frontend.invalid')
            unauthenticated=client.get('/api/students',headers={'Origin':head['Origin']})
            self.assertEqual(unauthenticated.status_code,401)

    def test_invalid_legacy_match_preserves_sibling_status(self):
        with sqlite3.connect(self.path) as con:
            con.execute('UPDATE odev_satir SET odev_id=NULL WHERE id=1')
            con.execute("INSERT INTO odev VALUES(2,1,1,'lgs_matematik',2,'Cebir','Kitap',0,'','devam','2026-10-10',NULL)")
            set_single_line_done(con,1,True)
            self.assertIsNone(con.execute('SELECT odev_id FROM odev_satir WHERE id=1').fetchone()[0])
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=2').fetchone()[0], 'devam')

if __name__=='__main__':
    unittest.main()
