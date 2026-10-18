# -*- coding: utf-8 -*-
"""V38 headless QA: 33 presets, local style and guarded Qt event simulation."""
from pathlib import Path
import sys
import types
import importlib.util
import ast
ROOT = Path(__file__).resolve().parents[1]
ui = types.ModuleType('ui')
ui.__path__ = [str(ROOT/'ui')]
sys.modules['ui'] = ui
settings = {}
appset = types.ModuleType('ui.app_settings')
appset.ayar_get = lambda key, default=None: settings.get(key) or default
appset.ayar_set = lambda key, value: settings.__setitem__(key, str(value) if value is not None else '')
sys.modules['ui.app_settings'] = appset


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT/rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

theme = load('ui.theme', 'ui/theme.py')
load('ui.theme_tokens_v37', 'ui/theme_tokens_v37.py')
notifications = load('ui.theme_notification_tokens_v38', 'ui/theme_notification_tokens_v38.py')

pairs = [('bg','fg'),('soft','soft_fg'),('field','field_fg'),
         ('selection','selection_fg'),('btn','btn_fg'),('hover','hover_fg'),
         ('focus','focus_fg'),('focus_hover','focus_fg'),
         ('disabled','disabled_fg'),('progress','progress_fg')]
for name in theme.tema_presets():
    theme.tema_apply_preset(name)
    c = notifications.notification_palette()
    for bg, fg in pairs:
        assert theme.contrast_ratio(c[bg], c[fg]) >= 4.5, (name,bg,fg,c[bg],c[fg])
    css = notifications.notification_qss()
    assert css.count('{') == css.count('}'), name
    for piece in ('QMessageBox QLabel','QMessageBox QTextEdit','QMessageBox QPushButton:default',
                  'QMessageBox QPushButton:disabled','QInputDialog QComboBox',
                  'QProgressDialog QProgressBar','QErrorMessage QLabel'):
        assert piece in css, (name,piece)
print('PASS: 33 themes × 10 notification contrast states; QSS selectors')

# Adversarial background/foreground overrides should not be same color.
settings.update({'tema_card':'#111111','tema_bg':'#101010','tema_button_bg':'#ffffff',
                 'tema_button_fg':'#ffffff', 'tema_list_bg':'#151515'})
c = notifications.notification_palette()
for bg,fg in pairs:
    assert theme.contrast_ratio(c[bg],c[fg])>=4.5,(bg,fg,c[bg],c[fg])
print('PASS: custom themes with clashing local color overrides')

for kind in ('info','success','warn','error','unexpected'):
    bg, fg = notifications.toast_colors(kind)
    assert theme.contrast_ratio(bg,fg) >= 4.5, (kind,bg,fg)
for color in ('#ffffff','#000000','#ffff00','#16a34a','#3b82f6'):
    bg,fg = notifications.toast_colors('success',color)
    assert theme.contrast_ratio(bg,fg) >= 4.5, (bg,fg)
print('PASS: status and custom toast foreground/background contrast')

# Mock enough Qt to verify that original dialog behavior is not hijacked.
class QObject:
    def __init__(self, parent=None):self.parent=parent
class Type:
    Show = 1
    Hide = 2
class QEvent:
    Type = Type
class Event:
    def __init__(self, kind):self.kind=kind
    def type(self):return self.kind
class QApplication:
    def __init__(self): self.filters=[];self.windows=[]
    def installEventFilter(self, f):self.filters.append(f)
    def topLevelWidgets(self):return self.windows
class Dialog:
    def __init__(self, stylesheet=''):
        self.css=stylesheet
        self.props={}
        self.current_answer=42
    def styleSheet(self):return self.css
    def setStyleSheet(self, s):self.css=s
    def property(self,k):return self.props.get(k)
    def setProperty(self,k,v):self.props[k]=v
class QMessageBox(Dialog):pass
class QInputDialog(Dialog):pass
class QProgressDialog(Dialog):pass
class QErrorMessage(Dialog):pass
class NotNotification(Dialog):pass
qtcore=types.ModuleType('PyQt6.QtCore');qtcore.QObject=QObject;qtcore.QEvent=QEvent
qtwidgets=types.ModuleType('PyQt6.QtWidgets')
for cls in (QApplication,QMessageBox,QInputDialog,QProgressDialog,QErrorMessage): setattr(qtwidgets,cls.__name__,cls)
qt=types.ModuleType('PyQt6')
sys.modules.update({'PyQt6':qt,'PyQt6.QtCore':qtcore,'PyQt6.QtWidgets':qtwidgets})
runtime=load('ui.theme_popup_runtime_v38','ui/theme_popup_runtime_v38.py')
app=QApplication()
msg=QMessageBox('QMessageBox {border-radius:7px;}')
inputbox=QInputDialog()
progress=QProgressDialog()
error_message=QErrorMessage()
custom=NotNotification('keep')
app.windows.extend([msg,inputbox,progress,error_message,custom])
runtime.install_notification_guard(app)
assert len(app.filters)==1
assert 'border-radius:7px;' in msg.styleSheet()
assert 'QMessageBox QLabel' in msg.styleSheet()
assert not inputbox.property('_v38_original_notification_style')
assert custom.styleSheet()=='keep'
assert msg.current_answer==42
old_count=msg.styleSheet().count('QMessageBox QLabel')
runtime.install_notification_guard(app)
assert len(app.filters)==1
assert msg.styleSheet().count('QMessageBox QLabel')==old_count
assert app.filters[0].eventFilter(QMessageBox(),Event(Type.Show)) is False
assert app.filters[0].eventFilter(msg,Event(Type.Hide)) is False
assert custom.styleSheet()=='keep'
assert 'QErrorMessage QLabel' in error_message.styleSheet()
# Regression: local CSS edited by the owner while open must survive the next refresh.
msg.setStyleSheet('QMessageBox { border-radius:13px; }')
runtime.refresh_open_notifications(app)
assert 'border-radius:13px;' in msg.styleSheet()
assert 'border-radius:7px;' not in msg.styleSheet()
assert msg.styleSheet().count('QMessageBox QLabel') == 1
print('PASS: future/existing boxes; original QSS preserved; one guard; events not consumed')

for file in [p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]:
    if '.git' in file.parts:continue
    ast.parse(file.read_text(encoding='utf-8-sig'),filename=str(file))
print(f'PASS: whole project Python AST')
