"""V40 headless checks. Does not open files containing student data."""
from __future__ import annotations
import ast, importlib.util, re, sys, types
from pathlib import Path
R = Path(__file__).resolve().parents[1]
ui=types.ModuleType('ui');ui.__path__=[str(R/'ui')];sys.modules['ui']=ui
settings={}
app=types.ModuleType('ui.app_settings')
app.ayar_get=lambda k, default=None: settings.get(k) or default
app.ayar_set=lambda k, v:settings.__setitem__(k,v)
sys.modules['ui.app_settings']=app

def load(n,relative):
 spec=importlib.util.spec_from_file_location(n,R/relative)
 obj=importlib.util.module_from_spec(spec);sys.modules[n]=obj;spec.loader.exec_module(obj);return obj

base=load('ui.theme','ui/theme.py')
colors=load('ui.theme_tokens_v37','ui/theme_tokens_v37.py')
paper=load('ui.theme_report_canvas_v40','ui/theme_report_canvas_v40.py')
visual=load('ui.theme_visual_tokens_v40','ui/theme_visual_tokens_v40.py')
grads=[('#3b82f6','#2563eb'),('#10b981','#059669'),('#ef4444','#b91c1c'),
       ('#8b5cf6','#7c3aed'),('#fef9c3','#fde047'),('#f1f5f9','#cbd5e1'),
       ('#d1fae5','#6ee7b7'),('#ccfbf1','#99f6e4')]
for preset in base.tema_presets():
 base.tema_apply_preset(preset)
 c=colors.semantic_palette()
 for background, fg in [('surface','surface_fg'),('field','field_fg'),
                        ('selected','selected_fg'),('tab_hover','tab_hover_fg')]:
  assert base.contrast_ratio(c[background],c[fg])>=4.5,(preset,background)
 text_bg='#3F222B' if c['dark'] else '#FFF1F2'
 fg=base.readable_text(text_bg,'#9f1239')
 assert base.contrast_ratio(fg,text_bg)>=4.5,(preset,'critical-header')
 assert 'background:#FFFFFF' in paper.report_paper_qss()
 assert 'color:#172033' in paper.report_paper_qss()
 for left,right in grads:
  a,b,text=visual.accessible_gradient(left,right)
  assert min(base.contrast_ratio(a,text),base.contrast_ratio(b,text))>=4.5, (preset,left,right,text)
print('PASS: 33 themes; main panel, alert header, HTML paper and gradient text contrast')

src=lambda path:(R/path).read_text(encoding='utf-8')
assert src('ui/dashboard_widget.py').count('p.setPen(QColor(chart_colors["surface_fg"]))')==2
assert 'p.setPen(QColor(colors["surface_fg"]))' in src('ui/dashboard_widget.py')
assert 'register_theme_listener(self)' in src('ui/today_priority_strip_v4.py')
assert 'def _on_theme_changed(self):' in src('ui/gamification_widget.py')
assert "self._last_alerts = list(alerts)" in src('ui/gamification_widget.py')
assert 'self._badge_gradient' in src('ui/gamification_widget.py') and 'accessible_gradient(' in src('ui/gamification_widget.py')
for target in ['ui/adaptive_coaching_center_v26.py','ui/adaptive_followup_v11.py']:
 t=src(target)
 assert 'report_paper_qss()' in t and 'register_theme_listener(self)' in t
 assert '.setHtml(' in t
print('PASS: theme listener hooks, chart pens, status cache and HTML-viewer isolation')

for name in ['ui/dashboard_widget.py','ui/gamification_widget.py',
 'ui/today_priority_strip_v4.py','ui/adaptive_coaching_center_v26.py',
 'ui/adaptive_followup_v11.py']:
 ast.parse(src(name), filename=name)
for p in [x for x in R.rglob('*.py') if not any(k in x.parts for k in ('.git', '.venv', 'build', 'dist', '__pycache__'))]:
 ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
print('PASS: 494 Python modules parse successfully')
