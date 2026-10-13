# -*- coding: utf-8 -*-
"""Hedef analizi: Qt gerektirmeyen, veri kaybı riskine odaklı testler."""
from pathlib import Path
import ast
import pytest
from services.target_analysis_v24.logic import (
    TargetDataError, validated_net, extract_known_exam_nets, target_data_source_label
)

@pytest.mark.parametrize('input_value,max_net', [('120',120),('80',80),('90',90),('15,75',120),('-1',80)])
def test_nets_accepted(input_value,max_net):
    assert validated_net(input_value,max_net,'test') == float(input_value.replace(',','.'))

@pytest.mark.parametrize('input_value,max_net', [('',120),('121',120),('81',80),('91',90),('nan',120),('inf',120),('-31',120),('-23',90),('abc',80)])
def test_nets_rejected(input_value,max_net):
    with pytest.raises(TargetDataError): validated_net(input_value,max_net,'test')

def test_single_tyt_exam_may_include_unlabelled_subjects():
    r=extract_known_exam_nets([('Türkçe',21),('Matematik',19)], 'TYT', 'YKS-SAY')
    assert r == {'TYT': 40.0}

def test_mixed_labeled_exam_keeps_distinct_papers():
    r=extract_known_exam_nets([('TYT Türkçe',25),('AYT Matematik',30)], 'YKS', 'YKS-SAY')
    assert r == {'TYT':25.0,'AYT':30.0}

def test_undifferentiated_yks_exam_fails_closed():
    with pytest.raises(TargetDataError,match='tahmin edilmeyecek'):
        extract_known_exam_nets([('Matematik',60)], 'YKS', 'YKS-SAY')

def test_mixed_type_exam_with_unlabelled_lesson_fails_closed():
    with pytest.raises(TargetDataError,match='tahmin edilmeyecek'):
        extract_known_exam_nets([('Matematik',30)], 'TYT-AYT', 'YKS-SAY')

def test_unknown_student_exam_mismatch():
    with pytest.raises(TargetDataError,match='uyumsuz'):
        extract_known_exam_nets([('Türkçe',20)], 'LGS', 'YKS-SAY')

def test_lgs():
    assert extract_known_exam_nets([('Matematik',12),('Fen Bilimleri',13)], 'LGS', 'LGS') == {'LGS':25.0}

def test_ydt_not_counted_as_ayt():
    with pytest.raises(TargetDataError):
        extract_known_exam_nets([('YDT İngilizce',55)], 'YDT','YKS-SAY')
    assert extract_known_exam_nets([('YDT İngilizce',55)], 'YDT','YKS-DIL') == {'YDT':55.0}

def test_source_is_not_claimed_official():
    for year in (2024,2025,2026):
        assert 'doğrulanmadı' in target_data_source_label(year)

def test_source_ui_does_not_write_in_analysis_method():
    p=Path(__file__).parents[1]/'ui'/'target_analysis_dialog.py'
    source=p.read_text(encoding='utf-8')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TargetAnalysisDialog')
    analyze=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_analyze')
    analyze_source=ast.get_source_segment(source,analyze)
    assert 'UPDATE ogrenci' not in analyze_source
    assert '_last_analysis' in analyze_source
    save=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_save_analyzed_target')
    assert 'UPDATE ogrenci' in ast.get_source_segment(source,save)


def test_no_manufactured_rank_estimate():
    p=Path(__file__).parents[1]/'ui'/'target_analysis_dialog.py'
    s=p.read_text(encoding='utf-8')
    assert 'rank_taban * 2.2' not in s
    assert 'tot * 0.6' not in s
    assert 'rank_taban * 0.9' not in s


def test_panel_is_student_scoped():
    p=Path(__file__).parents[1]/'ui'/'advanced_analytics.py'
    text=p.read_text(encoding='utf-8')
    assert 'self.student_store.add(self.student_id,' in text
    assert 'self.student_store.list_last(self.student_id,' in text
    assert 'self.store.add(date_, exam_type, alan, payload)' not in text


def test_no_unverified_official_claim_in_year_selector():
    p=Path(__file__).parents[1]/'ui'/'advanced_analytics.py'
    text=p.read_text(encoding='utf-8')
    assert '2024 ÖSYM/MEB Resmi' not in text
    assert '2025 Güncel Yerleştirme' not in text
