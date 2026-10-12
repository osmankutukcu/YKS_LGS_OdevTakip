"""V20.2 conservative OCR tests. All databases remain untouched."""
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont

from services.question_evidence_v19 import parse_analysis_file, ReportFormatError
from services.question_evidence_v19 import ocr_adapter_v202 as ocr
from tests.test_v19_question_topic_evidence import db
from services.question_evidence_v19 import prepare


def photo(tmp_path, name='karne.png', size=(900, 500)):
    path=tmp_path/name
    Image.new('RGB',size,'white').save(path)
    return path


def recognizer(lines, confidence=90):
    return lambda im: (lines,confidence)


GOOD=['Ogrenci ID: 1','Deneme ID: 9','Ders | Soru No | Sonuc | Konu',
      'Fizik | 3 | Yanlis | Elektrostatik', 'Fizik | 7 | Bos | Basinc']


def test_image_ocr_valid_and_v19_preview(tmp_path, monkeypatch):
    path=photo(tmp_path)
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(GOOD))
    d=parse_analysis_file(path,student_id=1,exam_id=9,allow_ocr=True)
    assert d.source_format=='local_ocr' and len(d.rows)==2
    assert d.student_id_in_source and d.exam_id_in_source
    assert any('TEK TEK' in warning for warning in d.warnings)
    p=prepare(db(),9,1,d.rows)
    assert not p.errors and p.counts['new']==2


def test_image_rejects_without_explicit_opt_in(tmp_path):
    with pytest.raises(ReportFormatError,match='Yalnızca'):
        parse_analysis_file(photo(tmp_path),student_id=1,exam_id=9)


def test_no_subject_topic_inference_from_net_only(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines', recognizer(['Ders | Dogru | Yanlis | Net','Fizik | 5 | 3 | 4.25']))
    with pytest.raises(ReportFormatError,match='açık soru tablosu'):
        ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)


def test_wrong_student_ocr_blocks_import(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(['Ogrenci ID: 2', *GOOD[1:]]))
    with pytest.raises(ReportFormatError,match='uyuşmuyor'):
        ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)


def test_missing_identity_still_requires_confirmation(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(GOOD[2:]))
    data=ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)
    assert not data.student_id_in_source
    assert not data.exam_id_in_source
    assert any('kimliği' in m or 'öğrenci ID' in m for m in data.warnings)


def test_ocr_no_guessing_when_missing_header_columns(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(['Ders | Soru No | Sonuc', 'Fizik | 3 | Yanlis']))
    with pytest.raises(ReportFormatError,match='eksik/bozuk'):
        ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)


def test_ocr_row_out_of_columns_never_saved(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer([GOOD[2], 'Fizik | 3 | Yanlis']))
    result=ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)
    p=prepare(db(),9,1,result.rows)
    assert p.errors  # topic cannot be inferred


def test_bogus_image_rejected(tmp_path):
    p=tmp_path/'fake.jpg'; p.write_bytes(b'not a photo')
    with pytest.raises(ReportFormatError,match='Görsel okunamadı'):
        ocr.parse_scanned_report(p,student_id=1,exam_id=9)


def test_pixels_bounded_before_ocr(tmp_path,monkeypatch):
    p=photo(tmp_path,size=(6600,900))
    monkeypatch.setattr(ocr,'_recognize_lines',lambda _: pytest.fail('should not OCR oversized picture'))
    with pytest.raises(ReportFormatError,match='çözünürlüğü'):
        ocr.parse_scanned_report(p,student_id=1,exam_id=9)


def test_pdf_image_only_uses_ocr_if_opted_in(tmp_path,monkeypatch):
    image=Image.new('RGB',(720,440),'white')
    path=tmp_path/'scan.pdf';image.save(path,'PDF')
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(GOOD))
    with pytest.raises(ReportFormatError,match='aranabilir metin yok'):
        parse_analysis_file(path,student_id=1,exam_id=9)
    result=parse_analysis_file(path,student_id=1,exam_id=9,allow_ocr=True)
    assert len(result.rows)==2 and result.source_format=='local_ocr'


def test_ocr_normalizes_only_header_spacing():
    lines=['Ders |SoruNo |Sonuc _ | Konu','Fizik |3 | | Yanlis | | Elektrostatik']
    grid=ocr._ocr_grid(lines)
    assert grid==[['Ders','Soru No','Sonuc','Konu'],['Fizik','3','Yanlis','Elektrostatik']]


