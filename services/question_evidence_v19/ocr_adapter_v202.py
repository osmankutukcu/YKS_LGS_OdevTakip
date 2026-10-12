"""V20.2: bounded, local-only OCR for *explicit question tables*.

This optional adapter has no Qt or database dependencies and never writes files.
OCR text is NOT an authoritative fact. It must pass the V20/V19 strict
structural, identity and teacher-confirmation path before persistence.
"""
from __future__ import annotations

import statistics
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .karne_adapter_v20 import (
    ReportData, ReportFormatError, _from_grid, _split_pdf_row,
)
from .layout_detector_v201 import has_partial_question_header
from services.trial_exam_import_v17 import MAX_FILE_BYTES, MAX_INPUT_ROWS

if TYPE_CHECKING:
    from PIL import Image

OCR_MAX_PDF_PAGES = 6
OCR_MAX_PIXELS = 18_000_000
OCR_MAX_EDGE = 6500
OCR_MAX_LINES = 6_000
OCR_MIN_MEAN_CONFIDENCE = 65.0
OCR_PAGE_TIMEOUT_SECONDS = 20
OCR_PDF_DPI = 145
_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg'})


def _validate_image(image: 'Image.Image') -> 'Image.Image':
    from PIL import ImageOps
    width, height = image.size
    if (min(width, height) < 200 or max(width, height) > OCR_MAX_EDGE
            or width * height > OCR_MAX_PIXELS):
        raise ReportFormatError('Görsel çözünürlüğü OCR güvenlik sınırlarının dışında.')
    result = ImageOps.exif_transpose(image)
    # Do not interpolate/edit text geometry or save the student image to disk.
    return ImageOps.autocontrast(result.convert('L'))


