# -*- coding: utf-8 -*-
"""Headless presentation-safety tests; no Qt, database, or network needed."""
import sys,types,importlib.util,ast,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
settings={}
appset=types.ModuleType('ui.app_settings')
appset.ayar_get=lambda key,default=None: (settings.get(key) or default)
appset.ayar_set=lambda key,value: settings.__setitem__(key,str(value) if value is not None else '')
ui=types.ModuleType('ui');ui.__path__=[str(ROOT/'ui')]
sys.modules['ui']=ui;sys.modules['ui.app_settings']=appset

def load(name,rel):
 spec=importlib.util.spec_from_file_location(name,ROOT/rel)
 mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
 return mod

theme=load('ui.theme','ui/theme.py')
tokens=load('ui.theme_tokens_v37','ui/theme_tokens_v37.py')

# Every token for every active preset is legible on its associated surface.
key_pairs=[('bg','fg'),('surface','surface_fg'),('alt','alt_fg'),('field','field_fg'),
           ('neutral','neutral_fg'),('tab_hover','tab_hover_fg'),
           ('selected','selected_fg'),('btn_bg','btn_fg'),('btn_hover','btn_fg'),
           ('danger_bg','danger_fg'),('danger_hover','danger_hover_fg'),
           ('success_bg','success_fg'),('success_hover','success_hover_fg'),
           ('info_bg','info_fg'),('info_hover','info_hover_fg')]
for name in theme.tema_presets():
 theme.tema_apply_preset(name)
 c=tokens.semantic_palette()
 for bg,fg in key_pairs:
  ratio=theme.contrast_ratio(c[bg],c[fg])
  assert ratio>=4.5,(name,bg,fg,ratio,c[bg],c[fg])
 assert theme.contrast_ratio(c['selected'],c['selected_fg'])>=4.5
 qss=tokens.homework_root_qss()
 assert qss.count('{')==qss.count('}'),name
 for selector in ('QLineEdit','QTableWidget','QComboBox','QPushButton#btnDanger',
                  'QTabBar::tab','QHeaderView::section','QMenu','QToolTip'):
  assert selector in qss,(name,selector)
 assert 'color:None' not in qss and 'background:None' not in qss
print('PASS: 33 palettes × 16 semantic roles and home-work form QSS')

# Disabled + selected/hover state coverage in the application-wide style.
qss=theme.build_qss()
for sel in ('QPushButton:disabled','QTableWidget::item:hover','QListWidget',
            'QTreeWidget','QTextBrowser','QComboBox QAbstractItemView'):
 assert sel in qss,sel

class FakeApp:
 def setStyleSheet(self,s):self.current=s
class Listener:
 def __init__(self):self.n=0
 def _on_theme_changed(self):self.n+=1
app=FakeApp(); listener=Listener()
theme.register_theme_listener(listener)
theme.apply(app)
assert listener.n==1 and app.current==theme.build_qss()
print('PASS: active windows are notified on live theme switch, no business operations')

# Custom arbitrary contrast overrides should never yield identical text/background.
settings.update({'tema_bg':'#101010','tema_card':'#0b0b0b',
                 'tema_button_bg':'#141414','tema_button_fg':'#141414'})
c=tokens.semantic_palette()
assert theme.contrast_ratio(c['bg'],c['fg'])>=4.5
assert theme.contrast_ratio(c['btn_bg'],c['btn_fg'])>=4.5
print('PASS: dark-on-dark adversarial custom palette')

sources=[p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]
for p in sources:
 ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
print(f'PASS: AST for {len(sources)} Python files')
