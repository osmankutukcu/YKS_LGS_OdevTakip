# -*- coding: utf-8 -*-
"""V24 kaynak doğruluğu, öğrenciye özgü sınav trendi ve eski verinin korunması."""
import datetime as dt
import sqlite3
from pathlib import Path
import pytest

from services.target_analysis_v24.official_sources import (
    official_source, safe_official_url, is_allowlisted_url, connectivity_description
)
from services.target_analysis_v24.logic import validated_net, extract_known_exam_nets, TargetDataError
from services.target_analysis_v24.student_history import StudentTrendStore


def test_zero_is_a_valid_known_net():
    assert validated_net(0, 80, 'AYT') == 0
    assert validated_net('0', 120, 'TYT') == 0


def test_composite_course_label_is_never_mistaken_as_tyt():
    with pytest.raises(TargetDataError, match='tahmin edilmeyecek'):
        extract_known_exam_nets([('TYT-AYT Matematik', 35)], 'TYT', 'YKS-SAY')


@pytest.mark.parametrize('exam,host', [('YKS-SAY','yokatlas.yok.gov.tr'),
                                      ('YKS-DİL','yokatlas.yok.gov.tr'),
                                      ('LGS','www.meb.gov.tr')])
def test_no_student_information_in_official_url(exam,host):
    from urllib.parse import urlsplit
    source,url = official_source(exam)
    assert source
    assert urlsplit(url).netloc == host
    assert urlsplit(url).query == ''
    assert is_allowlisted_url(url)
    assert safe_official_url(exam) == url


def test_arbitrary_url_is_not_allowlisted():
    assert not is_allowlisted_url('https://yokatlas.yok.gov.tr.evil.example/abc')
    assert not is_allowlisted_url('http://yokatlas.yok.gov.tr/netler-tablo.php')
    assert not is_allowlisted_url('https://yokatlas.yok.gov.tr/netler-tablo.php?student=1')


def test_connectivity_is_not_data_validation():
    assert 'otomatik doğrulanmadı' in connectivity_description(200)
    assert 'doğrulanamadı' in connectivity_description(403)
    assert 'kontrol edilemedi' in connectivity_description(None, 'timeout')


def test_source_sync_updates_changed_exam_without_duplicate_or_legacy_write(tmp_path):
    path = tmp_path/'deneme_history.db'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE deneme (id INTEGER PRIMARY KEY, d TEXT, exam TEXT, alan TEXT, payload TEXT)')
        con.execute("INSERT INTO deneme VALUES (1,'2026-10-10','YKS','SAY','{}')")
    store=StudentTrendStore(str(path))
    d=dt.date(2026,10,10)
    p={'tyt_total':45,'ayt_total':25}
    assert store.sync_source(1,d,'YKS','SAY',p,'deneme:99:SAY')=='inserted'
    assert store.sync_source(1,d,'YKS','SAY',p,'deneme:99:SAY')=='unchanged'
    p2={'tyt_total':46,'ayt_total':25}
    assert store.sync_source(1,d,'YKS','SAY',p2,'deneme:99:SAY')=='updated'
    assert len(store.list_last(1,'YKS','SAY'))==1
    assert store.list_last(1,'YKS','SAY')[0][1]['tyt_total']==46
    with sqlite3.connect(path) as con:
        assert con.execute('SELECT COUNT(*) FROM deneme').fetchone()[0]==1


def test_updates_are_student_specific_and_manual_records_stable(tmp_path):
    store=StudentTrendStore(str(tmp_path/'db.sqlite'))
    d=dt.date(2026,10,11)
    store.add(1,d,'YKS','EA',{'tyt_total':11})
    store.add(2,d,'YKS','EA',{'tyt_total':22},'deneme:10:EA')
    store.sync_source(1,d,'YKS','EA',{'tyt_total':33},'deneme:10:EA')
    store.sync_source(2,d,'YKS','EA',{'tyt_total':44},'deneme:10:EA')
    assert [x[1]['tyt_total'] for x in store.list_last(1,'YKS','EA')] == [11,33]
    assert [x[1]['tyt_total'] for x in store.list_last(2,'YKS','EA')] == [44]


def test_auto_sync_skips_partials_before_combined_trend():
    ui=(Path(__file__).parents[1]/'ui'/'advanced_analytics.py').read_text(encoding='utf-8')
    assert "if 'TYT' not in parsed or second not in parsed:" in ui
    assert 'self.student_store.sync_source(' in ui


def test_ui_online_probe_does_not_upload_student_fields():
    ui=(Path(__file__).parents[1]/'ui'/'target_analysis_dialog.py').read_text(encoding='utf-8')
    assert 'QNetworkAccessManager' in ui
    assert 'self._official_manager.head(request)' in ui
    assert 'safe_official_url(exam)' in ui
    assert 'student_id' not in ui[ui.index('    def _check_official_connection('):ui.index('    def _analysis_signature(')]
