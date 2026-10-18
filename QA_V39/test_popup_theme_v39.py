# -*- coding: utf-8 -*-
"""V39 headless regression: 33 themes, contrast, menu lifecycle, QoS hooks.

No PyQt dependency and no user settings or database is loaded.
"""
import ast
import importlib.util
import sys
import types
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ui=types.ModuleType('ui');ui.__path__=[str(ROOT/'ui')];sys.modules['ui']=ui
settings={}
appset=types.ModuleType('ui.app_settings')
appset.ayar_get=lambda key, default=None: settings.get(key) or default
appset.ayar_set=lambda key, value: settings.__setitem__(key, str(value) if value is not None else '')
sys.modules['ui.app_settings']=appset

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/filename)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod

theme=load('ui.theme','ui/theme.py')
load('ui.theme_tokens_v37','ui/theme_tokens_v37.py')

class QObject:
    def __init__(self,parent=None):self.parent=parent
class Type:Show=1;Hide=2
class QEvent:Type=Type
class Event:
    def __init__(self,type_):self.type_=type_
    def type(self):return self.type_
class QApplication:
    def __init__(self):self.filters=[];self.windows=[]
    def installEventFilter(self,obj):self.filters.append(obj)
    def topLevelWidgets(self):return self.windows
class QMenu:
    def __init__(self,stylesheet=''):
        self.css=stylesheet;self.props={};self.triggers=[];self.commands=['sample','delete']
    def property(self,key):return self.props.get(key)
    def setProperty(self,key,value):self.props[key]=value
    def styleSheet(self):return self.css
    def setStyleSheet(self,value):self.css=value
qtcore=types.ModuleType('PyQt6.QtCore');qtcore.QObject=QObject;qtcore.QEvent=QEvent
qtwidgets=types.ModuleType('PyQt6.QtWidgets');qtwidgets.QApplication=QApplication;qtwidgets.QMenu=QMenu
sys.modules.update({'PyQt6':types.ModuleType('PyQt6'),'PyQt6.QtCore':qtcore,'PyQt6.QtWidgets':qtwidgets})
runtime=load('ui.theme_popup_runtime_v39','ui/theme_popup_runtime_v39.py')

for name in theme.tema_presets():
    theme.tema_apply_preset(name)
    p=runtime.menu_palette()
    for bg,fg in [('bg','fg'),('selected','selected_fg'),('disabled_bg','disabled_fg')]:
        ratio=theme.contrast_ratio(p[bg],p[fg]);assert ratio>=4.5,(name,bg,fg,ratio)
    assert runtime.menu_qss().count('{')==runtime.menu_qss().count('}')
print('PASS: 33 presets × 3 menu text-background pairings (WCAG AA)')

app=QApplication()
menu=QMenu('QMenu { padding: 6px; background:#fff; }')
other=QMenu('QMenu { padding: 5px; }')
other.setProperty('_v39_preserve_menu_style',True)
app.windows=[menu,other]
runtime.install_popup_menu_guard(app)
assert len(app.filters)==1
assert 'padding: 6px' in menu.styleSheet()
assert 'QMenu::item:selected' in menu.styleSheet()
assert menu.commands==['sample','delete']
assert other.styleSheet()=='QMenu { padding: 5px; }'
first=menu.styleSheet();runtime.install_popup_menu_guard(app)
assert len(app.filters)==1 and menu.styleSheet()==first
assert app.filters[0].eventFilter(QMenu(),Event(Type.Show)) is False
assert app.filters[0].eventFilter(menu,Event(Type.Hide)) is False
menu.setStyleSheet('QMenu { border-radius: 11px; }')
runtime.refresh_open_popup_menus(app)
assert 'border-radius: 11px' in menu.styleSheet()
assert 'padding: 6px' not in menu.styleSheet()
assert menu.styleSheet().count('QMenu::item:selected {')==1
# Switching to a completely different theme must replace, not stack, old CSS.
theme.tema_apply_preset('Dracula')
old=menu.styleSheet();runtime.refresh_open_popup_menus(app)
assert old!=menu.styleSheet() and menu.styleSheet().count('QMenu::item:selected {')==1
assert menu.commands==['sample','delete']
print('PASS: Show, refresh, app singleton guard, local CSS edits, opt-out, action preservation')

p=(ROOT/'ui/progress.py').read_text()
assert 'register_theme_listener(self)' in p
assert 'def _on_theme_changed(self)' in p
assert 'Qt.TextFormat.PlainText' in p
assert 'color:#000000' not in p
print('PASS: legacy progress dialog updates with theme; no forced black rich-text style')

book=(ROOT/'ui/book_dialog.py').read_text()
assert 'background:#fff; color:#111827;' in book
print('PASS: fixed-white book search/input fields have explicit dark foreground')

p38=(ROOT/'ui/theme_popup_runtime_v38.py').read_text()
assert 'QErrorMessage' in p38
assert 'return False' in p38
print('PASS: QErrorMessage included; Qt dialog event handling remains unconsumed')

for py in [p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]:
    ast.parse(py.read_text(encoding='utf-8-sig'),filename=str(py))
print('PASS: complete project AST')
