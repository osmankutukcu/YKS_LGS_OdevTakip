"""Deterministic V2 contract tests, independent of PyQt6 and student data."""
from __future__ import annotations
import sys
from pathlib import Path
import types
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.homework_context_integrations_v2 import (
    CENTERS, selected_student_id, student_still_current, execute_existing, install_existing_centers
)

class Button:
    def __init__(self, enabled=True):
        self.count = 0
        self.enabled = enabled
    def isEnabled(self): return self.enabled
    def click(self): self.count += 1

class Combo:
    def __init__(self, sid): self.sid=sid
    def currentData(self): return self.sid

class Panel:
    def __init__(self, sid): self._student_id=sid; self._is_open=False; self._dirty=True;self.refresh_count=0;self.topics_count=0
    def refresh(self): self.refresh_count+=1
    def open_topics(self): self.topics_count+=1

class Bridge:
    def __init__(self, sid): self.panel=Panel(sid);self.toggle_count=0;self.selection_count=0
    def toggle(self): self.toggle_count+=1;self.panel._is_open=not self.panel._is_open
    def selection_changed(self): self.selection_count+=1

class Form:
    def __init__(self,sid=14):
        self.sid=sid; self.cmbAd=Combo(sid); self.cmbSoyad=Combo(sid)
        self._workspace_v21=Bridge(sid)
        for c in CENTERS: setattr(self,c.button,Button())
    def _secili_ogrenci_id(self): return self.sid

class Signal:
    def __init__(self):self.callbacks=[]
    def connect(self,cb):self.callbacks.append(cb)
    def fire(self):
        for cb in self.callbacks: cb(False)

class Action:
    def __init__(self,title): self.title=title;self.enabled=True;self.triggered=Signal();self.tip=''
    def setEnabled(self,v):self.enabled=v
    def setToolTip(self,t):self.tip=t

class Menu:
    def __init__(self,title='root'):self.title=title;self.items=[];self.tip=''
    def addMenu(self,title):
        m=Menu(title);self.items.append(m);return m
    def setToolTipsVisible(self,_):pass
    def setToolTip(self,x):self.tip=x
    def addAction(self,title):
        a=Action(title);self.items.append(a);return a
    def addSeparator(self):return self.addAction('---')
    def recursive_actions(self):
        for i in self.items:
            if isinstance(i,Menu):yield from i.recursive_actions()
            else:yield i

@pytest.mark.parametrize('center',CENTERS,ids=lambda c:c.key)
def test_existing_buttons_clicked_only_after_explicit_action(center):
    form=Form()
    assert execute_existing(form,center.key,14)
    assert getattr(form,center.button).count==1
    assert sum(getattr(form,c.button).count for c in CENTERS)==1

@pytest.mark.parametrize('scenario', ['new_student','wrong_surname','missing','missing_combo'])
def test_student_mismatch_prevents_every_shortcut(monkeypatch,scenario):
    import ui.homework_context_integrations_v2 as integration
    monkeypatch.setattr(integration,'_warn',lambda *_:None)
    form=Form()
    if scenario=='new_student':form.sid=77;form.cmbAd.sid=77;form.cmbSoyad.sid=77
    if scenario=='wrong_surname':form.cmbSoyad.sid=88
    if scenario=='missing':form.sid=None
    if scenario=='missing_combo':del form.cmbSoyad
    for center in CENTERS:
        assert not execute_existing(form,center.key,14)
        assert getattr(form,center.button).count == 0
    assert not execute_existing(form,'student360',14)
    assert form._workspace_v21.toggle_count==0


def test_360_opens_once_without_closing_if_already_open():
    form=Form()
    assert execute_existing(form,'student360',14)
    assert form._workspace_v21.toggle_count == 1
    assert execute_existing(form,'student360',14)
    assert form._workspace_v21.toggle_count == 1
    assert form._workspace_v21.panel.refresh_count == 1


def test_topic_evidence_calls_existing_panel_without_set_student_or_write():
    form=Form()
    assert execute_existing(form,'topics',14)
    assert form._workspace_v21.panel.topics_count==1
    assert form._workspace_v21.selection_count==0


def test_missing_buttons_do_not_create_new_module_and_skip_action():
    form=Form(); del form.btnPlan
    assert execute_existing(form,'weekly',14) is False


def test_no_student_disables_all_menu_actions():
    form=Form(sid=None)
    root=Menu()
    install_existing_centers(root,form)
    acts=[a for a in root.recursive_actions() if a.title != '---']
    assert len(acts)==len(CENTERS)+2
    assert not any(a.enabled for a in acts)
    assert sum(getattr(form,c.button).count for c in CENTERS)==0


def test_menu_open_never_clicks_any_existing_button():
    form=Form()
    root=Menu()
    install_existing_centers(root,form)
    assert sum(getattr(form,c.button).count for c in CENTERS)==0
    assert form._workspace_v21.toggle_count==0
    assert form._workspace_v21.panel.topics_count==0
    acts=[a for a in root.recursive_actions() if a.title != '---']
    assert len(acts)==len(CENTERS)+2
    assert all(a.enabled for a in acts)
    next(a for a in acts if 'Haftalık Plan' in a.title).triggered.fire()
    assert form.btnPlan.count==1


def test_menu_capture_student_prevents_switch_before_menu_action(monkeypatch):
    import ui.homework_context_integrations_v2 as integration
    monkeypatch.setattr(integration,'_warn',lambda *_:None)
    form=Form();m=Menu();install_existing_centers(m,form)
    form.sid=15;form.cmbAd.sid=15;form.cmbSoyad.sid=15
    next(a for a in m.recursive_actions() if 'Sihirbaz' in a.title).triggered.fire()
    assert form.btnSihirbaz.count==0


def test_unknown_action_and_disabled_button_no_op():
    form=Form();form.btnSihirbaz.enabled=False
    assert not execute_existing(form,'wizard',14)
    assert not execute_existing(form,'nonexistent',14)
    assert sum(getattr(form,c.button).count for c in CENTERS)==0


def test_ui_core_has_only_one_added_host_argument():
    # This test guards preservation of existing checkbox/color/lock implementation.
    here=Path(__file__).resolve().parents[1]/'ui'/'homework_form.py'
    if not here.is_file():pytest.skip('overlay source not available')
    original=Path('/mnt/data/homework_context_v1_build/ui/homework_form.py')
    if not original.is_file():pytest.skip('reference source not available')
    before=original.read_text(encoding='utf-8')
    after=here.read_text(encoding='utf-8')
    assert after.replace('                    host=self,  # V2: mevcut form modüllerine yazmasız erişim köprüsü\n','')==before


@pytest.mark.parametrize('key', ['wizard','weekly','missing','support'])
def test_stale_loaded_matrix_does_not_dispatch_sensitive_workflow(monkeypatch,key):
    import ui.homework_context_integrations_v2 as integration
    monkeypatch.setattr(integration,'_warn',lambda *_:None)
    form=Form()
    form._loaded_student_id=99
    assert not execute_existing(form,key,14)
    assert sum(getattr(form,c.button).count for c in CENTERS)==0
    # V21 read-only student overlay is still safe with selected id.
    assert execute_existing(form,'student360',14)
