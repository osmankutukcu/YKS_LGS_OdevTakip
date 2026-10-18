from __future__ import annotations
"""V40 presentation-only guards; run without PyQt6 and never open user data."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'ui' / 'curriculum_page.py'
SOURCE = UI.read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


def _method(class_name, method_name):
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)


def _isolate_method(cls, name):
    helper = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == '_search_key')
    method = _method(cls, name)
    env = {'unicodedata': unicodedata}
    module = ast.fix_missing_locations(ast.Module(body=[helper, method], type_ignores=[]))
    exec(compile(module, '<isolated_curriculum_ui>', 'exec'), env)
    return env[name]


def test_v40_has_clear_three_steps_with_accessible_navigation():
    assert '"1. Dersleri Yönet", "2. Gruplara Ata", "3. Konuları Düzenle"' in SOURCE
    assert 'self.tabs.setCurrentIndex(i)' in SOURCE
    assert 'button.setAccessibleName(label)' in SOURCE
    assert 'button.setChecked(idx == step_index)' in SOURCE
    assert 'ⓘ Nasıl Kullanılır?' in SOURCE
    assert 'self.tabs.addTab(self.tab_integration, "Bağlantı Kontrolü")' in SOURCE


def test_v40_save_semantics_not_misrepresented():
    assert "'İptal' bunları geri almaz" in SOURCE
    assert 'Grup ataması ayrıca Kaydet gerektirir' in SOURCE
    assert 'self.btnSave.clicked.connect(self.save_mapping)' in SOURCE
    assert 'self.btnAdd.clicked.connect(self.add_lesson)' in SOURCE
    assert 'self.btnReset.clicked.connect(self.reset_mapping)' in SOURCE


def test_v40_accessibility_and_theme_styles_without_hardcoded_text_color():
    init = ast.unparse(_method('CurriculumPage', '__init__'))
    assert 'palette(alternate-base)' in init
    assert 'palette(midlight)' in init
    assert 'background: #ffffff' not in init
    assert 'color: #000000' not in init
    assert 'setAccessibleName' in init
    lessons = ast.unparse(_method('LessonListPage', '__init__'))
    for marker in ['self.search.setAccessibleName', 'self.table.setAccessibleName',
                   'self.filter_status.setAccessibleName', 'self.filter_group.setAccessibleName']:
        assert marker in lessons


def test_filter_search_filters_without_writes_and_reports_true_count():
    class FakeCell:
        def __init__(self, value): self.value = value
        def text(self): return self.value

    class FakeTable:
        def __init__(self, ids):
            self.ids = ids
            self.hidden = {}
        def rowCount(self): return len(self.ids)
        def item(self, r, c):
            return FakeCell(self.ids[r]) if c == 0 else None
        def setRowHidden(self, r, value): self.hidden[r] = value

    class FakeLabel:
        def setText(self, value): self.text = value
        def setVisible(self, value): self.visible = value

    table = FakeTable(['fizik', 'lgs_fen', 'tyt_matematik'])
    summary, empty = FakeLabel(), FakeLabel()
    obj = SimpleNamespace(
        table=table,
        search=SimpleNamespace(text=lambda: 'FİZİK'),
        filter_status=SimpleNamespace(currentIndex=lambda: 1),
        filter_group=SimpleNamespace(currentText=lambda: 'Tüm gruplar'),
        _records={
            'fizik': {'ad': 'Fizik', 'grup': 'Ara Sınıf', 'aktif': 1},
            'lgs_fen': {'ad': 'LGS Fen', 'grup': 'LGS', 'aktif': 0},
            'tyt_matematik': {'ad': 'TYT Matematik', 'grup': 'YKS', 'aktif': 1},
        }, summary=summary, empty_state=empty
    )
    _isolate_method('LessonListPage', '_apply_filters')(obj)
    assert table.hidden == {0: False, 1: True, 2: True}
    assert '1 ders gösteriliyor' in summary.text
    assert empty.visible is False
    obj.search = SimpleNamespace(text=lambda: 'tarih')
    _isolate_method('LessonListPage', '_apply_filters')(obj)
    assert empty.visible is True
    assert all(table.hidden.values())
    src = ast.unparse(_method('LessonListPage', '_apply_filters'))
    assert not any(marker in src for marker in ('db.', 'update_lesson_status', 'set_lessons_for_group'))


def test_protected_modules_match_v39_byte_for_byte():
    import zipfile
    archive = ROOT / 'tests' / 'v40_protected_hashes.txt'
    hashes = {}
    for line in archive.read_text(encoding='utf-8').splitlines():
        if line.strip():
            filename, expected = line.split(' ', 1)
            # V41 legitimately updates Koçluk only; V40's other protected files
            # retain their exact hash and receive separate V41 regression guards.
            if filename == 'ui/coaching_manager.py' and (
                ROOT / 'services' / 'coaching_curriculum_bridge_v41.py').exists():
                continue
            assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected, filename
            hashes[filename] = expected
    assert len(hashes) >= 7


def test_v40_presentation_compiles():
    compile(SOURCE, str(UI), 'exec')
