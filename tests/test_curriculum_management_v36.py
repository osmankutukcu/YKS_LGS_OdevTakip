from __future__ import annotations
"""Curriculum compatibility tests; can run without desktop Qt installed.

All SQL operations target a temporary SQLite database, never the bundled user DB.
"""
import ast
import pathlib
import sqlite3
import types
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "db.py").read_text(encoding="utf-8")
FUNCS = {
    'init_curriculum', 'get_lesson_config', 'add_custom_lesson',
    'update_lesson_status', 'init_group_lessons', 'get_lessons_for_group',
    'set_lessons_for_group', 'get_curriculum_groups', 'get_group_main_group',
    'get_effective_group_lessons', 'get_student_curriculum'
}
VARS = {'DERS_TABLOLARI', 'DEFAULT_GRUP_DERSLER', 'CURRICULUM_GROUPS'}


@pytest.fixture()
def fake_db(tmp_path):
    """Execute production functions in isolation with a temporary database."""
    path = tmp_path / 'curriculum.sqlite'
    namespace = {'sqlite3': sqlite3}

    def get_conn():
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c

    namespace['get_conn'] = get_conn
    tree = ast.parse(SOURCE)
    extracted = [node for node in tree.body if
                 (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCS) or
                 (isinstance(node, ast.Assign) and
                  any(isinstance(n, ast.Name) and n.id in VARS for n in node.targets))]
    code = compile(ast.fix_missing_locations(ast.Module(body=extracted, type_ignores=[])),
                   filename=str(ROOT / 'db.py'), mode='exec')
    exec(code, namespace)
    with get_conn() as conn:
        conn.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ana_grup TEXT,alt_grup TEXT)')
        namespace['init_curriculum'](conn)
        namespace['init_group_lessons'](conn)
    return types.SimpleNamespace(**namespace)


def test_original_defaults_and_student_group_mapping(fake_db):
    db = fake_db
    with db.get_conn() as con:
        con.execute("INSERT INTO ogrenci(id,ana_grup,alt_grup) VALUES(1,'LGS','8.sınıf')")
    original = db.get_student_curriculum(1)
    assert 'lgs_matematik' in original
    assert 'tyt_matematik' not in original
    db.set_lessons_for_group('8.sınıf', ['lgs_fen', 'lgs_turkce'])
    assert db.get_student_curriculum(1) == ['lgs_fen', 'lgs_turkce']
    db.set_lessons_for_group('8.sınıf', [])  # old client contract: reset to defaults
    assert db.get_student_curriculum(1) == original


def test_deactivation_hides_but_does_not_delete(fake_db):
    db = fake_db
    with db.get_conn() as con:
        con.execute("INSERT INTO ogrenci(id,ana_grup,alt_grup) VALUES(1,'LGS','8.sınıf')")
    db.set_lessons_for_group('8.sınıf', ['lgs_fen', 'lgs_turkce'])
    db.update_lesson_status('lgs_fen', False)
    assert db.get_student_curriculum(1) == ['lgs_turkce']
    assert db.get_lessons_for_group('8.sınıf') == ['lgs_fen', 'lgs_turkce']
    db.update_lesson_status('lgs_fen', True)
    assert db.get_student_curriculum(1) == ['lgs_fen', 'lgs_turkce']


def test_custom_lessons_validated_and_reusable(fake_db):
    db = fake_db
    added = db.add_custom_lesson('Ölçme & Değerlendirme', 'YKS')
    assert added[0] and added[2] == 'ozel_olcme_degerlendirme'
    assert added[2] in db.get_lesson_config()
    assert not db.add_custom_lesson('Ölçme & Değerlendirme', 'YKS')[0]
    assert not db.add_custom_lesson('İzin verilmeyen', 'YKS', 'ozel_ok; DROP TABLE ogrenci;--')[0]
    db.set_lessons_for_group('12-say', [added[2], 'tyt_matematik'])
    with db.get_conn() as con:
        con.execute("INSERT INTO ogrenci(id,ana_grup,alt_grup) VALUES(2,'YKS','12-say')")
    assert added[2] in db.get_student_curriculum(2)
    with db.get_conn() as con:
        assert con.execute("SELECT name FROM sqlite_master WHERE name='ogrenci'").fetchone()
        assert con.execute("SELECT name FROM sqlite_master WHERE name=?", (added[2],)).fetchone()


