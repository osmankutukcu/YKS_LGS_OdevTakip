"""V20 conservative analysis-report adapter (NO OCR, NO database writes).

Recognises explicitly labelled *question-level* rows in CSV/TSV/XLSX and
searchable PDF tables. Does NOT infer topics from lesson score totals, student
names, question text, or publisher templates without a declared mapping.
Selected student/exam identity is a UI hint, NOT document proof; callers must
present ``identity_unverified`` before the V19 confirmation step.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from services.trial_exam_import_v17 import _key, MAX_FILE_BYTES, MAX_INPUT_ROWS
from .layout_detector_v201 import match_header, read_xlsx_sheets, has_partial_question_header

MAX_PDF_PAGES = 20
MAX_EXTRACTED_TEXT = 500_000


class ReportFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ReportData:
    rows: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    source_format: str
    student_id_in_source: bool
    exam_id_in_source: bool
    detected_layout: str = 'Açık soru tablosu'
    scanned_sheets: int = 1


_REQUIRED = ('ders','soru_no','sonuc','konu')
_METADATA = re.compile(r'^\s*(öğrenci|ogrenci|deneme|sınav|sinav)\s*(?:id|no|numarası|numarasi)\s*[:=]\s*(\d+)\s*$', re.I)
_SECTION = re.compile(r'^\s*(?:Ders|Ders Adı|Branş)\s*[:=]\s*([^:|;\t]+?)\s*$', re.I)


def _column_header(row):
    try:
        found = match_header(row)
    except ValueError as exc:
        raise ReportFormatError(str(exc)) from exc
    return found.columns if found else None


def _from_grid(grid, *, student_id, exam_id, source_format, pdf_mode=False):
    rows = []
    warnings = []
    errors = []
    header = None
    lesson_hint = None
    document_student = None
    document_exam = None
    direct_student = False
    direct_exam = False
    student_id_per_row = []
    exam_id_per_row = []
    if len(grid) > MAX_INPUT_ROWS + 150:
        raise ReportFormatError('Dosyada çok fazla satır var; dosyayı bölün.')
    for line, values in enumerate(grid, 1):
        values = [str(value if value is not None else '').strip() for value in values]
        if not any(values):
            continue
        if len(values) == 1:
            label = _SECTION.fullmatch(values[0])
            if label:
                lesson_hint = label.group(1).strip()
                continue
            match = _METADATA.fullmatch(values[0])
            if match:
                field = _key(match.group(1))
                num = int(match.group(2))
                if field.startswith('ogrenci'):
                    if document_student is not None and document_student != num:
                        raise ReportFormatError('Bir dosyada çelişen öğrenci kimliği var.')
                    document_student = num
                    direct_student = True
                else:
                    if document_exam is not None and document_exam != num:
                        raise ReportFormatError('Bir dosyada çelişen deneme kimliği var.')
                    document_exam = num
                    direct_exam = True
                continue
        candidate = _column_header(values)
        if candidate:
            header = candidate
            if 'ders' not in header and not lesson_hint:
                errors.append(f'Satır {line}: ders sütunu veya açık ders başlığı bulunamadı.')
            continue
        if header is None:
            continue  # title, notes, exam summary: not question-level evidence
        if len(rows) >= MAX_INPUT_ROWS:
            errors.append('En fazla 5000 soru satırı kabul edilir.')
            break
        def cell(field):
            idx = header.get(field)
            return values[idx] if idx is not None and idx < len(values) else ''
        # Don't silently skip misformatted nonempty lines in a question table.
        if not cell('soru_no') and not cell('konu') and not cell('sonuc'):
            # Distinguish section titles/footnotes from corrupted entries.
            if len(values) == 1:
                header = None
                continue
            errors.append(f'Satır {line}: soru bilgileri boş veya tablo bozulmuş.')
            continue
        lesson = cell('ders') or lesson_hint or ''
        if not lesson:
            errors.append(f'Satır {line}: ders adı yok.')
            continue
        raw_student = cell('ogrenci_id')
        raw_exam = cell('deneme_id')
        student_id_per_row.append(bool(raw_student))
        exam_id_per_row.append(bool(raw_exam))
        supplied_student = raw_student or (str(document_student) if document_student is not None else '')
        supplied_exam = raw_exam or (str(document_exam) if document_exam is not None else '')
        if supplied_student and supplied_student != str(student_id):
            errors.append(f'Satır {line}: dosyadaki öğrenci ID ile seçili öğrenci uyuşmuyor.')
            continue
        if supplied_exam and supplied_exam != str(exam_id):
            errors.append(f'Satır {line}: dosyadaki deneme ID ile seçili deneme uyuşmuyor.')
            continue
        # No identity in source: use selected ID but flag it clearly in the preview.
        rows.append(dict(ogrenci_id=str(student_id), deneme_id=str(exam_id),
                         ders=lesson, soru_no=cell('soru_no'), sonuc=cell('sonuc'),
                         konu=cell('konu'), kazanim_kodu=cell('kazanim_kodu'), _row=line))
    if errors:
        raise ReportFormatError('Karne tablo hataları: ' + ' | '.join(errors[:10]) +
                                (f' (+{len(errors)-10} hata)' if len(errors)>10 else ''))
    if not rows:
        raise ReportFormatError('Açık soru no + sonuç + konu sütunları bulunamadı. '
                                'Yalnızca ders netlerinden konu/soru tahmini yapılmaz.')
    if document_student is not None and document_student != student_id:
        raise ReportFormatError('Belgede yer alan öğrenci ID, seçili öğrenciyle uyuşmuyor.')
    if document_exam is not None and document_exam != exam_id:
        raise ReportFormatError('Belgede yer alan deneme ID, seçili denemeyle uyuşmuyor.')
    direct_student = direct_student or bool(student_id_per_row and all(student_id_per_row))
    direct_exam = direct_exam or bool(exam_id_per_row and all(exam_id_per_row))
    if not direct_student:
        warnings.append('Dosyada öğrenci ID kanıtı bulunmayabilir. Seçilen öğrenciyi öğretmen özellikle doğrulamalıdır.')
    if not direct_exam:
        warnings.append('Dosyada deneme ID kanıtı yok. Seçilen sınavı öğretmen özellikle doğrulamalıdır.')
    warnings.append('Konu/kazanım metni belge beyanıdır; resmî kazanım doğrulaması değildir.')
    if pdf_mode:
        warnings.append('PDF metin çıkarımı satır/sütun sırasını değiştirebilir; her soru önizlemede doğrulanmalıdır.')
    return ReportData(tuple(rows), tuple(dict.fromkeys(warnings)), source_format,
                      direct_student, direct_exam)


def _pdf_text_lines(path):
    """Read *embedded* PDF text only. Never OCR / guess from image pixels."""
    errors = []
    try:
        import fitz
        doc = fitz.open(str(path))
        try:
            if doc.needs_pass:
                raise ReportFormatError('Parolalı PDF desteklenmiyor.')
            if len(doc) > MAX_PDF_PAGES:
                raise ReportFormatError(f'En fazla {MAX_PDF_PAGES} PDF sayfası desteklenir.')
            texts = [page.get_text('text', sort=True) or '' for page in doc]
        finally:
            doc.close()
    except ReportFormatError:
        raise
    except (ImportError, RuntimeError, ValueError) as exc:
        errors.append(str(exc))
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path), strict=True)
            if reader.is_encrypted:
                raise ReportFormatError('Parolalı PDF desteklenmiyor.')
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ReportFormatError('PDF sayfa sınırını aşıyor.')
            texts = [page.extract_text() or '' for page in reader.pages]
        except ReportFormatError:
            raise
        except Exception as err:
            raise ReportFormatError('PDF metni okunamadı veya PDF bozuk.') from err
    text = '\n'.join(texts)
    if len(text)>MAX_EXTRACTED_TEXT:
        raise ReportFormatError('PDF çıkarılan metin sınırını aşıyor.')
    if not text.strip():
        raise ReportFormatError('Taranmış/görsel PDF: aranabilir metin yok. OCR ile tahmini konu atanmaz.')
    return text.splitlines()


def _split_pdf_row(text):
    if '|' in text:
        return [x.strip() for x in text.strip(' |').split('|')]
    if '\t' in text:
        return [x.strip() for x in text.split('\t')]
    if ';' in text:
        return [x.strip() for x in text.split(';')]
    if re.search(r'\s{2,}',text):
        return [x.strip() for x in re.split(r'\s{2,}',text.strip())]
    return [text.strip()]


def parse_analysis_file(path, *, student_id: int, exam_id: int, allow_ocr: bool = False) -> ReportData:
    """Generate V19-compatible draft rows; does not persist any information."""
    if type(student_id) is not int or student_id <= 0 or type(exam_id) is not int or exam_id <= 0:
        raise ReportFormatError('Önce doğru öğrenci ve deneme seçilmelidir.')
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES or file.stat().st_size == 0:
        raise ReportFormatError('Dosya bulunamadı, boş veya 8 MB sınırını aşıyor.')
    suffix = file.suffix.lower()
    if suffix in {'.jpg', '.jpeg', '.png'} and allow_ocr:
        from .ocr_adapter_v202 import parse_scanned_report
        return parse_scanned_report(file, student_id=student_id, exam_id=exam_id)
    if suffix == '.pdf':
        try:
            lines = _pdf_text_lines(file)
        except ReportFormatError as exc:
            if allow_ocr and 'aranabilir metin yok' in str(exc):
                from .ocr_adapter_v202 import parse_scanned_report
                return parse_scanned_report(file, student_id=student_id, exam_id=exam_id)
            raise
        return _from_grid([_split_pdf_row(t) for t in lines], student_id=student_id,
                          exam_id=exam_id, source_format='searchable_pdf', pdf_mode=True)
    if suffix == '.xlsx':
        try:
            sheets = read_xlsx_sheets(file)
        except Exception as exc:
            raise ReportFormatError('XLSX dosyası okunamadı: '+str(exc)) from exc
        parsed = []
        ignored = []
        for sheet_name, grid in sheets:
            try:
                data = _from_grid(grid, student_id=student_id, exam_id=exam_id,
                                  source_format='xlsx')
            except ReportFormatError as exc:
                # A cover/info sheet with no question table is not a parse error.
                # Any other error, including conflicting IDs or bad rows, blocks ALL imports.
                if str(exc).startswith('Açık soru no + sonuç + konu sütunları bulunamadı.'):
                    if has_partial_question_header(grid):
                        raise ReportFormatError(f'Excel sayfası {sheet_name!r}: Soru tablosu eksik sütun içeriyor; ders, soru no, sonuç ve konu başlıklarını doğrulayın.') from exc
                    ignored.append(sheet_name)
                    continue
                raise ReportFormatError(f'Excel sayfası {sheet_name!r}: {exc}') from exc
            parsed.append((sheet_name, data))
        if not parsed:
            raise ReportFormatError('Excel dosyasının görünür sayfalarında açık soru no + sonuç + konu tablosu bulunamadı.')
        if sum(len(x.rows) for _, x in parsed) > MAX_INPUT_ROWS:
            raise ReportFormatError('Excel toplam soru satırı 5000 sınırını aşıyor.')
        rows = tuple(row for _, data in parsed for row in data.rows)
        warnings = [w for _, data in parsed for w in data.warnings]
        if ignored:
            warnings.append('Soru tablosu olmayan sayfalar atlandı: ' + ', '.join(ignored[:8]))
        warnings.append('Okunan sayfalar: ' + ', '.join(name for name, _ in parsed))
        if len(parsed) > 1:
            warnings.append('Birden çok sayfa birleştirildi; öğrenci, ders ve soru numaralarını önizlemede kontrol edin.')
        return ReportData(rows, tuple(dict.fromkeys(warnings)), 'xlsx',
                          all(d.student_id_in_source for _, d in parsed),
                          all(d.exam_id_in_source for _, d in parsed),
                          'Çok sayfalı soru tabloları' if len(parsed)>1 else 'Tek sayfalı soru tablosu',
                          len(sheets))
    elif suffix in {'.csv','.tsv'}:
        try:
            text = file.read_text('utf-8-sig')
        except UnicodeError as exc:
            raise ReportFormatError('CSV/TSV UTF-8 olmalıdır.') from exc
        if suffix == '.tsv':
            dialect = csv.excel_tab
        else:
            try:
                dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t|')
            except csv.Error:
                dialect = csv.excel
        grid = list(csv.reader(io.StringIO(text),dialect))
    else:
        raise ReportFormatError('Yalnızca CSV, TSV, XLSX veya aranabilir PDF kabul edilir. Görsellerde otomatik OCR yok.')
    return _from_grid(grid,student_id=student_id,exam_id=exam_id,source_format=suffix[1:])
