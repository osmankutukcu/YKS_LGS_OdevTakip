# -*- coding: utf-8 -*-
"""V3.5.4: Gerçek kişi verisi kullanmadan ödev kayıt ve eşzamanlılık regresyonları."""
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from utils.homework_status import is_completed
from tests import test_unified_core as _test_fixtures


class WriteDurabilityTests(unittest.TestCase):
    def setUp(self):
        _test_fixtures.UnifiedTests.setUp(self)

    def _bulk(self, **overrides):
        payload = dict(student_id=1, lesson_table='lgs_matematik', lesson_name='LGS Matematik',
                       items=[dict(topic_id=1, topic_name='Cebir', book_name='Kaynak')],
                       due_date='2026-10-31')
        payload.update(overrides)
        return self.client.post('/api/homework/bulk', headers=self.headers, json=payload)

    def _counts(self):
        con = sqlite3.connect(self.path)
        try:
            return tuple(con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                         for name in ('odev_kume','odev','odev_satir','kitap'))
        finally:
            con.close()

    def test_unknown_student_does_not_leave_orphan_cluster(self):
        before = self._counts()
        response = self._bulk(student_id=999)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(before, self._counts())

    def test_untrusted_lesson_table_rejected_without_writes(self):
        before = self._counts()
        response = self._bulk(lesson_table='ogrenci')
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(before, self._counts())

    def test_empty_or_excessive_bulk_request_rejected(self):
        before = self._counts()
        for items in ([], [{'topic_id':1,'topic_name':'  ','book_name':'Kitap'}],
                      [{'topic_id':1,'topic_name':'Cebir','book_name':'Kitap'}]*501):
            with self.subTest(size=len(items)):
                self.assertEqual(self._bulk(items=items).status_code, 422)
        self.assertEqual(before, self._counts())

    def test_topic_id_name_mismatch_rejected(self):
        before = self._counts()
        res = self._bulk(items=[{'topic_id':2,'topic_name':'Cebir','book_name':'Kaynak'}])
        self.assertEqual(res.status_code, 422, res.text)
        self.assertEqual(before, self._counts())

    def test_invalid_date_rejected_from_single_and_bulk(self):
        before = self._counts()
        self.assertEqual(self._bulk(due_date='2026-02-31').status_code, 422)
        single = self.client.post('/api/homework', headers=self.headers,
                                  json={'student_id':1,'lesson':'lgs_matematik','book':'Kaynak',
                                        'topics':['Cebir'],'due_date':'31/10/2026'})
        self.assertEqual(single.status_code, 422, single.text)
        self.assertEqual(before, self._counts())

    def test_bulk_duplicate_items_insert_once_and_canonical_lesson(self):
        res = self._bulk(items=[dict(topic_id=1, topic_name='Cebir',book_name='Kaynak'),
                                dict(topic_id=1, topic_name='Cebir',book_name='Kaynak'),
                                dict(topic_id=2, topic_name='Geometri',book_name='Kaynak')])
        self.assertEqual(res.status_code, 200, res.text)
        with sqlite3.connect(self.path) as con:
            kid=res.json()['kume_id']
            rows=con.execute('''SELECT h.id,h.ders,s.ders FROM odev h JOIN odev_satir s
                               ON s.odev_id=h.id WHERE h.kume_id=?''',(kid,)).fetchall()
            self.assertEqual(len(rows),2)
            self.assertTrue(all(header==line=='lgs_matematik' for _,header,line in rows))

    def test_mid_transaction_write_error_rolls_back_all_tables(self):
        with sqlite3.connect(self.path) as con:
            con.execute('''CREATE TRIGGER reject_geometry BEFORE INSERT ON odev_satir
                         WHEN NEW.konu='Geometri' BEGIN SELECT RAISE(FAIL, 'synthetic write fault'); END''')
        before = self._counts()
        res=self._bulk(items=[dict(topic_id=1,topic_name='Cebir',book_name='Yeni Kitap'),
                              dict(topic_id=2,topic_name='Geometri',book_name='Yeni Kitap')])
        self.assertEqual(res.status_code,422,res.text)
        self.assertEqual(before,self._counts())

    def test_large_batch_survives_database_reopen(self):
        # 120 satırlı makul bir matris yazımı ve fiziksel SQLite yeniden açma.
        with sqlite3.connect(self.path) as con:
            con.executemany('INSERT INTO lgs_matematik(id,konu) VALUES (?,?)',
                            [(i, f'Konu {i}') for i in range(3,121)])
        items=[{'topic_id':1,'topic_name':'Cebir','book_name':'Kaynak'}]
        items.extend({'topic_id':i,'topic_name':f'Konu {i}','book_name':'Kaynak'}
                     for i in range(3,121))
        res=self._bulk(items=items)
        self.assertEqual(res.status_code,200,res.text)
        kume=res.json()['kume_id']
        # Veri yalnızca RAM'de değil; kapanıp yeniden açılan bağlantıda da var.
        with sqlite3.connect(self.path) as reopened:
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM odev WHERE kume_id=?',(kume,)).fetchone()[0],119)
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM odev_satir WHERE kume_id=? AND odev_id IS NOT NULL',(kume,)).fetchone()[0],119)
            self.assertEqual(reopened.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_completion_replay_keeps_original_timestamp(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE odev SET durum='yapildi',tamamlanma_tarihi='2001-01-01T00:00:00' WHERE id=1")
            con.execute("UPDATE odev_satir SET durum='tamam',tamamlanma_tarihi='2001-01-01T00:00:00' WHERE id=1")
        r = self.client.post('/api/homework/1/complete',headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT tamamlanma_tarihi FROM odev WHERE id=1').fetchone()[0],'2001-01-01T00:00:00')
            self.assertEqual(con.execute('SELECT tamamlanma_tarihi FROM odev_satir WHERE id=1').fetchone()[0],'2001-01-01T00:00:00')

    def test_bulk_replay_keeps_existing_timestamps(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE odev SET durum='yapildi',tamamlanma_tarihi='2001-01-01T00:00:00' WHERE id=1")
            con.execute("UPDATE odev_satir SET durum='tamam',tamamlanma_tarihi='2001-01-01T00:00:00' WHERE id=1")
        res=self.client.post('/api/homework/status/bulk',headers=self.headers,
                             json={'homework_ids':[1],'status':'tamam'})
        self.assertEqual(res.status_code,200,res.text)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT tamamlanma_tarihi FROM odev WHERE id=1').fetchone()[0],'2001-01-01T00:00:00')
            self.assertEqual(con.execute('SELECT tamamlanma_tarihi FROM odev_satir WHERE id=1').fetchone()[0],'2001-01-01T00:00:00')

    def test_bulk_does_not_update_corrupted_cross_student_link(self):
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO ogrenci VALUES(2,'Diger','Ogrenci',1,'Okul','8A','000')")
            con.execute("INSERT INTO odev_satir(id,odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum) VALUES(2,1,1,2,'lgs_matematik','Cebir','Kitap','2026-10-10','devam')")
        res=self.client.post('/api/homework/status/bulk',headers=self.headers,
                             json={'homework_ids':[1],'status':'tamam'})
        self.assertEqual(res.status_code,200,res.text)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT durum FROM odev_satir WHERE id=2').fetchone()[0],'devam')

    def test_bulk_links_all_unambiguous_legacy_children(self):
        with sqlite3.connect(self.path) as con:
            con.execute('UPDATE odev_satir SET odev_id=NULL, durum=? WHERE id=1',('devam',))
            for oid in (2,3):
                con.execute('''INSERT INTO odev_satir(id,odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum)
                    VALUES(?,NULL,1,1,'LGS Matematik','Cebir','Kitap','2026-10-10','devam')''',(oid,))
        res=self.client.post('/api/homework/status/bulk',headers=self.headers,
                             json={'homework_ids':[1],'status':'tamam'})
        self.assertEqual(res.status_code,200,res.text)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM odev_satir WHERE odev_id=1 AND durum=?',('tamam',)).fetchone()[0],3)

    def test_line_completion_does_not_ignore_pending_legacy_child(self):
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE odev SET durum='devam' WHERE id=1")
            con.execute("UPDATE odev_satir SET durum='devam' WHERE id=1")
            con.execute('''INSERT INTO odev_satir(id,odev_id,kume_id,ogrenci_id,ders,konu,kitap,tarih,durum)
                    VALUES(2,NULL,1,1,'LGS Matematik','Cebir','Kitap','2026-10-10','devam')''')
        r=self.client.post('/api/homework/1/complete',headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'devam')
            self.assertEqual(con.execute('SELECT odev_id FROM odev_satir WHERE id=2').fetchone()[0],1)

    def test_concurrent_status_requests_cannot_split_header_and_line(self):
        def task(index):
            if index % 2:
                return self.client.post('/api/homework/1/complete', headers=self.headers)
            return self.client.post('/api/homework/status/bulk',headers=self.headers,
                                    json={'homework_ids':[1],'status':'devam'})
        with ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(task,range(32)))
        self.assertTrue(all(res.status_code==200 for res in results),
                        [(r.status_code,r.text[:70]) for r in results if r.status_code!=200])
        with sqlite3.connect(self.path) as con:
            header=con.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0]
            line=con.execute('SELECT durum FROM odev_satir WHERE id=1').fetchone()[0]
            self.assertEqual(is_completed(header),is_completed(line))
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')


if __name__=='__main__':
    unittest.main()
