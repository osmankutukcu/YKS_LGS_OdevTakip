"""V35 opt-in planner bridge. Fully Qt-free, in-memory and read-only."""
import sqlite3
from datetime import date
from services.adaptive_coaching_v28.quick_notes import set_note
from services.adaptive_coaching_v25.engine import ensure_schema, save_observation
from services.weekly_adaptive_bridge_v35 import suggested_lesson_focus, merge_teacher_approved_focus


def setup():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
        CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
             ders TEXT, konu_ad TEXT, kitap_ad TEXT, saat_dk INTEGER, durum TEXT);
        INSERT INTO ogrenci VALUES (1,'Sena','Bir'), (2,'Sena','İki');
        INSERT INTO odev_kume VALUES(7,1),(8,2);
        INSERT INTO odev VALUES (10,7,1,'Fizik','Enerji','A',75,'devam'),
                                (11,7,1,'Matematik','Problemler','B',45,'devam'),
                                (12,8,2,'Fizik','Enerji','C',60,'devam');
    ''')
    con.commit()
    return con


def tasks():
    return [{'ders':'Fizik','konu':'Enerji','kitap':'A','sure':75},
            {'ders':'Matematik','konu':'Problemler','kitap':'B','sure':45}]


def snapshot(con):
    return list(con.execute('SELECT * FROM odev ORDER BY id'))


def test_no_notes_or_evidence_means_no_guess_no_schema():
    con=setup()
    before=snapshot(con)
    assert suggested_lesson_focus(con,1,tasks()) == []
    assert snapshot(con)==before
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'adaptive_%'").fetchone()[0] == 0
    con.close()


def test_teacher_observation_exact_current_lesson_and_student():
    con=setup()
    set_note(con,1,10,'concept')
    set_note(con,2,12,'time')
    original=snapshot(con)
    con.execute('PRAGMA query_only=ON')
    suggestions=suggested_lesson_focus(con,1,tasks())
    assert len(suggestions)==1 and suggestions[0]['lesson']=='Fizik'
    assert suggestions[0]['topics']==['Enerji']
    assert len(suggestions[0]['reasons'])==1
    assert snapshot(con)==original
    con.close()


def test_other_student_observation_does_not_leak():
    con=setup()
    ensure_schema(con)
    save_observation(con,2,'Fizik','Enerji',homework_id=12,
        correct=1,wrong=7,blank=0,observed_on=date.today().isoformat())
    assert suggested_lesson_focus(con,1,tasks())==[]
    assert suggested_lesson_focus(con,2,[{'ders':'Fizik','konu':'Enerji','sure':60}])[0]['lesson']=='Fizik'
    con.close()


def test_independent_measurement_signal_only_when_relevant_and_recent():
    con=setup()
    ensure_schema(con)
    save_observation(con,1,'Fizik','Enerji',homework_id=10,
        correct=2,wrong=6,blank=0,observed_on=date.today().isoformat())
    data=suggested_lesson_focus(con,1,tasks())
    assert data[0]['lesson']=='Fizik' and '2/8' in data[0]['reasons'][0]
    assert suggested_lesson_focus(con,1,[{'ders':'Türkçe','konu':'Paragraf','sure':20}])==[]
    con.close()


def test_workload_and_easy_do_not_expand_homework_priority():
    con=setup()
    set_note(con,1,10,'workload')
    set_note(con,1,11,'easy')
    assert suggested_lesson_focus(con,1,tasks())==[]
    con.close()


def test_merge_only_on_explicit_teacher_approval_and_deduplicates():
    source='Kimya, Matematik'
    suggestions=[{'lesson':'Fizik'}, {'lesson':'matematik'}]
    assert merge_teacher_approved_focus(source,suggestions)=='Kimya, Matematik, Fizik'
    assert source=='Kimya, Matematik'


def test_invalid_student_rejected_and_never_changes_tasks():
    con=setup()
    before=tasks()
    try:
        suggested_lesson_focus(con,999,before)
        assert False, 'should reject wrong id'
    except ValueError:
        pass
    assert before==tasks()
    con.close()


def test_approved_focus_reuses_original_calendar_without_new_task_or_minutes():
    from services.smart_calendar import SmartCalendarService
    from services.planning_constraints import serialize_details
    assignments=tasks()
    settings={'planner_version':2, 'school_by_day':{},'blocks':[],
              'wake':'07:00','sleep':'23:00','max':180,'empty':'Yok',
              'focus':'Kimya','weekend_mode':'Dengeli'}
    default=SmartCalendarService.create_weekly_plan_data('Sena Bir',assignments,serialize_details(settings))
    after=dict(settings,focus=merge_teacher_approved_focus('Kimya',[{'lesson':'Fizik'}]))
    adaptive=SmartCalendarService.create_weekly_plan_data('Sena Bir',assignments,serialize_details(after))
    def minutes(b):
        return sum(t.sure for day in b['days'] for t in day.tasks) + sum(t.sure for t in b['profile']['unassigned'])
    assert minutes(default)==minutes(adaptive)==120
    assert assignments==tasks()
    assert 'Fizik' in after['focus'] and settings['focus']=='Kimya'
    assert 'Yerleştirilemeyen' in adaptive['html']
