"""UI-independent contract tests for existing dashboard visuals and reliable counts."""
from __future__ import annotations
import sqlite3
from datetime import date
import pytest

from services.dashboard_metrics_v35 import build_snapshot, build_teacher_insight

TODAY = date(2026, 10, 13)


@pytest.fixture
def con():
    cx = sqlite3.connect(':memory:')
    cx.executescript('''
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, aktif INTEGER);
    CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, bitis_tarihi TEXT);
    CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
                      durum TEXT, saat_dk INTEGER, silindi INTEGER DEFAULT 0,
                      tamamlanma_tarihi TEXT);
    ''')
    yield cx
    cx.close()


def seed(con):
    con.executemany('INSERT INTO ogrenci VALUES (?,?,?,?)',
                    [(1, 'Ayşe', 'Demir', 1), (2, 'Ali', 'Yılmaz', 1), (3, 'Eski', 'Öğrenci', 0)])
    con.executemany('INSERT INTO odev_kume VALUES (?,?,?)',
                    [(10, 1, '2026-10-12'), (20, 2, '2026-10-13'),
                     (30, 3, '2026-10-01'), (40, 1, '2026-10-14')])
    con.executemany('INSERT INTO odev VALUES (?,?,?,?,?,?,?)', [
        (100,10,1,'devam',75,0,None),
        (101,10,1,'devam',60,0,None),
        (102,10,1,'yapildi',40,0,'2026-10-10 17:30:00'),
        (103,20,2,'devam',30,0,None),
        (104,20,2,'tamam',15,0,'2026-10-08 13:00:00'),
        (105,30,3,'devam',120,0,None),
        (106,40,1,'devam',55,1,None),
    ])


def test_count_items_not_clusters(con):
    seed(con)
    s = build_snapshot(con, today=TODAY)
    assert s.overdue_items == 2
    assert s.due_today_sets == 1
    assert s.active_students == 2
    assert s.total_items == 5
    assert s.done_items == 2
    assert s.completion_pct == 40


def test_student_alerts_count_items_and_exclude_inactive(con):
    seed(con)
    s = build_snapshot(con, today=TODAY)
    assert len(s.alerts) == 1
    assert 'Ayşe D.' in s.alerts[0]['text']
    assert '2 ödev' in s.alerts[0]['text']


def test_deadline_cohort_not_completion_day(con):
    seed(con)
    s = build_snapshot(con, today=TODAY)
    by_date = {x['date']: x for x in s.trend}
    assert by_date['2026-10-12']['total'] == 3
    assert by_date['2026-10-12']['done'] == 1
    assert by_date['2026-10-13']['total'] == 2
    assert by_date['2026-10-13']['done'] == 1
    assert by_date['2026-10-08']['total'] == 0  # completion date is *not* due date


def test_missing_history_not_made_up(con):
    seed(con)
    s = build_snapshot(con, today=TODAY)
    assert s.verified_study_minutes is None
    assert s.verified_streak_days is None
    old_contract = s.to_gamification_stats()
    assert old_contract['weekly_minutes'] == 0
    assert old_contract['streak_days'] == 0
    assert old_contract['top_marathon'] is None


def test_teacher_decision_based_on_evidence(con):
    seed(con)
    s = build_snapshot(con, today=TODAY)
    tip = build_teacher_insight(s)
    assert 'görüşme' in tip.lower()
    assert 'Ayşe D.' in tip
    assert '%100 risk' not in tip


def test_empty_students_and_no_data_separate(con):
    s = build_snapshot(con, today=TODAY)
    assert s.active_students == 0
    assert s.completion_pct is None
    assert s.trend and all(d['total'] == 0 for d in s.trend)
    assert 'Öğrenci Kaydı' in build_teacher_insight(s)


def test_active_students_without_homework(con):
    con.execute("INSERT INTO ogrenci VALUES (1, 'Seda','A',1)")
    s = build_snapshot(con, today=TODAY)
    assert s.active_students == 1
    assert s.completion_pct is None
    assert 'henüz ödev' in build_teacher_insight(s)


def test_due_today_action(con):
    con.execute("INSERT INTO ogrenci VALUES (1,'Veli','T',1)")
    con.execute("INSERT INTO odev_kume VALUES (1,1,'2026-10-13')")
    con.execute("INSERT INTO odev VALUES (1,1,1,'devam',75,0,NULL)")
    s = build_snapshot(con, today=TODAY)
    assert s.due_today_sets == 1
    assert 'kontrol bekleyen 1 ödev kümesi' in build_teacher_insight(s)


def test_deleted_homeworks_do_not_count(con):
    con.execute("INSERT INTO ogrenci VALUES (1,'A','B',1)")
    con.execute("INSERT INTO odev_kume VALUES (1,1,'2026-10-01')")
    con.execute("INSERT INTO odev VALUES (1,1,1,'devam',75,1,NULL)")
    s = build_snapshot(con, today=TODAY)
    assert s.overdue_items == 0 and s.total_items == 0


def test_non_legacy_no_soft_delete_column():
    cx = sqlite3.connect(':memory:')
    try:
        cx.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER, durum TEXT);
          INSERT INTO ogrenci VALUES (1,'A','B',1);
          INSERT INTO odev_kume VALUES (1,1,'2026-10-01');
          INSERT INTO odev VALUES (1,1,1,'devam');
        ''')
        assert build_snapshot(cx, today=TODAY).overdue_items == 1
    finally:
        cx.close()


def test_done_state_case_insensitive(con):
    con.execute("INSERT INTO ogrenci VALUES (1,'A','B',1)")
    con.execute("INSERT INTO odev_kume VALUES (1,1,'2026-10-13')")
    con.execute("INSERT INTO odev VALUES (1,1,1,'YAPILDI',75,0,NULL)")
    s = build_snapshot(con, today=TODAY)
    assert s.done_items == 1 and s.due_today_sets == 0


def test_no_writes_during_snapshot(con):
    seed(con)
    con.commit()
    seen = []
    con.set_trace_callback(seen.append)
    build_snapshot(con, today=TODAY)
    assert not any(x.strip().split()[0].upper() in ('UPDATE','DELETE','INSERT','ALTER', 'CREATE')
                   for x in seen)


def test_missing_required_table_is_error_not_zero(con):
    con.execute('DROP TABLE odev')
    with pytest.raises(sqlite3.OperationalError):
        build_snapshot(con, today=TODAY)


def test_many_students_scales_with_grouped_queries(con):
    con.executemany('INSERT INTO ogrenci VALUES (?,?,?,1)',
                    [(i,f'S{i}','Test') for i in range(1,1001)])
    con.executemany('INSERT INTO odev_kume VALUES (?,?,?)',
                    [(i,i,'2026-10-12') for i in range(1,1001)])
    con.executemany('INSERT INTO odev VALUES (?,?,?,?,?,?,?)',
                    [(i,i,i,'devam',45,0,None) for i in range(1,1001)])
    trace = []
    con.set_trace_callback(trace.append)
    snapshot = build_snapshot(con, today=TODAY)
    assert snapshot.active_students == 1000
    assert snapshot.overdue_items == 1000
    assert sum('SELECT' in stmt.upper() for stmt in trace) <= 6
