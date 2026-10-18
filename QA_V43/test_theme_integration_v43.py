# -*- coding: utf-8 -*-
"""V43 isolated tokens/cascade and bundle checks, without PyQt or user data."""
from __future__ import annotations
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ui = types.ModuleType('ui')
ui.__path__ = [str(ROOT / 'ui')]
sys.modules['ui'] = ui
settings = {}
appset = types.ModuleType('ui.app_settings')
appset.ayar_get = lambda k, default=None: settings.get(k, default)
appset.ayar_set = lambda k, value: settings.__setitem__(k, value)
sys.modules['ui.app_settings'] = appset


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


theme = load('ui.theme', 'ui/theme.py')
scroll = load('ui.theme_scrollbar_v41', 'ui/theme_scrollbar_v41.py')
tokens = load('ui.theme_tokens_v37', 'ui/theme_tokens_v37.py')
notification = load('ui.theme_notification_tokens_v38', 'ui/theme_notification_tokens_v38.py')
visual = load('ui.theme_visual_tokens_v40', 'ui/theme_visual_tokens_v40.py')
special = load('ui.theme_special_v42', 'ui/theme_special_v42.py')

# Every preset must survive repeated theme changes without changing data-logic modules.
checks = 0
presets = theme.tema_presets()
for name in list(presets) + list(reversed(presets)):
    theme.tema_apply_preset(name)
    style = theme.build_qss()
    colors = tokens.semantic_palette()
    palette = notification.notification_palette()
    assert settings['tema'] == settings['tema_mod']
    for selector in ('QScrollBar::handle:vertical', 'QScrollBar::handle:horizontal',
                     'QMessageBox QLabel', 'QInputDialog', 'QComboBox QAbstractItemView',
                     'QTableWidget', 'QTreeWidget', 'QToolTip', 'QLineEdit', 'QTabBar::tab'):
        assert selector in style, (name, selector)
    assert 'background:None' not in style and 'color:None' not in style
    assert style.count('{') == style.count('}')
    for a,b in [('bg','fg'), ('surface','surface_fg'),('field','field_fg'),
                ('selected','selected_fg'),('btn_bg','btn_fg'),('btn_hover','btn_fg')]:
        assert theme.contrast_ratio(colors[a], colors[b]) >= 4.5, (name,a,b)
        checks+=1
    for a,b in [('bg','fg'), ('field','field_fg'), ('btn','btn_fg'),('selection','selection_fg')]:
        assert theme.contrast_ratio(palette[a],palette[b]) >= 4.5, (name,a,b)
        checks+=1
    generated=scroll.scrollbar_qss(colors['surface'],colors['surface_fg'],colors['primary'],12)
    assert generated.count('{') == generated.count('}')
    assert 'QScrollBar::handle:vertical:pressed' in generated
    checks+=1

# A preset switch must always supersede an accidentally persisted custom override.
settings.update({'tema_card':'#FFFFFF','tema_list_fg':'#FFFFFF','tema_button_fg':'#FFFFFF'})
theme.tema_apply_preset('Klasik Koyu')
assert not settings.get('tema_card')
assert not settings.get('tema_list_fg')
assert not settings.get('tema_button_fg')
print('PASS:',len(presets),'themes × two switching orders;',checks,'palette/notification and scrollbar checks')
print('PASS: notification, table, input, tooltip, scrollbar and menu selectors present')