def _recognize_lines(image: 'Image.Image') -> tuple[list[str], float]:
    """One OCR invocation per page; preserve conservative visual column gaps."""
    try:
        import pytesseract
        from pytesseract import Output
        from pytesseract.pytesseract import TesseractNotFoundError, TesseractError
    except ImportError as exc:
        raise ReportFormatError('OCR için pytesseract kurulmalı; OCR kurulumu isteğe bağlıdır.') from exc
    try:
        data = pytesseract.image_to_data(
            image, lang='eng', config='--psm 6', output_type=Output.DICT,
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    except (RuntimeError, TesseractNotFoundError, TesseractError, OSError) as exc:
        raise ReportFormatError('Yerel OCR çalıştırılamadı. Tesseract ve eng dil paketi kurulumunu kontrol edin.') from exc
    groups: dict[tuple[int, int, int], list[tuple[int, int, str, float]]] = {}
    scores: list[float] = []
    count = len(data.get('text', ()))
    if count > 40_000:
        raise ReportFormatError('OCR belge karmaşıklığı sınırını aşıyor.')
    for i in range(count):
        word = str(data['text'][i]).strip()
        if not word:
            continue
        try:
            conf = float(data['conf'][i])
        except (ValueError, TypeError):
            conf = -1
        if conf < 0:
            continue
        x = int(data['left'][i])
        w = int(data['width'][i])
        group = (int(data['block_num'][i]), int(data['par_num'][i]), int(data['line_num'][i]))
        groups.setdefault(group, []).append((x, w, word, conf))
        if any(c.isalnum() for c in word):
            scores.append(conf)
    if not scores:
        raise ReportFormatError('OCR okunabilir karakter bulamadı. Daha net tarama kullanın.')
    confidence = statistics.mean(scores)
    if confidence < OCR_MIN_MEAN_CONFIDENCE:
        raise ReportFormatError(f'OCR okuma güvenirliği düşük ({confidence:.0f}/100); kayıt için uygun değil.')
    lines=[]
    for tokens in groups.values():
        tokens.sort(key=lambda t: t[0])
        glyph_widths = [w / max(1, len(word)) for _x, w, word, _conf in tokens if any(c.isalnum() for c in word)]
        typical = statistics.median(glyph_widths) if glyph_widths else 8
        threshold = max(28, typical * 3.3)
        chunks=[]
        previous_end=None
        for x,w,word,_conf in tokens:
            if previous_end is not None:
                # Only a WIDE gap becomes a table column. Small gaps stay words.
                chunks.append(' | ' if x - previous_end >= threshold else ' ')
            chunks.append(word)
            previous_end = max(previous_end or x, x + w)
        line=''.join(chunks).strip()
        if line:
            lines.append(line)
        if len(lines)>OCR_MAX_LINES:
            raise ReportFormatError('OCR satır sayısı sınırını aşıyor.')
    return lines,confidence


def _ocr_grid(lines: list[str]) -> list[list[str]]:
    """Normalize a *tiny* set of common OCR heading spacing errors.

    Never infer a subject/topic, never turn course net summaries into questions.
    """
    grid=[]
    for line in lines:
        if '|' in line:
            line = re.sub(r'(?:\s*\|\s*)+', ' | ', line).strip(' |')
        row=_split_pdf_row(line)
        clean=[]
        for cell in row:
            cell=cell.strip()
            folded=re.sub(r'[^a-z0-9]', '', cell.casefold())
            if folded=='soruno':
                cell='Soru No'
            elif folded=='sonuc':
                cell='Sonuc'
            clean.append(cell)
        grid.append(clean)
    return grid


def _images_from_document(path: Path):
    suffix=path.suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        try:
            from PIL import Image
            with Image.open(path) as original:
                if original.format not in ('JPEG', 'PNG'):
                    raise ReportFormatError('Sadece gerçek JPG/PNG görüntü desteklenir.')
                yield _validate_image(original)
        except ReportFormatError:
            raise
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ReportFormatError('Görsel okunamadı veya güvenlik sınırını aşıyor.') from exc
    elif suffix=='.pdf':
        try:
            import fitz
            from PIL import Image
        except ImportError as exc:
            raise ReportFormatError('Taranmış PDF için PyMuPDF ve Pillow kurulmalıdır.') from exc
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise ReportFormatError('Parolalı PDF desteklenmiyor.')
                if not 1<=len(document)<=OCR_MAX_PDF_PAGES:
                    raise ReportFormatError(f'OCR için en fazla {OCR_MAX_PDF_PAGES} sayfalık PDF desteklenir.')
                for page in document:
                    # Reject huge page dimensions BEFORE rasterisation.
                    ratio=OCR_PDF_DPI/72.0
                    w=int(page.rect.width * ratio)
                    h=int(page.rect.height * ratio)
                    if min(w,h)<200 or max(w,h)>OCR_MAX_EDGE or w*h>OCR_MAX_PIXELS:
                        raise ReportFormatError('PDF sayfası OCR çözünürlük sınırını aşıyor.')
                    pix=page.get_pixmap(matrix=fitz.Matrix(ratio,ratio),alpha=False,colorspace=fitz.csGRAY)
                    frame=Image.frombytes('L',(pix.width,pix.height),pix.samples)
                    yield _validate_image(frame)
        except ReportFormatError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise ReportFormatError('PDF sayfası okunamadı veya geçersiz.') from exc
    else:
        raise ReportFormatError('OCR yalnızca JPG, PNG ve taranmış PDF destekler.')


def parse_scanned_report(path: str | Path, *, student_id: int, exam_id: int) -> ReportData:
    """Return V19-compatible DRAFT only; always require manual row verification.

    All page tables must be explicitly headed with question/result/topic columns.
    Cover pages may be skipped, but teacher sees each skipped page warning.
    """
    if type(student_id) is not int or student_id<=0 or type(exam_id) is not int or exam_id<=0:
        raise ReportFormatError('Önce doğru öğrenci ve deneme seçilmelidir.')
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=MAX_FILE_BYTES:
        raise ReportFormatError('OCR dosyası bulunamadı, boş veya 8 MB sınırını aşıyor.')
    rows=[]; warnings=[]; ignored=[]; page_count=0; source_student=True; source_exam=True
    for page_count,image in enumerate(_images_from_document(path),1):
        lines,confidence=_recognize_lines(image)
        grid=_ocr_grid(lines)
        try:
            result=_from_grid(grid,student_id=student_id,exam_id=exam_id,
                              source_format='local_ocr',pdf_mode=False)
        except ReportFormatError as exc:
            if str(exc).startswith('Açık soru no + sonuç + konu sütunları bulunamadı.'):
                if has_partial_question_header(grid):
                    raise ReportFormatError(f'Sayfa {page_count}: eksik/bozuk OCR soru tablosu; dosyayı düzeltin.') from exc
                ignored.append(page_count)
                continue
            raise ReportFormatError(f'Sayfa {page_count}: {exc}') from exc
        rows.extend({**row,'_row':page_count*10000+int(row['_row'])} for row in result.rows)
        source_student &= result.student_id_in_source
        source_exam &= result.exam_id_in_source
        warnings.extend(result.warnings)
        warnings.append(f'Sayfa {page_count}: OCR ortalama karakter güveni {confidence:.0f}/100 (doğruluk garantisi değildir).')
        if len(rows)>MAX_INPUT_ROWS:
            raise ReportFormatError('OCR soru satırı 5000 sınırını aşıyor.')
    if not rows:
        raise ReportFormatError('OCR ile doğrulanabilir açık soru tablosu bulunamadı; ödev veya konu tahmini yapılmadı.')
    if ignored:
        warnings.append('Tablo bulunamayan ve otomatik atlanan sayfalar: '+', '.join(map(str,ignored)) + '. Kaynakla kontrol edin.')
    warnings.append('OCR yerel çalışır; başlık ve soru değerlerini kaynak görselle TEK TEK karşılaştırın.')
    warnings.append('Belgedeki konu/kazanım adı öğretmen beyanıdır; resmî müfredat doğrulaması değildir.')
    return ReportData(tuple(rows),tuple(dict.fromkeys(warnings)), 'local_ocr',
                      bool(source_student),bool(source_exam),
                      'Fotoğraf/taranmış PDF – yerel OCR taslağı',page_count)
