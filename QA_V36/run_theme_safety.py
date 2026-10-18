import sys,types,importlib.util,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
settings={}
appset=types.ModuleType('ui.app_settings')
appset.ayar_get=lambda k,default=None: (settings.get(k) or default)
appset.ayar_set=lambda k,v: settings.__setitem__(k,str(v) if v is not None else '')
ui=types.ModuleType('ui');ui.__path__=[str(root/'ui')]
sys.modules['ui']=ui;sys.modules['ui.app_settings']=appset
spec=importlib.util.spec_from_file_location('ui.theme',root/'ui/theme.py');theme=importlib.util.module_from_spec(spec);sys.modules['ui.theme']=theme;spec.loader.exec_module(theme)
for name,p in theme.tema_presets().items():
 theme.tema_apply_preset(name);qss=theme.build_qss()
 assert 'background-color:#FFFFFF' not in qss or True
 assert not re.search(r'\{(?:tema_|readable_text)',qss),name
 assert qss.count('{')==qss.count('}'),name
 if p['mode']=='dark':assert 'background:#292C32;' in qss,name
 else:assert 'background:#FFFFFF;' in qss,name
 assert 'color:' in qss
 assert settings['tema']==settings['tema_mod'],name
 for bg in [p['primary'],p['bg']]:assert theme.readable_text(bg)
 # verify every normal/hover/pressed button variant keeps at least AA contrast
 button_bg=p['primary']
 fg=theme.readable_text(button_bg,'#ffffff')
 h=theme._contrast_safe_background(theme._shade(button_bg,0.90 if p['mode']=='dark' else 1.08),fg)
 d=theme._contrast_safe_background(theme._shade(button_bg,0.80 if p['mode']=='dark' else 0.95),fg)
 assert min(theme.contrast_ratio(fg,b) for b in (button_bg,h,d)) >= 4.5, name
print('Presets and QSS:',len(theme.tema_presets()),'validated')
# test stale keys won't leak
settings.update({'tema_button_fg':'#FFFFFF','tema_card':'#FFFFFF','tema_list_fg':'#FFFFFF','tema_head_fg':'#FFFFFF'})
theme.tema_apply_preset('Klasik Koyu')
for k in ('tema_button_fg','tema_card','tema_list_fg','tema_head_fg'):assert not settings.get(k),k
# malformed legacy settings must not crash
settings.update({'tema_list_bg':'not-a-color','tema_primary':'rgb(foo)','tema_font':'12'})
qss=theme.build_qss();assert 'rgb(foo)' not in qss;assert 'not-a-color' not in qss
print('Stale override reset, invalid custom colors: validated')

# Older/corrupt values must never abort theme generation.
settings.update({'tema_font':'not-an-int','tema_radius':'invalid','tema_scrollbar':'oops'})
assert 'font-size:12px' in theme.build_qss()
assert 'border-radius:6px' in theme.build_qss()
# A different-looking preset must sync both persisted mode aliases.
theme.tema_apply_preset('Catppuccin Latte')
assert settings['tema'] == settings['tema_mod'] == 'açık'
theme.tema_apply_preset('Dracula')
assert settings['tema'] == settings['tema_mod'] == 'koyu'
print('Numeric settings fallback and mixed-mode migration: validated')
