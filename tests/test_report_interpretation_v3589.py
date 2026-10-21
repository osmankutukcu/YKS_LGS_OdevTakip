# -*- coding: utf-8 -*-
import sqlite3

from services.report_interpretation_v3589 import interpret_chart
from services.report_diagnostics_v3589 import inspect_report_sources


def test_empty_or_zero_is_not_failure():
    assert "başarısızlık değildir" in interpret_chart("Durum Dağılımı", [])
    assert "başarısızlık değildir" in interpret_chart("Durum Dağılımı", [("devam", 0)])


def test_cancellation_does_not_enter_completion_denominator():
    html = interpret_chart("Durum Dağılımı", [("devam", 5), ("yapildi", 5), ("iptal", 90)])
    assert "%50.0" in html
    assert "iptal: 90" in html


def test_incomplete_data_not_called_psychological_risk():
    h = interpret_chart("Haftalık Saat Trendi (dk)", [("2026-W41", 60), ("2026-W42", 30)])
    assert "azaldı" in h
    assert "motivasyon veya başarı değişimi çıkarılmamalı" in h
    assert "zorlanma kanıtı değildir" in interpret_chart("Konu Verimi (dk/konu)", [("Fizik", 90)])


def test_escape_user_controlled_html():
    h = interpret_chart("Geciken Ödevler", [("<img src=x onerror=alert(1)>", 4)])
    assert "<img" not in h
    assert "&lt;img" in h


def test_invalid_metrics_skipped():
    h = interpret_chart("Haftalık Saat Trendi (dk)", [("a", float('nan')), ("b", -1), ("c", 5)])
    assert "yalnızca bir hafta" in h


def test_reader_no_mutations():
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE odev(ogrenci_id INTEGER,kume_id INTEGER,ders TEXT);
        CREATE TABLE odev_satir(ogrenci_id INTEGER,kume_id INTEGER,ders TEXT);
        CREATE TABLE ogrenci_perf_gunluk(ogrenci_id INTEGER);
        INSERT INTO odev VALUES(1,2,'mat'),(2,3,'fiz');
        INSERT INTO odev_satir VALUES(1,2,'mat'),(9,8,'bio');
    """)
    con.execute("PRAGMA query_only = ON")
    info = inspect_report_sources(con)
    assert (info['main'],info['rows'],info['candidate_keys']) == (2, 2, 1)
    assert info['monthly'] and not info['weekly']
    con.close()


def test_missing_tables_reported_without_creating():
    con=sqlite3.connect(':memory:')
    info=inspect_report_sources(con)
    assert set(info['missing']) == {'odev','odev_satir'}
    assert info['candidate_keys'] == 0
    con.close()
