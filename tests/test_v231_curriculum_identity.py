"""V23.1 pure SQL/read-only identity contract. No PyQt required."""
import sqlite3
import unittest

from services.curriculum_v23.impact import CurriculumSafetyError
from services.curriculum_v231 import TopicIdentity, effective_topics, resolve_legacy, topic_key


def conn():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE ders_tanimlari (id TEXT PRIMARY KEY, ad TEXT);
      INSERT INTO ders_tanimlari VALUES ('fizik','Fizik');
      CREATE TABLE fizik (id INTEGER PRIMARY KEY, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
      INSERT INTO fizik VALUES (1,'Elektrik',20,30),(2,'Basınç',10,15),(3,'Hareket',35,50);
      CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ana_grup TEXT, alt_grup TEXT);
      INSERT INTO ogrenci VALUES (1,'YKS','12-say'),(2,'YKS','12-ea'),(3,NULL,NULL);
      CREATE TABLE grup_konu_duzen (id INTEGER PRIMARY KEY, ana_grup TEXT, alt_grup TEXT,
        ders TEXT, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
      INSERT INTO grup_konu_duzen VALUES (1,'YKS','12-say','fizik','Elektrik',25,40),
        (2,'YKS','12-ea','fizik','Kimya',10,20),
        (3,'YKS','12-say','fizik','Dalgalar',30,45);
      CREATE TABLE ogrenci_konu_duzen (id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
        ders TEXT, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
      INSERT INTO ogrenci_konu_duzen VALUES(1,1,'fizik','Elektrik',31,60);
    ''')
    return db


class V231IdentityTests(unittest.TestCase):
    def setUp(self):
        self.db = conn()

    def tearDown(self):
        self.db.close()

    def test_id_namespace_differs_per_scope(self):
        names = [TopicIdentity('Genel','fizik',1).key,
                 TopicIdentity('Grup','fizik',1,ana_grup='YKS',alt_grup='12-say').key,
                 TopicIdentity('Öğrenci','fizik',1,ogrenci_id=1).key]
        self.assertEqual(3,len(set(names)))

    def test_student_id_namespace_differs(self):
        self.assertNotEqual(TopicIdentity('Öğrenci','fizik',1,ogrenci_id=1).key,
                            TopicIdentity('Öğrenci','fizik',1,ogrenci_id=2).key)

    def test_group_namespace_differs(self):
        self.assertNotEqual(TopicIdentity('Grup','fizik',1,ana_grup='YKS',alt_grup='12-say').key,
                            TopicIdentity('Grup','fizik',1,ana_grup='YKS',alt_grup='12-ea').key)

    def test_identity_fails_mismatched_scopes(self):
        for kwargs in [{'scope':'Genel','ders':'fizik','row_id':1,'ogrenci_id':1},
                       {'scope':'Grup','ders':'fizik','row_id':1,'ana_grup':'YKS'},
                       {'scope':'Öğrenci','ders':'fizik','row_id':1},
                       {'scope':'Genel','ders':'fizik','row_id':0}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(CurriculumSafetyError):
                TopicIdentity(**kwargs)

    def test_turkish_distinctions_not_synonyms(self):
        self.assertEqual(topic_key(' İÇİN '), topic_key('için'))
        self.assertNotEqual(topic_key('ışık'), topic_key('isik'))

    def test_student_layer_wins_without_changing_general(self):
        snap = effective_topics(self.db,ders='fizik',ogrenci_id=1)
        topic = next(t for t in snap.topics if t.record.name=='Elektrik')
        self.assertEqual('Öğrenci', topic.record.identity.scope)
        self.assertEqual(31,topic.record.target_questions)
        self.assertEqual({'Genel','Grup'}, {x.scope for x in topic.overridden})
        self.assertEqual(3, len(snap.topics) - 1)  # Elektrik + Basınç + Hareket + Dalgalar

    def test_different_student_not_leaked(self):
        snap = effective_topics(self.db,ders='fizik',ogrenci_id=2)
        self.assertNotIn('Dalgalar', [t.record.name for t in snap.topics])
        self.assertIn('Kimya', [t.record.name for t in snap.topics])
        self.assertEqual('Genel', next(t for t in snap.topics if t.record.name=='Elektrik').record.identity.scope)

    def test_student_missing_group_never_guesses(self):
        snap = effective_topics(self.db,ders='fizik',ogrenci_id=3)
        self.assertEqual({'Elektrik','Basınç','Hareket'}, {t.record.name for t in snap.topics})
        self.assertTrue(snap.warnings)

    def test_group_only_explicit(self):
        snap = effective_topics(self.db,ders='fizik',ana_grup='YKS',alt_grup='12-say')
        self.assertEqual({'Elektrik','Basınç','Hareket','Dalgalar'}, {t.record.name for t in snap.topics})
        self.assertEqual('Grup',next(t for t in snap.topics if t.record.name=='Elektrik').record.identity.scope)

    def test_wrong_student_id_is_rejected(self):
        with self.assertRaises(CurriculumSafetyError):
            effective_topics(self.db,ders='fizik',ogrenci_id=999)

    def test_explicit_wrong_group_rejected(self):
        with self.assertRaises(CurriculumSafetyError):
            effective_topics(self.db,ders='fizik',ogrenci_id=1,ana_grup='YKS',alt_grup='12-ea')

    def test_partial_group_rejected(self):
        with self.assertRaises(CurriculumSafetyError):
            effective_topics(self.db,ders='fizik',ana_grup='YKS')

    def test_invalid_subject_not_queried(self):
        with self.assertRaises(CurriculumSafetyError):
            effective_topics(self.db,ders='ogrenci')

    def test_legacy_multi_scope_collision_ambiguous(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        out=resolve_legacy(snap,topic_name='Elektrik')
        self.assertEqual('ambiguous',out.status)
        self.assertIsNone(out.topic)

    def test_legacy_general_numeric_id_does_not_force_conflicted_name(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual('ambiguous',resolve_legacy(snap,topic_name='Elektrik',general_topic_id=1).status)

    def test_legacy_single_name_can_be_unique(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        out=resolve_legacy(snap,topic_name='Hareket')
        self.assertEqual('unique',out.status)
        self.assertEqual(3,out.topic.identity.row_id)

    def test_legacy_missing_no_guess(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual('missing',resolve_legacy(snap,topic_name='Dönme').status)

    def test_legacy_rename_drift_needs_review(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual('name_changed_review',resolve_legacy(snap,topic_name='Eski Elektrik',general_topic_id=1).status)

    def test_legacy_wrong_id_rejected(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual('mismatch',resolve_legacy(snap,topic_name='Hareket',general_topic_id=999).status)

    def test_duplicate_in_same_scope_cannot_become_effective(self):
        self.db.execute("INSERT INTO fizik VALUES(4,'elektrik',10,20)")
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertIn('elektrik',snap.ambiguous_keys)
        self.assertNotIn('Elektrik',[t.record.name for t in snap.topics])

    def test_read_only_no_schema_or_data_changes(self):
        before=list(self.db.iterdump())
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        resolve_legacy(snap,topic_name='Elektrik')
        self.assertEqual(before,list(self.db.iterdump()))

    def test_missing_optional_tables_gracefully(self):
        self.db.execute('DROP TABLE grup_konu_duzen')
        self.db.execute('DROP TABLE ogrenci_konu_duzen')
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual(3,len(snap.topics))

    def test_order_general_first_and_extra_last(self):
        snap=effective_topics(self.db,ders='fizik',ogrenci_id=1)
        self.assertEqual(['Elektrik','Basınç','Hareket','Dalgalar'],[x.record.name for x in snap.topics])

if __name__=='__main__':
    unittest.main()
