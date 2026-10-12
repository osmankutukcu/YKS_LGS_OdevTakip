"""V20 karne adapter – source text only, never modifies DB or course settings."""
from pathlib import Path
import sqlite3
import csv
import pytest

from services.question_evidence_v19 import parse_analysis_file, ReportFormatError, prepare, apply
from tests.test_v19_question_topic_evidence import db


def file(tmp_path, name, contents):
    p=tmp_path/name
    p.write_text(contents,encoding='utf-8-sig')
    return p


def test_csv_publisher_headers_without_identity(tmp_path):
    path=file(tmp_path,'karne.csv','Ders Adı;Soru No;Cevap Durumu;Konu Adı;Kazanım Kodu\nFizik;3;Yanlış;Elektrostatik;FIZ.9\n')
    d=parse_analysis_file(path, student_id=1,exam_id=9)
    assert len(d.rows)==1 and d.rows[0]['ogrenci_id']=='1'
    assert not d.student_id_in_source
    assert any('öğrenci ID' in s for s in d.warnings)
    c=db();p=prepare(c,9,1,d.rows)
    assert not p.errors and p.counts['new']==1
    apply(c,p,teacher_confirmed=True)
    assert c.execute('select count(*) from soru_konu_kanit_v19').fetchone()[0]==1


def test_csv_explicit_id_and_safe_preview(tmp_path):
    path=file(tmp_path,'karne.csv','Ogrenci ID,Deneme ID,Ders,Soru No,Sonuc,Konu\n1,9,Fizik,3,Yanlis,Elektrostatik\n')
    d=parse_analysis_file(path,student_id=1,exam_id=9)
    assert d.student_id_in_source and d.exam_id_in_source
    assert d.rows[0]['soru_no']=='3'


@pytest.mark.parametrize('student,exam',[(2,9),(1,10)])
def test_never_retarget_explicit_identity(tmp_path,student,exam):
    path=file(tmp_path,'karne.csv',f'ogrenci_id,deneme_id,ders,soru_no,sonuc,konu\n{student},{exam},Fizik,3,yanlis,Elektrostatik\n')
    with pytest.raises(ReportFormatError,match='uyuşmuyor'):
        parse_analysis_file(path, student_id=1,exam_id=9)


def test_missing_exam_identity_requires_warning(tmp_path):
    p=file(tmp_path,'x.tsv','ders\tsoru no\tsonuc\tkonu\nFizik\t3\tyanlis\tElektrostatik\n')
    report=parse_analysis_file(p,student_id=1,exam_id=9)
    assert not report.exam_id_in_source and len(report.warnings)>=2


def test_no_question_table_never_invents_diagnosis(tmp_path):
    p=file(tmp_path,'net.csv','Ders,Dogru,Yanlis,Net\nFizik,5,3,4.25\n')
    with pytest.raises(ReportFormatError,match='Yalnızca ders netlerinden'):
        parse_analysis_file(p,student_id=1,exam_id=9)


def test_ambiguous_question_tables_fail_closed(tmp_path):
    p=file(tmp_path,'mixed.csv', 'Ders,Soru No,Sonuc,Konu\nFizik,3,yanlis,Elektrostatik\nFizik,,yanlis,Basınç\n')
    report=parse_analysis_file(p,student_id=1,exam_id=9)
    assert len(report.rows)==2
    preview=prepare(db(),9,1,report.rows)
    assert preview.errors


def test_document_metadata_identity(tmp_path):
    p=file(tmp_path,'karne.csv','Ogrenci ID: 1\nDeneme ID: 9\nDers | Soru No | Sonuc | Konu\nFizik | 3 | Yanlis | Elektrostatik\n')
    # For a PDF-like grid this metadata works; CSV with mixed separators has
    # no single reliable delimiter, so unknown publisher CSV is not guessed.
    with pytest.raises(ReportFormatError):
        parse_analysis_file(p, student_id=1,exam_id=9)


def test_unknown_extension_and_empty_file(tmp_path):
    p=file(tmp_path,'a.jpg','not a valid spreadsheet')
    with pytest.raises(ReportFormatError,match='Yalnızca'):
        parse_analysis_file(p,student_id=1,exam_id=9)
    p=tmp_path/'a.pdf'; p.write_bytes(b'')
    with pytest.raises(ReportFormatError,match='boş'):
        parse_analysis_file(p,student_id=1,exam_id=9)


def test_invalid_selected_ids(tmp_path):
    p=file(tmp_path,'a.csv','Ders,Soru No,Sonuc,Konu\nFizik,3,Yanlis,Elektrostatik\n')
    with pytest.raises(ReportFormatError,match='seçilmelidir'):
        parse_analysis_file(p,student_id=0,exam_id=9)


