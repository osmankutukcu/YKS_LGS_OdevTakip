"""V17 exam result import / conservative score persistence.

Pure Python, no Qt imports and no schema migration. Existing deneme_sonuclari
rows are only updated by their exact (exam, student, subject) identity.
Unmentioned rows are never deleted. All writes are transactional.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_INPUT_ROWS = 5000
MAX_FIELD_LENGTH = 500


def _key(value: object) -> str:
    text = str(value or '').replace('ı', 'i').replace('İ', 'I')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                    if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class ScoreInput:
    student_id: int
    subject: str
    correct: int
    wrong: int
    blank: Optional[int] = None
    source_row: int = 0


@dataclass(frozen=True)
class ScoreChange:
    item: ScoreInput
    before: Optional[tuple]
    status: str  # new, update, same


@dataclass(frozen=True)
class Preview:
    changes: tuple[ScoreChange, ...]
    errors: tuple[str, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {k: sum(c.status == k for c in self.changes) for k in ('new', 'update', 'same')}


class ExamImportError(ValueError):
    pass


def _to_int(value: object, label: str, row: int) -> int:
    if isinstance(value, bool):
        raise ExamImportError(f'Satır {row}: {label} tam sayı olmalı.')
    text = str(value if value is not None else '').strip()
    if not text or not text.isdecimal():
        raise ExamImportError(f'Satır {row}: {label} 0 veya pozitif tam sayı olmalı.')
    num = int(text)
    if num > 200:
        raise ExamImportError(f'Satır {row}: {label} 200 üzerinde olamaz; kaynağı kontrol edin.')
    return num


def _load_students(con: sqlite3.Connection):
    students = con.execute('SELECT id, ad, soyad, aktif FROM ogrenci').fetchall()
    by_id = {int(r[0]): r for r in students}
    names = {}
    for r in students:
        names.setdefault(_key(f'{r[1]} {r[2]}'), []).append(int(r[0]))
    return by_id, names


def _read_existing(con, exam_id, student_id, subject):
    rows = con.execute('''SELECT id,dogru,yanlis,bos,net FROM deneme_sonuclari
        WHERE deneme_id=? AND ogrenci_id=? AND ders_adi=?''',
        (exam_id, student_id, subject)).fetchall()
    if len(rows) > 1:
        raise ExamImportError(f'Öğrenci {student_id}, {subject}: geçmişte mükerrer sonuç mevcut; elle inceleme gerekli.')
    return tuple(rows[0]) if rows else None


def prepare(con: sqlite3.Connection, exam_id: int, subjects: Iterable[str],
            records: Iterable[Mapping[str, object]], *, baseline: Optional[Mapping[tuple, object]] = None) -> Preview:
    """Validates all rows; no SQL writes. A displayed-table baseline can be supplied
    to reject an edit made stale since the screen was opened.
    """
    if type(exam_id) is not int or exam_id <= 0 or not con.execute('SELECT 1 FROM denemeler WHERE id=?', (exam_id,)).fetchone():
        raise ExamImportError('Geçerli bir deneme seçilmedi.')
    allowed = {}
    for sub in subjects:
        norm = _key(sub)
        if norm in allowed and allowed[norm] != sub:
            raise ExamImportError('Ayarlar içinde aynı isme karşılık gelen iki ders var.')
        allowed[norm] = sub
    by_id, by_name = _load_students(con)
    changes = []
    errors = []
    seen = set()
    for index, raw in enumerate(records, 2):
        if index > MAX_INPUT_ROWS + 1:
            errors.append(f'En fazla {MAX_INPUT_ROWS} satır içe aktarılabilir.')
            break
        line = int(raw.get('_row') or index)
        try:
            raw_id = str(raw.get('ogrenci_id') or '').strip()
            name = str(raw.get('ad_soyad') or '').strip()
            if raw_id:
                if not raw_id.isdecimal():
                    raise ExamImportError(f'Satır {line}: Öğrenci ID geçersiz.')
                student_id = int(raw_id)
                if student_id not in by_id:
                    raise ExamImportError(f'Satır {line}: Öğrenci ID bulunamadı.')
                if name and _key(f'{by_id[student_id][1]} {by_id[student_id][2]}') != _key(name):
                    raise ExamImportError(f'Satır {line}: Öğrenci adı ile ID uyuşmuyor.')
            else:
                matches = by_name.get(_key(name), [])
                if len(matches) != 1:
                    raise ExamImportError(f'Satır {line}: Öğrenci adı eşsiz değil veya bulunamadı; öğrenci_id kullanın.')
                student_id = matches[0]
            if int(by_id[student_id][3] or 0) != 1:
                raise ExamImportError(f'Satır {line}: Öğrenci aktif değil; önce kaydı kontrol edin.')
            subject = allowed.get(_key(raw.get('ders')))
            if subject is None:
                raise ExamImportError(f'Satır {line}: Ders adı seçili sınavın ders listesinde bulunamadı.')
            correct = _to_int(raw.get('dogru'), 'Doğru', line)
            wrong = _to_int(raw.get('yanlis'), 'Yanlış', line)
            blank_raw = raw.get('bos')
            blank = None if blank_raw is None or str(blank_raw).strip() == '' else _to_int(blank_raw, 'Boş', line)
            if correct + wrong + (blank or 0) > 200:
                raise ExamImportError(f'Satır {line}: Doğru+yanlış+boş toplamı makul sınırı aşıyor.')
            identity = (student_id, subject)
            if identity in seen:
                raise ExamImportError(f'Satır {line}: Aynı öğrenci/ders birden fazla kez bulunuyor.')
            seen.add(identity)
            before = _read_existing(con, exam_id, student_id, subject)
            if baseline is not None and identity in baseline and baseline[identity] != before:
                raise ExamImportError(f'Satır {line}: Kayıt ekranda açıldığından beri değişmiş. Yenileyip tekrar deneyin.')
            previous_blank = int(before[3] or 0) if before else 0
            stored_blank = previous_blank if blank is None else blank
            new_net = max(0., correct - wrong / 4.)
            same = (before is not None and int(before[1]) == correct and int(before[2]) == wrong
                    and previous_blank == stored_blank and abs(float(before[4] or 0.) - new_net) < 1e-8)
            item = ScoreInput(student_id, subject, correct, wrong, blank, line)
            changes.append(ScoreChange(item, before, 'same' if same else 'update' if before else 'new'))
        except ExamImportError as exc:
            errors.append(str(exc))
    if not changes and not errors:
        errors.append('İçe aktarılacak dolu sonuç bulunamadı.')
    return Preview(tuple(changes), tuple(errors))


def apply(con: sqlite3.Connection, exam_id: int, preview: Preview) -> dict[str, int]:
    """Atomic apply with optimistic recheck. Does not delete missing students/results."""
    if preview.errors:
        raise ExamImportError('Hatalı satırlar düzeltilmeden sonuçlar kaydedilemez.')
    if not preview.changes:
        raise ExamImportError('Kaydedilecek sonuç yok.')
    # Avoid taking over a caller-owned transaction.
    if con.in_transaction:
        raise ExamImportError('Bu bağlantıda açık işlem var; güvenli kaydetme başlatılamadı.')
    try:
        con.execute('BEGIN IMMEDIATE')
        count = {'new': 0, 'update': 0, 'same': 0}
        for change in preview.changes:
            item = change.item
            before = _read_existing(con, exam_id, item.student_id, item.subject)
            if before != change.before:
                raise ExamImportError('Başka bir kullanıcı deneme sonucunu değiştirmiş; yeniden önizleyin.')
            if change.status == 'same':
                count['same'] += 1
                continue
            blank = item.blank if item.blank is not None else int(before[3] or 0) if before else 0
            net = max(0., item.correct - item.wrong / 4.)
            if before:
                con.execute('''UPDATE deneme_sonuclari SET dogru=?, yanlis=?, bos=?, net=?
                    WHERE id=?''', (item.correct, item.wrong, blank, net, before[0]))
                count['update'] += 1
            else:
                con.execute('''INSERT INTO deneme_sonuclari
                    (deneme_id,ogrenci_id,ders_adi,dogru,yanlis,bos,net)
                    VALUES (?,?,?,?,?,?,?)''',
                    (exam_id, item.student_id, item.subject, item.correct, item.wrong, blank, net))
                count['new'] += 1
        con.commit()
        return count
    except Exception:
        con.rollback()
        raise


HEADER_ALIASES = {
    'ogrenci_id': ('ogrenci_id', 'ogrenci id', 'id'),
    'ad_soyad': ('ad soyad', 'ogrenci', 'ogrenci adi', 'adi soyadi', 'ad_soyad'),
    'ders': ('ders', 'ders adi', 'ders_adi'),
    'dogru': ('dogru', 'd'),
    'yanlis': ('yanlis', 'y'),
    'bos': ('bos', 'b'),
}


def _from_grid(grid: list[list[object]]) -> list[dict[str, object]]:
    if not grid:
        raise ExamImportError('Dosya boş.')
    mapping = {}
    for i, header in enumerate(grid[0]):
        name = _key(header).replace('_', ' ')
        hits = [target for target, aliases in HEADER_ALIASES.items()
                if name in {_key(a).replace('_', ' ') for a in aliases}]
        if len(hits) == 1:
            if hits[0] in mapping:
                raise ExamImportError(f'Birden fazla {hits[0]} sütunu var.')
            mapping[hits[0]] = i
    for mandatory in ('ders', 'dogru', 'yanlis'):
        if mandatory not in mapping:
            raise ExamImportError(f'Gerekli sütun eksik: {mandatory}.')
    if 'ogrenci_id' not in mapping and 'ad_soyad' not in mapping:
        raise ExamImportError('Öğrenci ID veya Ad Soyad sütunu gerekli.')
    result = []
    for row_num, row in enumerate(grid[1:], 2):
        if all(not str(x or '').strip() for x in row):
            continue
        data = {key: (row[idx] if idx < len(row) else '') for key, idx in mapping.items()}
        data['_row'] = row_num
        result.append(data)
    return result


def _read_xlsx(path: Path) -> list[list[object]]:
    """Small plain-cell XLSX reader. No macros/formulas/external links are executed.
    Cached formula results are intentionally rejected to avoid stale marks.
    """
    main = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    relns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    pkgrel = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    with zipfile.ZipFile(path) as arc:
        entries = arc.infolist()
        if len(entries) > 1000 or sum(x.file_size for x in entries) > 40 * 1024 * 1024:
            raise ExamImportError('Excel dosyası güvenlik sınırlarını aşıyor.')
        if any(n.lower().endswith(('vbaproject.bin','.rels.exe')) for n in arc.namelist()):
            raise ExamImportError('Makro içeren çalışma kitabı desteklenmiyor.')
        wb = ET.fromstring(arc.read('xl/workbook.xml'))
        rel = ET.fromstring(arc.read('xl/_rels/workbook.xml.rels'))
        targets = {x.attrib.get('Id'): x.attrib.get('Target', '') for x in rel}
        sheets = wb.find(main+'sheets')
        if sheets is None or not len(sheets):
            raise ExamImportError('Excel sayfası bulunamadı.')
        path_target = targets.get(sheets[0].get(relns+'id'), '')
        if '..' in path_target.split('/') or '://' in path_target:
            raise ExamImportError('Excel sayfa yolu geçersiz.')
        sheetpath = (path_target.lstrip('/') if path_target.startswith('/') else 'xl/' + path_target)
        sheetpath = sheetpath.replace('xl/xl/', 'xl/')
        shared = []
        if 'xl/sharedStrings.xml' in arc.namelist():
            ss = ET.fromstring(arc.read('xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in el.iter(main+'t')) for el in ss.findall(main+'si')]
        sheet = ET.fromstring(arc.read(sheetpath))
        out = []
        for r in sheet.iter(main+'row'):
            if len(out) > MAX_INPUT_ROWS:
                raise ExamImportError('Çok fazla satır.')
            cells = {}
            for c in r.findall(main+'c'):
                if c.find(main+'f') is not None:
                    raise ExamImportError('Formül içeren Excel hücresi desteklenmiyor; değer olarak yapıştırın.')
                ref = c.get('r','')
                col = 0
                for char in ref:
                    if not char.isalpha():
                        break
                    col = col*26 + ord(char.upper())-64
                if not 1 <= col <= 64:
                    raise ExamImportError('Excel sütun sayısı 64 sınırını aşıyor.')
                v = c.find(main+'v')
                if c.get('t') == 'inlineStr':
                    is_elem = c.find(main+'is')
                    value = ''.join(t.text or '' for t in is_elem.iter(main+'t')) if is_elem is not None else ''
                elif v is None:
                    value = ''
                elif c.get('t') == 's':
                    try: value = shared[int(v.text or '')]
                    except (ValueError,IndexError): raise ExamImportError('Excel ortak metin indeksi bozuk.')
                else:
                    value = v.text or ''
                if len(str(value)) > MAX_FIELD_LENGTH:
                    raise ExamImportError('Excel hücresi beklenenden uzun.')
                cells[col-1] = value
            out.append([cells.get(i, '') for i in range(max(cells,default=-1)+1)])
        return out


def parse_file(path: str | Path) -> list[dict[str, object]]:
    file = Path(path)
    if file.stat().st_size > MAX_FILE_BYTES:
        raise ExamImportError('Dosya çok büyük (en fazla 8 MB).')
    suffix = file.suffix.lower()
    if suffix == '.xlsx':
        grid = _read_xlsx(file)
    elif suffix in ('.csv', '.tsv', '.txt'):
        try:
            content = file.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ExamImportError('Dosyayı UTF-8 CSV olarak kaydedin.') from exc
        dialect = csv.excel_tab if suffix == '.tsv' else csv.excel
        if suffix != '.tsv':
            try: dialect = csv.Sniffer().sniff(content[:4096], delimiters=',;\t')
            except csv.Error: pass
        grid = list(csv.reader(io.StringIO(content), dialect=dialect))
    else:
        raise ExamImportError('Yalnızca CSV, TSV ve XLSX dosyaları destekleniyor.')
    if len(grid) - 1 > MAX_INPUT_ROWS:
        raise ExamImportError('Çok fazla satır.')
    return _from_grid(grid)
