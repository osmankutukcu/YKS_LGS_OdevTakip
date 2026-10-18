from __future__ import annotations
"""V37 usability and protected-core regression guard.

Runs without PyQt6 (CI-only AST and checksums) and without user databases.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'ui' / 'curriculum_page.py'
SAFE_HASHES = ROOT / 'tests' / 'v37_protected_core_hashes.json'
BASELINE_METHODS = ROOT / 'tests' / 'v37_protected_ui_methods.json'


def _method(class_name, method_name):
    tree = ast.parse(UI.read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == class_name)
    return next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == method_name)


def _method_digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode('utf-8')).hexdigest()


def test_protected_homework_and_controls_byte_for_byte_unchanged():
    protected = json.loads(SAFE_HASHES.read_text(encoding='utf-8'))
    for relative, expected in protected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative


def test_legacy_mapping_save_and_leave_methods_are_unchanged():
    baseline = json.loads(BASELINE_METHODS.read_text(encoding='utf-8'))
    for class_name, methods in baseline.items():
        for name, expected in methods.items():
            assert _method_digest(_method(class_name, name)) == expected, (class_name, name)


def test_context_help_is_read_only_and_guide_does_not_write_data():
    func = _method('CurriculumPage', '_show_help')
    src = ast.unparse(func)
    assert 'QDialog' in src and 'dialog.exec()' in src
    assert not any(x in src for x in ('db.', 'set_lessons_for_group', 'save_mapping(', 'update_lesson_status'))


def test_navigation_is_only_navigation_and_manual_save_remains():
    src = UI.read_text(encoding='utf-8')
    assert '"1. Dersleri Yönet", "2. Gruplara Ata", "3. Konuları Düzenle"' in src
    assert 'self.tabs.setCurrentIndex(i)' in src
    assert 'self.tab_list.request_mapping.connect' in src
    assert 'self.btnSave.clicked.connect(self.save_mapping)' in src
    assert 'self.btnReset.clicked.connect(self.reset_mapping)' in src
    assert 'self.btnAdd.clicked.connect(self.add_lesson)' in src
    assert 'self.tabs.addTab(self.tab_list, "Ders Listesi")' in src
    assert 'self.tabs.addTab(self.tab_mapping, "Grup Eşleştirmeleri")' in src


def test_usability_guidance_covers_real_save_contracts():
    src = UI.read_text(encoding='utf-8')
    for marker in ('anında kaydedilir', 'kaydetmeden uygulanmaz',
                   'Gruba Ata', 'Kaydedilmemiş', 'Varsayılan Derslere Dön',
                   'eski ödevler silinmez', 'Aktif', 'Pasif'):
        assert marker.casefold() in src.casefold(), marker


def test_all_v37_ui_methods_compile():
    compile(UI.read_text(encoding='utf-8'), str(UI), 'exec')


def _isolated_ui_method(class_name, method_name):
    """Run pure UI selection/state logic with fakes, no Qt installation required."""
    node = _method(class_name, method_name)
    import copy
    isolated = copy.deepcopy(node)
    isolated.decorator_list = []
    ui_tree = ast.parse(UI.read_text(encoding='utf-8'))
    helper = next(n for n in ui_tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_search_key')
    import unicodedata
    scope = {'unicodedata': unicodedata}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                 '<ui-search>', 'exec'), scope)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[])),
                 '<ui-selection>', 'exec'), scope)
    return scope[method_name]


def test_filter_limited_bulk_selection_does_not_touch_other_lessons():
    from types import SimpleNamespace

    class FakeCheck:
        def __init__(self, name, value):
            self.name, self.checked = name, value
        def text(self):
            return self.name
        def setChecked(self, value):
            self.checked = value
        def isVisible(self):
            raise AssertionError('Widget visibility must never affect selection scope')

    physics = FakeCheck('Fizik', False)
    math = FakeCheck('Matematik', True)
    obj = SimpleNamespace(_group_name=lambda: '12-say',
                          txtFilter=SimpleNamespace(text=lambda: 'FİZ'),
                          check_map={'fizik': physics, 'matematik': math})
    fn = _isolated_ui_method('GroupMappingPage', '_select_visible')
    fn(obj, True)
    assert physics.checked and math.checked
    fn(obj, False)
    assert not physics.checked and math.checked


def test_unsaved_change_status_is_visible_and_save_remains_user_initiated():
    from types import SimpleNamespace

    class FakeLabel:
        def __init__(self): self.value = ''
        def setText(self, value): self.value = value

    class FakeButton:
        def __init__(self): self.value = None
        def setEnabled(self, value): self.value = value

    mode, feedback, save = FakeLabel(), FakeLabel(), FakeButton()
    obj = SimpleNamespace(_group_name=lambda: '8.sınıf',
                          _selected_ids=lambda: {'lgs_matematik', 'lgs_fen'},
                          _baseline={'lgs_matematik'},
                          _is_custom=False, _dirty=True,
                          lblMode=mode, lblUnsaved=feedback,
                          btnSave=save, btnAll=FakeButton(),
                          btnNone=FakeButton(), btnReset=FakeButton())
    fn = _isolated_ui_method('GroupMappingPage', '_update_state')
    fn(obj)
    assert '8.sınıf' in mode.value and '2 seçili ders' in mode.value
    assert '1 ders seçimi değişti' in feedback.value
    assert save.value is True
    obj._dirty = False
    fn(obj)
    assert save.value is False
    assert 'Kaydedilmemiş grup değişikliği bulunmuyor' in feedback.value


def test_turkish_search_normalization_without_qt():
    import unicodedata
    tree = ast.parse(UI.read_text(encoding='utf-8'))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name == '_search_key')
    env = {'unicodedata': unicodedata}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<search>', 'exec'), env)
    search = env['_search_key']
    assert search('FİZİK') == search('fizik')
    assert search('IŞIK') == search('ışık')
    assert search('GEOMETRİ') == search('geometri')
    assert search('BİYOLOJİ') == search('biyoloji')
