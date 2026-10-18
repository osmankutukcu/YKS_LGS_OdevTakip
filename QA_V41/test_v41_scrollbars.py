"""V41 headless palette and QSS tests. Does not open real student/application settings."""
import ast
import importlib.util
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ui = types.ModuleType('ui')
ui.__path__ = [str(ROOT / 'ui')]
sys.modules['ui'] = ui
settings = {}
a = types.ModuleType('ui.app_settings')
a.ayar_get = lambda k, default=None: settings.get(k) or default
a.ayar_set = lambda k, v: settings.__setitem__(k, v)
sys.modules['ui.app_settings'] = a

def load(modname, file):
    spec=importlib.util.spec_from_file_location(modname,ROOT/file)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[modname]=mod
    spec.loader.exec_module(mod)
    return mod

t=load('ui.theme', 'ui/theme.py')
sb=load('ui.theme_scrollbar_v41', 'ui/theme_scrollbar_v41.py')
palette=load('ui.theme_tokens_v37', 'ui/theme_tokens_v37.py')

# Each theme must produce visible normal/hover/dragging/disabled thumbs
# in the context of its own light/dark surface and both orientations.
count=0
for preset in t.tema_presets():
    t.tema_apply_preset(preset)
    c = palette.semantic_palette()
    surface=t._mix(c['surface'], c['bg'], .65)
    colors=sb.scrollbar_palette(surface,c['surface_fg'],c['primary'])
    for state in ('normal','hovered','pressed','disabled'):
        ratio=t.contrast_ratio(surface,colors[state])
        assert ratio >= 3.0 - 1e-8, (preset,state,ratio)
        count+=1
    assert colors['track']==surface
    for requested_size in (6,7,8,9,12,16,24,0,99,'invalid'):
        css=sb.scrollbar_qss(surface,c['surface_fg'],c['primary'],requested_size)
        size=12 if requested_size=='invalid' else max(6,min(24,int(requested_size)))
        assert f'width:{size}px' in css and f'height:{size}px' in css
        assert 'min-height:32px' in css and 'min-width:32px' in css
        assert 'background-clip' not in css and 'border:none;' in css
        assert css.count('{')==css.count('}')
        for expected in ('QScrollBar::handle:vertical:hover','QScrollBar::handle:horizontal:pressed',
                         'QScrollBar::handle:vertical:disabled','QScrollBar::add-page:horizontal'):
            assert expected in css,(preset,expected)
        assert all(sub in css for sub in ['::handle:vertical','::handle:horizontal'])
        appcss=t.build_qss()
        assert '/* V41: opaque, contrast-checked themed scrollbars' in appcss
        assert 'background-clip: content-box' not in appcss
        assert 'background:{' not in appcss
        assert appcss.count('{')==appcss.count('}')
    rootcss=palette.homework_root_qss()
    assert '/* V41: opaque, contrast-checked themed scrollbars' in rootcss
    assert rootcss.count('{')==rootcss.count('}')

# Adversarial colour combinations, including a custom near-mid-grey surface.
for track,fg,accent in [('#FFFFFF','#FFFFFF','#FFFFFF'),('#000000','#000000','#000000'),
                        ('#777777','#777777','#777777'),('#808080','#808080','#808080'),
                        ('#efefef','#ffffff','#eaeaea'),('#222428','#222428','#161616'),
                        ('#CCFFEE','#00ffee','#CCFFEE')]:
    vals=sb.scrollbar_palette(track,fg,accent)
    for state in ('normal','hovered','pressed','disabled'):
        assert t.contrast_ratio(track, vals[state])>=3.0, (track,state,vals[state])
print('PASS:',len(t.tema_presets()),'themes × 4 visible thumb states:',count, 'plus adversarial colours')

q=t.build_qss()
assert "_mix(primary, input_bg, 0.12)" in (ROOT/'ui/theme.py').read_text(encoding='utf-8')
for file in ['ui/homework_form.py','ui/mail_send_whatsapp.py','ui/info_board_widget.py','ui/topic_map_dialog.py']:
    assert 'scrollbar_qss(' in (ROOT/file).read_text(encoding='utf-8'),file
assert 'style += scrollbar_qss' in (ROOT/'ui/mail_send_whatsapp.py').read_text(encoding='utf-8')
print('PASS: global palette, themed homework and three specially-styled scrollbar contexts')

# Whole project parse: evidence of syntax integrity, NOT live Qt acceptance.
files=[p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]
for f in files:
    ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
print('PASS:',len(files),'Python modules parse successfully; PyQt runtime GUI test remains open')
