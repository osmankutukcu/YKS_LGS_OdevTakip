"""Independent, no-PyQt tests for the safe context menu adapter."""
from __future__ import annotations
import datetime
import os
import sys
import types
from urllib.parse import urlsplit, parse_qs

import pytest
from ui.homework_context_logic_v1 import summarize_topic, official_resource_links, create_study_plan
from ui import homework_context_hub_v1 as hub


def test_topic_summary_does_not_assume_color_means_state():
    summary = summarize_topic('Parabol', 'AYT Matematik', [
        ('AYT MAT1', True, False), ('AYT MAT2', True, True), ('AYT MAT3', False, True)
    ])
    assert (summary.locked, summary.checked, summary.empty) == (1, 1, 1)
    assert len(summary.cells) == 3


def test_external_links_official_and_topic_search_no_student_data():
    links = official_resource_links('AYT Matematik', 'Parabol')
    assert len(links) == 4
    for _, url, _ in links:
        parsed = urlsplit(url)
        assert parsed.scheme == 'https'
        assert parsed.hostname in ('mebi.eba.gov.tr','ogmmateryal.eba.gov.tr',
                                   'www.osym.gov.tr','www.google.com')
        assert 'student' not in url.lower() and 'ogrenci' not in url.lower()
    assert 'AYT Matematik' in parse_qs(urlsplit(links[-1][1]).query)['q'][0]


def test_empty_topic_only_official_portals():
    assert len(official_resource_links('Fizik', '')) == 3


def test_study_preview_pure_and_date_accurate():
    tasks = [('Parabol','MAT2'),('Limit','MAT3'),('Türev','MAT3')]
    before = tasks[:]
    txt = create_study_plan(tasks,2,datetime.date(2026,10,15))
    assert '15.10.2026 Perşembe' in txt
    assert '16.10.2026 Cuma' in txt
    assert txt.count('☐') == 3
    assert tasks == before
    with pytest.raises(ValueError):
        create_study_plan(tasks,0,datetime.date.today())


class Trigger:
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)
    def fire(self):
        for cb in self.callbacks: cb(False)


class FakeAction:
    def __init__(self,text):
        self.text = text
        self.enabled = True
        self.tip = None
        self.triggered = Trigger()
    def setEnabled(self,val): self.enabled=val
    def setToolTip(self,tip): self.tip=tip


class FakeMenu:
    def __init__(self,*args):
        self.name = args[0] if args else 'root'
        self._acts=[]
        self.submenus=[]
    def actions(self): return list(self._acts)
    def addAction(self,item):
        if isinstance(item, str): item=FakeAction(item)
        self._acts.append(item)
        return item
    def removeAction(self,a): self._acts.remove(a)
    def addSeparator(self): return self.addAction(FakeAction('---'))
    def addMenu(self,title):
        child=FakeMenu(title)
        self.submenus.append(child)
        self._acts.append(child)
        return child
    def setToolTipsVisible(self,*_): pass
    def setToolTip(self,*_): pass
    def clear(self): self._acts.clear(); self.submenus.clear()


class FakeSettings:
    setting=False
    def __init__(self,*_): pass
    def value(self,*_args,**_kwargs): return self.setting
    def setValue(self,_k,v): FakeSettings.setting=v


class FakeIndex:
    def isValid(self): return True
    def row(self): return 0
    def column(self): return 1


class FakeItem:
    def __init__(self,txt): self.txt=txt
    def text(self): return self.txt


class FakeTable:
    def __init__(self): self.mutation_calls=0
    def item(self,r,c): return FakeItem('Parabol') if c==0 else None
    def horizontalHeaderItem(self,c): return FakeItem('AYT MAT3')
    def setData(self,*args): self.mutation_calls+=1
    def setCheckState(self,*args): self.mutation_calls+=1


def setup_fake_qt(monkeypatch):
    pkg=types.ModuleType('PyQt6')
    for name,attrs in {'QtWidgets': {'QMenu': FakeMenu},
                       'QtGui':{'QAction':FakeAction},
                       'QtCore':{'QSettings':FakeSettings}}.items():
        mod=types.ModuleType('PyQt6.'+name)
        for k,v in attrs.items(): setattr(mod,k,v)
        monkeypatch.setitem(sys.modules,'PyQt6.'+name,mod)
    monkeypatch.setitem(sys.modules,'PyQt6',pkg)
    FakeSettings.setting=False


def walk_actions(menu):
    for x in menu.actions():
        if isinstance(x,FakeMenu): yield from walk_actions(x)
        else: yield x


