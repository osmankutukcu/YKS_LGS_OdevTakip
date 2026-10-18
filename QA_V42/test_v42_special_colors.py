"""V42 theme-specific, headless checks. Does not modify user settings or open Qt."""
from pathlib import Path
import ast
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
settings = {}
ui = types.ModuleType('ui')
ui.__path__ = [str(ROOT / 'ui')]
sys.modules['ui'] = ui
appset = types.ModuleType('ui.app_settings')
appset.ayar_get = lambda k, default=None: settings.get(k) or default
appset.ayar_set = lambda k, v: settings.__setitem__(k, v)
sys.modules['ui.app_settings'] = appset


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


t = load('ui.theme', 'ui/theme.py')
load('ui.theme_scrollbar_v41', 'ui/theme_scrollbar_v41.py')
load('ui.theme_tokens_v37', 'ui/theme_tokens_v37.py')
sp = load('ui.theme_special_v42', 'ui/theme_special_v42.py')

checks=0
for name in t.tema_presets():
    t.tema_apply_preset(name)
    tc=sp.timeline_colors()
    for bg, fg in [('surface','text'),('surface','muted'),('surface','capacity')]:
        assert t.contrast_ratio(tc[bg],tc[fg])>=4.5-1e-8, (name,bg,fg,tc)
        checks+=1
    for first,last,fg in [('school_start','school_end','school_text'),
                          ('course_start','course_end','course_text')]:
        for bg in (first,last):
            assert t.contrast_ratio(tc[bg],tc[fg])>=4.5-1e-8, (name,bg,fg,tc)
            checks+=1
    for pct in (0,5,25,40,50,60,75,90,100):
        bar=sp.table_bar_colors(pct)
        for bg in ('base','fill'):
            assert t.contrast_ratio(bar[bg],bar['text'])>=4.5-1e-8,(name,pct,bg,bar)
            checks+=1
    trend=sp.trend_colors()
    assert t.contrast_ratio(trend['surface'],trend['text'])>=4.5,(name,trend)
    checks+=1
print('PASS:',checks,'timeline, bar and trend text contrast checks in',len(t.tema_presets()),'presets')

for bg,fg in [('#FFFFFF','#FFFFFF'),('#000000','#000000'),('#737373','#737373')]:
    adjusted=sp.legible_accent(bg,fg)
    assert t.contrast_ratio(bg,adjusted)>=4.5,(bg,fg,adjusted)

# Explicit regressions for the source of the actual invisible-text problems.
painter=(ROOT/'ui/performans_paneli.py').read_text(encoding='utf8')
timeline=(ROOT/'ui/plan_settings_dialog.py').read_text(encoding='utf8')
mini=(ROOT/'ui/odev_kontrol.py').read_text(encoding='utf8')
update=(ROOT/'ui/update_dialog.py').read_text(encoding='utf8')
guide=(ROOT/'ui/homework_guide_dialog.py').read_text(encoding='utf8')
for src, fragment in [(painter,'table_bar_colors(pct)'),(painter,'trend_colors()'),
                      (timeline,'register_theme_listener(self)'),(timeline,'tc = timeline_colors()'),
                      (mini,"p.fillRect(r, QColor(c['surface']))"),
                      (update,'register_theme_listener(self)'),
                      (guide,'register_theme_listener(self)')]:
    assert fragment in src, fragment
assert '                color: #15191E;}' not in update
assert 'self._theme_labels' in update
assert 'self.btnUpdate.clicked.connect(self._start_update)' in update
assert 'btn_close.clicked.connect(self.accept)' in guide
assert 'def _on_theme_changed(self)' in timeline
assert 'def _on_theme_changed(self)' in guide

# Syntax pass is not a simulated GUI test.
all_modules=[p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]
for file in all_modules:
    ast.parse(file.read_text(encoding='utf-8-sig'),filename=str(file))
print('PASS:',len(all_modules),'Python files parse; event callbacks kept unchanged')
print('IMPORTANT: Windows/macOS live PyQt6 testing is still required')
