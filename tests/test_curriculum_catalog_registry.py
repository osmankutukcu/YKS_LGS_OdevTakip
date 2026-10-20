"""Comprehensive unit tests for Curriculum Catalog Registry and modular switching."""
import json
import sqlite3
import unittest
from datetime import date
from pathlib import Path

from services.curriculum_catalog_registry import (
    list_available_catalogs,
    get_active_catalog_id,
    set_active_catalog_id,
    get_active_catalog_data,
    is_curriculum_enabled,
    get_catalog_metadata,
    load_catalog_by_id,
    clear_cache,
    DEFAULT_CATALOG_ID,
)
from services.coach_curriculum_v7 import (
    build_outcome_review,
    exact_outcome,
    detect_grade,
    load_catalog,
)

TODAY = date(2026, 10, 11)


def make_test_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, ana_grup TEXT, alt_grup TEXT);
        INSERT INTO ogrenci VALUES(1, 'Hüsnü', 'Mühendis', 'YKS', 'Mezun');
        INSERT INTO ogrenci VALUES(2, 'Ahmet', 'Sayısal', 'YKS', '11-SAY');
        INSERT INTO ogrenci VALUES(3, 'Zeynep', 'Temel', 'YKS', '9. Sınıf');

        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, bitis_tarihi TEXT);
        INSERT INTO odev_kume VALUES(1, '2026-10-01'), (2, '2026-10-30');

        CREATE TABLE odev_satir(
            id INTEGER PRIMARY KEY, ogrenci_id INTEGER, odev_id INTEGER,
            kume_id INTEGER, ders TEXT, konu TEXT, kitap TEXT,
            durum TEXT, tarih TEXT, tamamlanma_tarihi TEXT, silindi INTEGER DEFAULT 0
        );

        CREATE TABLE koc_konu_takip(
            id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            ders_adi TEXT, konu_adi TEXT, hakimiyet_puani REAL, updated_at TEXT
        );

        CREATE TABLE ayar(anahtar TEXT PRIMARY KEY, deger TEXT);
    """)
    return db


class CurriculumCatalogRegistryTest(unittest.TestCase):
    def setUp(self):
        clear_cache()
        self.db = make_test_db()

    def tearDown(self):
        clear_cache()
        self.db.close()

    def test_catalog_definitions_structure(self):
        catalogs = list_available_catalogs()
        self.assertGreaterEqual(len(catalogs), 4)
        catalog_ids = [c["id"] for c in catalogs]
        self.assertIn("yks_full", catalog_ids)
        self.assertIn("maarif_modeli", catalog_ids)
        self.assertIn("meb_pilot", catalog_ids)
        self.assertIn("disabled", catalog_ids)

    def test_yks_full_catalog_integrity(self):
        data = load_catalog_by_id("yks_full")
        self.assertEqual(len(data), 861)
        subjects = {d["subject"] for d in data}
        self.assertIn("Fizik", subjects)
        self.assertIn("Matematik", subjects)
        self.assertIn("Kimya", subjects)
        self.assertIn("Biyoloji", subjects)
        self.assertIn("Coğrafya", subjects)
        self.assertIn("Tarih", subjects)
        for row in data:
            self.assertTrue(1 <= row["grade"] <= 12)
            self.assertTrue(row["source_url"].startswith("https://"))
            self.assertEqual(row["review_status"], "official_excerpt")
            self.assertGreaterEqual(len(row["topic_aliases"]), 1)

    def test_maarif_modeli_catalog_integrity(self):
        data = load_catalog_by_id("maarif_modeli")
        self.assertGreater(len(data), 10)
        for row in data:
            self.assertIn("tymm.meb.gov.tr", row["source_url"])
            self.assertEqual(row["grade"], 9)

    def test_meb_pilot_catalog_integrity(self):
        data = load_catalog_by_id("meb_pilot")
        self.assertEqual(len(data), 4)
        for row in data:
            self.assertIn("ttkbyayin.meb.gov.tr", row["source_url"])

    def test_disabled_catalog_returns_empty(self):
        data = load_catalog_by_id("disabled")
        self.assertEqual(len(data), 0)

    def test_active_catalog_switching_and_toggle(self):
        set_active_catalog_id("disabled")
        self.assertFalse(is_curriculum_enabled())
        self.assertEqual(len(get_active_catalog_data()), 0)

        set_active_catalog_id("yks_full")
        self.assertTrue(is_curriculum_enabled())
        self.assertEqual(len(get_active_catalog_data()), 861)

        set_active_catalog_id("maarif_modeli")
        self.assertTrue(is_curriculum_enabled())
        self.assertGreater(len(get_active_catalog_data()), 10)

        # Restore default
        set_active_catalog_id(DEFAULT_CATALOG_ID)

    def test_canonical_subject_normalization(self):
        catalog = load_catalog_by_id("yks_full")
        # Enerji ve Hareket in 11th grade Fizik
        r1 = exact_outcome("Fizik", "Enerji ve Hareket", 11, catalog)
        r2 = exact_outcome("AYT Fizik", "Enerji ve Hareket", 11, catalog)
        r3 = exact_outcome("ayt_fizik", "Enerji ve Hareket", 11, catalog)
        self.assertIsNotNone(r1)
        self.assertEqual(r1["code"], r2["code"])
        self.assertEqual(r1["code"], r3["code"])

        # Trigonometri in 11th grade Matematik
        m1 = exact_outcome("Matematik", "Trigonometri", 11, catalog)
        m2 = exact_outcome("AYT Matematik", "Trigonometri", 11, catalog)
        m3 = exact_outcome("ayt_matematik", "Trigonometri", 11, catalog)
        self.assertIsNotNone(m1)
        self.assertEqual(m1["code"], m2["code"])
        self.assertEqual(m1["code"], m3["code"])

    def test_build_outcome_review_with_full_yks_catalog(self):
        # Insert overdue homework for student 2 (11-SAY) in Enerji ve Hareket
        self.db.execute("""
            INSERT INTO odev_satir(ogrenci_id, kume_id, ders, konu, kitap, durum, silindi)
            VALUES(2, 1, 'AYT Fizik', 'Enerji ve Hareket', 'Kitap 3D', 'devam', 0)
        """)
        catalog = load_catalog_by_id("yks_full")
        report = build_outcome_review(self.db, 2, as_of=TODAY, catalog=catalog)
        self.assertEqual(report["mapped_topics"], 1)
        self.assertEqual(len(report["actions"]), 1)
        action = report["actions"][0]
        self.assertEqual(action["type"], "overdue_check")
        self.assertEqual(action["subject"], "Fizik")
        self.assertEqual(action["grade"], 11)
        self.assertIn("mufredat.meb.gov.tr", action["source_url"])

    def test_build_outcome_review_with_grade_override_for_mezun(self):
        # Insert overdue homework for student 1 (Mezun candidate) in 11th grade topic
        self.db.execute("""
            INSERT INTO odev_satir(ogrenci_id, kume_id, ders, konu, kitap, durum, silindi)
            VALUES(1, 1, 'Fizik', 'Enerji ve Hareket', 'Test Kitabı', 'devam', 0)
        """)
        catalog = load_catalog_by_id("yks_full")
        # Without grade override: Mezun student has grade=None -> 0 actions
        r_none = build_outcome_review(self.db, 1, as_of=TODAY, catalog=catalog)
        self.assertEqual(len(r_none["actions"]), 0)

        # With teacher selecting 11th grade: matches!
        r_11 = build_outcome_review(self.db, 1, as_of=TODAY, catalog=catalog, grade_override=11)
        self.assertEqual(len(r_11["actions"]), 1)
        self.assertEqual(r_11["actions"][0]["code"], "FIZ-GEN-11.1.6.1")


if __name__ == "__main__":
    unittest.main()