def test_ocr_explicit_compared_with_real_result_on_fixture(tmp_path):
    # One local smoke test; no real student data and no network.
    import shutil
    if not shutil.which('tesseract'):
        pytest.skip('Tesseract executable not installed')
    path=tmp_path/'synthetic.jpg'
    font_path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not font_path.is_file():
        pytest.skip('Synthetic test font unavailable')
    font=ImageFont.truetype(str(font_path),32)
    im=Image.new('RGB',(1280,550),'white');drawer=ImageDraw.Draw(im)
    for i,text in enumerate(['Ogrenci ID: 1','Deneme ID: 9',
        'Ders     | Soru No   | Sonuc     | Konu',
        'Fizik    | 3             | Yanlis     | Elektrostatik',
        'Fizik    | 7             | Bos         | Basinc']):
        drawer.text((50,50+82*i),text,fill='black',font=font)
    im.save(path)
    result=ocr.parse_scanned_report(path,student_id=1,exam_id=9)
    assert [(r['soru_no'],r['sonuc'],r['konu']) for r in result.rows]==[
        ('3','Yanlis','Elektrostatik'),('7','Bos','Basinc')]


def test_missing_ocr_dep_provides_clear_error(tmp_path,monkeypatch):
    # Simulates missing OCR engine by making the recognizer raise.
    def bad(_):raise ReportFormatError('Yerel OCR çalıştırılamadı.')
    monkeypatch.setattr(ocr,'_recognize_lines',bad)
    with pytest.raises(ReportFormatError,match='Yerel OCR'):
        ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)


def test_invalid_student_and_empty_file(tmp_path):
    p=photo(tmp_path)
    with pytest.raises(ReportFormatError,match='seçilmelidir'):
        ocr.parse_scanned_report(p,student_id=0,exam_id=9)
    q=tmp_path/'empty.png';q.write_bytes(b'')
    with pytest.raises(ReportFormatError,match='boş'):
        ocr.parse_scanned_report(q,student_id=1,exam_id=9)


def test_pdf_more_than_six_pages_rejected_without_running_ocr(tmp_path,monkeypatch):
    p=tmp_path/'too_many.pdf'
    im=Image.new('RGB',(320,320),'white')
    im.save(p,'PDF',save_all=True,append_images=[im.copy() for _ in range(6)])
    monkeypatch.setattr(ocr,'_recognize_lines',lambda image: pytest.fail('page count check first'))
    with pytest.raises(ReportFormatError,match='6 sayfalık'):
        ocr.parse_scanned_report(p,student_id=1,exam_id=9)


def test_multiple_scanned_pages_report_ignored_cover(tmp_path,monkeypatch):
    p=tmp_path/'two_pages.pdf'
    im=Image.new('RGB',(380,300),'white')
    im.save(p,'PDF',save_all=True,append_images=[im.copy()])
    queue=iter([(['Öğrenci performans raporu', 'Tarih: 12-10-2026'],92.0), (GOOD,90.0)])
    monkeypatch.setattr(ocr,'_recognize_lines',lambda image: next(queue))
    result=ocr.parse_scanned_report(p,student_id=1,exam_id=9)
    assert result.scanned_sheets==2 and len(result.rows)==2
    assert any('atlanan sayfalar: 1' in m for m in result.warnings)


def test_page_with_partial_table_blocks_multi_page_import(tmp_path,monkeypatch):
    p=tmp_path/'two_pages.pdf';im=Image.new('RGB',(380,300),'white')
    im.save(p,'PDF',save_all=True,append_images=[im.copy()])
    seq=iter([(GOOD,85),(['Ders | Soru No | Sonuc','Fizik | 4 | Yanlis'],85)])
    monkeypatch.setattr(ocr,'_recognize_lines',lambda im: next(seq))
    with pytest.raises(ReportFormatError,match='Sayfa 2: eksik/bozuk'):
        ocr.parse_scanned_report(p,student_id=1,exam_id=9)


def test_wrong_exam_id_blocks(tmp_path,monkeypatch):
    monkeypatch.setattr(ocr,'_recognize_lines',recognizer(['Deneme ID: 10',*GOOD[2:]]))
    with pytest.raises(ReportFormatError,match='uyuşmuyor'):
        ocr.parse_scanned_report(photo(tmp_path),student_id=1,exam_id=9)


def test_ocr_file_size_bounded(tmp_path,monkeypatch):
    p=tmp_path/'big.png'
    p.write_bytes(b'x' * (8*1024*1024 + 1))
    with pytest.raises(ReportFormatError,match='8 MB'):
        ocr.parse_scanned_report(p,student_id=1,exam_id=9)


def test_ocr_low_confidence_rejected(monkeypatch):
    import pytesseract
    monkeypatch.setattr(pytesseract,'image_to_data',lambda *args,**kwargs: {
        'text':['Ders','Soru','No','Sonuc','Konu'],
        'conf':['17','22','20','12','10'],
        'left':[0,80,130,260,410],
        'width':[50,40,30,80,65],
        'block_num':[1]*5,'par_num':[1]*5,'line_num':[1]*5,
    })
    with pytest.raises(ReportFormatError,match='güvenirliği düşük'):
        ocr._recognize_lines(Image.new('L',(800,500),'white'))