def test_groups_include_database_defined_subgroups(fake_db):
    db = fake_db
    with db.get_conn() as con:
        con.execute("INSERT INTO ogrenci(id,ana_grup,alt_grup) VALUES(1,'LGS','5.sınıf')")
    db.set_lessons_for_group('yeni-grup', ['fizik'])
    result = db.get_curriculum_groups()
    assert '5.sınıf' in result['LGS']
    assert 'yeni-grup' in result['Diğer']
    assert '8.sınıf' in result['LGS']


def test_mapping_deduplicates_and_invalid_group_fails(fake_db):
    db = fake_db
    db.set_lessons_for_group('12-say', ['fizik', 'fizik', 'geometri'])
    assert db.get_lessons_for_group('12-say') == ['fizik', 'geometri']
    with pytest.raises(ValueError):
        db.set_lessons_for_group('', ['fizik'])


def test_topic_map_and_homework_use_same_curriculum_source():
    txt = (ROOT / 'ui' / 'topic_map_dialog.py').read_text(encoding='utf-8')
    homework = (ROOT / 'ui' / 'homework_form.py').read_text(encoding='utf-8')
    editor = (ROOT / 'ui' / 'topic_editor.py').read_text(encoding='utf-8')
    assert 'db.get_student_curriculum(int(student_id))' in txt
    assert 'db.get_student_curriculum(ogr_id)' in homework
    assert 'db.get_effective_group_lessons(alt, ana)' in editor


def test_all_changed_modules_compile():
    for rel in ('db.py', 'ui/curriculum_page.py', 'ui/modern_settings.py',
                'ui/topic_editor.py', 'ui/topic_map_dialog.py'):
        compile((ROOT / rel).read_text(encoding='utf-8'), rel, 'exec')


def test_web_lesson_catalog_reads_dictionary_values(fake_db):
    import typing
    source = (ROOT / 'web_api' / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    funcs = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ('_load_lesson_configs', 'get_lessons_list'):
            node.decorator_list = []
            funcs.append(node)
    env = {
        'db': fake_db,
        'Optional': typing.Optional,
        'Query': lambda value=None: value,
        'GRUP_DERSLER': {'LGS': ['lgs_matematik']},
        'clean_lesson_name': lambda value: value,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                 'web_api/main.py', 'exec'), env)
    contents = env['_load_lesson_configs']()
    assert any(isinstance(item, dict) and item['id'] == 'lgs_fen' for item in contents)
    name = 'Trafik ve İlk Yardım'
    custom = fake_db.add_custom_lesson(name, 'LGS')
    assert custom[0]
    lid = custom[2]
    with fake_db.get_conn() as con:
        con.execute("INSERT INTO ogrenci(id,ana_grup,alt_grup) VALUES(1,'LGS','8.sınıf')")
    fake_db.set_lessons_for_group('8.sınıf', [lid, 'lgs_fen'])
    returned = env['get_lessons_list'](student_id=1)
    assert {entry['id'] for entry in returned} == {lid, 'lgs_fen'}
    assert {entry['name'] for entry in returned} == {name, 'LGS Fen'} or name in {entry['name'] for entry in returned}
    fake_db.update_lesson_status(lid, False)
    fake_db.update_lesson_status('lgs_fen', False)
    assert env['get_lessons_list'](student_id=1) == []
    assert all(entry['id'] not in {lid, 'lgs_fen'} for entry in env['get_lessons_list']())