def test_searchable_pdf_with_explicit_columns(tmp_path):
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip('reportlab unavailable')
    p=tmp_path/'karne.pdf'
    pdf=canvas.Canvas(str(p))
    pdf.drawString(40,770, 'Ogrenci ID: 1')
    pdf.drawString(40,750, 'Deneme ID: 9')
    pdf.drawString(40,730, 'Ders | Soru No | Sonuc | Konu')
    pdf.drawString(40,710, 'Fizik | 3 | Yanlis | Elektrostatik')
    pdf.save()
    result=parse_analysis_file(p, student_id=1,exam_id=9)
    assert len(result.rows)==1
    assert result.rows[0]['konu']=='Elektrostatik'
    assert result.source_format=='searchable_pdf'
    assert result.student_id_in_source


def test_searchable_pdf_with_subject_section(tmp_path):
    from reportlab.pdfgen import canvas
    p=tmp_path/'karne.pdf'
    pdf=canvas.Canvas(str(p))
    pdf.drawString(40,780,'Ders: Fizik')
    pdf.drawString(40,760,'Soru No | Sonuc | Konu')
    pdf.drawString(40,740,'3 | Yanlis | Elektrostatik')
    pdf.save()
    report=parse_analysis_file(p,student_id=1,exam_id=9)
    assert report.rows[0]['ders']=='Fizik'


def test_pdf_without_question_columns_fails(tmp_path):
    from reportlab.pdfgen import canvas
    p=tmp_path/'summary.pdf';pdf=canvas.Canvas(str(p))
    pdf.drawString(40,780,'Ders | Dogru | Yanlis | Net')
    pdf.drawString(40,760,'Fizik | 5 | 3 | 4.25')
    pdf.save()
    with pytest.raises(ReportFormatError,match='Yalnızca ders netlerinden'):
        parse_analysis_file(p,student_id=1,exam_id=9)


def test_unreadable_image_pdf_fails(tmp_path):
    from reportlab.pdfgen import canvas
    p=tmp_path/'scan.pdf';pdf=canvas.Canvas(str(p))
    pdf.rect(40,500,400,200,stroke=1,fill=0)
    pdf.save()
    with pytest.raises(ReportFormatError,match='aranabilir metin yok'):
        parse_analysis_file(p,student_id=1,exam_id=9)


def test_reimport_idempotent_and_no_homework_writes(tmp_path):
    p=file(tmp_path,'karne.csv','Ders,Soru No,Sonuc,Konu\nFizik,3,Yanlis,Elektrostatik\n')
    c=db()
    before=c.execute('SELECT * FROM odev_takip').fetchall()
    rows=parse_analysis_file(p,student_id=1,exam_id=9).rows
    apply(c,prepare(c,9,1,rows),teacher_confirmed=True)
    again=prepare(c,9,1,rows)
    assert again.counts['same']==1
    apply(c,again,teacher_confirmed=True)
    assert c.execute('SELECT * FROM odev_takip').fetchall()==before
    assert c.execute('SELECT COUNT(*) FROM soru_konu_kanit_v19').fetchone()[0]==1


def test_empty_identity_column_is_not_considered_proven(tmp_path):
    p=file(tmp_path,'student.csv','ogrenci_id,deneme_id,ders,soru_no,sonuc,konu\n,9,Fizik,3,yanlis,Elektrostatik\n')
    data=parse_analysis_file(p,student_id=1,exam_id=9)
    assert not data.student_id_in_source
    assert data.exam_id_in_source
    assert any('öğrenci ID' in w for w in data.warnings)


def test_pdf_identity_declared_after_table_must_agree(tmp_path):
    from reportlab.pdfgen import canvas
    p=tmp_path/'last.pdf'; pdf=canvas.Canvas(str(p))
    pdf.drawString(40,780,'Ders | Soru No | Sonuc | Konu')
    pdf.drawString(40,760,'Fizik | 3 | Yanlis | Elektrostatik')
    pdf.drawString(40,740,'Ogrenci ID: 2')
    pdf.save()
    with pytest.raises(ReportFormatError,match='uyuşmuyor'):
        parse_analysis_file(p,student_id=1,exam_id=9)


def test_duplicate_header_is_error(tmp_path):
    p=file(tmp_path,'duplicate.csv','Ders,Soru No,Sonuc,Konu,Konu Adı\nFizik,3,Yanlis,Elektrostatik,Elektrostatik\n')
    with pytest.raises(ReportFormatError,match='Tekrarlanan'):
        parse_analysis_file(p,student_id=1,exam_id=9)