def setup_commands():
    names=('toggle','row_give','row_clear','col_give','col_clear','col_clean',
           'book_status','lesson_analyze','gap_analyze','smart_analyze',
           'yt','gg','review','plan','parent_report')
    actions={k: FakeAction(k) for k in names}
    menu=FakeMenu()
    for a in actions.values(): menu.addAction(a)
    return menu,actions


def test_menu_preserves_all_15_connected_legacy_actions(monkeypatch):
    setup_fake_qt(monkeypatch)
    menu,commands=setup_commands()
    original_callbacks=[]
    for a in commands.values():
        a.triggered.connect(lambda checked=False: original_callbacks.append('triggered'))
    table=FakeTable()
    assert hub.install_hub(menu,table,FakeIndex(),'AYT Matematik',commands)
    flattened=list(walk_actions(menu))
    for name,action in commands.items():
        assert flattened.count(action)==1, name
        action.triggered.fire()
    assert len(original_callbacks)==15
    assert table.mutation_calls==0
    assert any(sub.name.startswith('🌐') for sub in menu.submenus)
    assert any('Planı Önizle' in a.text for a in flattened)


def test_menu_expert_restores_full_flat_action_list(monkeypatch):
    setup_fake_qt(monkeypatch)
    menu,commands=setup_commands()
    FakeSettings.setting=True
    assert hub.install_hub(menu,FakeTable(),FakeIndex(),'Fizik',commands)
    assert list(menu.actions())[:15] == list(commands.values())


def test_fallback_when_module_disabled(monkeypatch):
    setup_fake_qt(monkeypatch)
    menu,commands=setup_commands()
    before=menu.actions()
    monkeypatch.setenv('ODEV_CONTEXT_MENU_LEGACY','1')
    assert hub.install_hub(menu,FakeTable(),FakeIndex(),'Fizik',commands) is False
    assert menu.actions()==before
    monkeypatch.delenv('ODEV_CONTEXT_MENU_LEGACY')


def test_missing_legacy_action_keeps_original_menu(monkeypatch):
    setup_fake_qt(monkeypatch)
    menu,commands=setup_commands()
    before=menu.actions()
    del commands['plan']
    assert not hub.install_hub(menu,FakeTable(),FakeIndex(),'Fizik',commands)
    assert menu.actions()==before


def test_sources_do_not_open_until_explicit_click(monkeypatch):
    setup_fake_qt(monkeypatch)
    calls=[]
    monkeypatch.setattr(hub.webbrowser, 'open', lambda url: calls.append(url))
    menu,commands=setup_commands()
    assert hub.install_hub(menu, FakeTable(), FakeIndex(), 'AYT Matematik', commands)
    assert calls == []
    resource_menu=next(sub for sub in menu.submenus if sub.name.startswith('🌐'))
    next(a for a in resource_menu.actions()
         if isinstance(a, FakeAction) and 'OGM Materyal - resmi' in a.text).triggered.fire()
    assert calls == ['https://ogmmateryal.eba.gov.tr/']


def test_expert_mode_is_persisted_separately_from_database(monkeypatch):
    setup_fake_qt(monkeypatch)
    menu,commands=setup_commands()
    assert hub.install_hub(menu, FakeTable(), FakeIndex(), 'AYT Matematik', commands)
    action=next(a for a in menu.actions()
                if isinstance(a, FakeAction) and 'Tüm işlemleri göster' in a.text)
    assert FakeSettings.setting is False
    action.triggered.fire()
    assert FakeSettings.setting is True


def test_topic_snapshot_uses_existing_lock_checker(monkeypatch):
    setup_fake_qt(monkeypatch)
    core=sys.modules['PyQt6.QtCore']
    class DummyCheckState:
        Checked=2
    class DummyItemFlag:
        ItemIsUserCheckable=1
    core.Qt=types.SimpleNamespace(CheckState=DummyCheckState, ItemFlag=DummyItemFlag)
    class Item:
        def __init__(self,value): self.value=value
        def checkState(self): return self.value
        def flags(self): return 1
    class Model:
        def index(self,r,c):return (r,c)
    class Table(FakeTable):
        def columnCount(self):return 4
        def model(self):return Model()
        def item(self,r,c):return FakeItem('Parabol') if c==0 else Item(2)
    table=Table()
    seen=[]
    def existing_lock_policy(index):
        seen.append(index)
        return index[1] in (1,3)
    summary=hub._topic_snapshot(table,FakeIndex(),'AYT Matematik',existing_lock_policy)
    assert (summary.locked,summary.checked,summary.empty)==(2,1,0)
    assert seen==[(0,1),(0,2),(0,3)]
