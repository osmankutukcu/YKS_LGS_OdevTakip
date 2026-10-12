"""Conservative question-to-topic import; independent of homework writes.

CSV/XLSX rows are teacher assertions, never AI-generated diagnoses or verified
official curriculum mappings. Preview is read-only and apply is atomic,
optimistically rechecking every affected row. Re-import is idempotent.
"""
from __future__ import annotations
import csv
import io
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Iterable

from services.trial_exam_import_v17 import _key, _read_xlsx, MAX_FILE_BYTES, MAX_INPUT_ROWS

ALLOWED_RESULTS = {'dogru':'dogru','d':'dogru','correct':'dogru',
                   'yanlis':'yanlis','y':'yanlis','wrong':'yanlis',
                   'bos':'bos','b':'bos','blank':'bos'}
DDL = '''CREATE TABLE IF NOT EXISTS soru_konu_kanit_v19 (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 deneme_id INTEGER NOT NULL, ogrenci_id INTEGER NOT NULL,
 ders_adi TEXT NOT NULL, soru_no INTEGER NOT NULL,
 sonuc TEXT NOT NULL CHECK(sonuc IN ('dogru','yanlis','bos')),
 konu_adi TEXT NOT NULL, kazanim_kodu TEXT NOT NULL DEFAULT '',
 kaynak TEXT NOT NULL DEFAULT 'ogretmen_onayli_dosya',
 guncelleme_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(deneme_id, ogrenci_id, ders_adi, soru_no),
 FOREIGN KEY(deneme_id) REFERENCES denemeler(id),
 FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id))'''
LOG_DDL = '''CREATE TABLE IF NOT EXISTS soru_konu_kanit_log_v19 (
 id INTEGER PRIMARY KEY AUTOINCREMENT, deneme_id INTEGER NOT NULL,
 ogrenci_id INTEGER NOT NULL, ders_adi TEXT NOT NULL, soru_no INTEGER NOT NULL,
 onceki TEXT, sonraki TEXT NOT NULL, islem_tarihi TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)'''

class EvidenceImportError(ValueError):
    pass

@dataclass(frozen=True)
class EvidenceItem:
    exam_id: int
    student_id: int
    subject: str
    question_no: int
    result: str
    topic: str
    outcome_code: str = ''
    source_row: int = 0

@dataclass(frozen=True)
class Change:
    item: EvidenceItem
    before: tuple | None  # (result, topic, outcome_code), or absent
    status: str  # new/update/same

@dataclass(frozen=True)
class Preview:
    changes: tuple[Change, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    score_baseline: tuple[tuple[str,int,int,int], ...] = ()
    @property
    def counts(self):
        return {label:sum(c.status == label for c in self.changes)
                for label in ('new','update','same')}

HEADER_ALIASES = {
 'ogrenci_id': ('ogrenci_id','ogrenci id','id'),
 'deneme_id': ('deneme_id','deneme id','sinav_id'),
 'ders': ('ders','ders_adi','ders adi'),
 'soru_no': ('soru_no','soru no','soru','soru numarasi'),
 'sonuc': ('sonuc','cevap_durumu','durum'),
 'konu': ('konu','konu_adi','konu adi'),
 'kazanim_kodu': ('kazanim_kodu','kazanim kodu','ogrenme_ciktisi','kazanim')
}
REQUIRED = ('ogrenci_id','ders','soru_no','sonuc','konu')


def parse_file(path: str | Path) -> list[dict[str, object]]:
    """No formulas, macros, remote documents, or implicit topic extraction."""
    p=Path(path)
    if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
        raise EvidenceImportError('Dosya bulunamadı veya 8 MB sınırını aşıyor.')
    if p.suffix.lower()=='.xlsx':
        try: grid=_read_xlsx(p)
        except Exception as exc: raise EvidenceImportError(str(exc)) from exc
    elif p.suffix.lower() in ('.csv','.tsv'):
        try: text=p.read_text('utf-8-sig')
        except UnicodeError as exc: raise EvidenceImportError('UTF-8 kodlu dosya gerekli.') from exc
        dialect=csv.excel_tab if p.suffix.lower()=='.tsv' else csv.excel
        if p.suffix.lower()=='.csv':
            try: dialect=csv.Sniffer().sniff(text[:4096],delimiters=',;\t')
            except csv.Error: pass
        grid=list(csv.reader(io.StringIO(text),dialect))
    else:
        raise EvidenceImportError('Yalnızca CSV, TSV veya XLSX desteklenir.')
    if not grid: raise EvidenceImportError('Dosya boş.')
    if len(grid)>MAX_INPUT_ROWS+1: raise EvidenceImportError('Satır sınırı aşıldı.')
    columns={}
    for col,value in enumerate(grid[0]):
        h=_key(value).replace('_',' ')
        for target,aliases in HEADER_ALIASES.items():
            if h in {_key(a).replace('_',' ') for a in aliases}:
                if target in columns: raise EvidenceImportError(f'Tekrarlanan sütun: {target}')
                columns[target]=col
    missing=[k for k in REQUIRED if k not in columns]
    if missing: raise EvidenceImportError('Eksik sütunlar: '+', '.join(missing))
    out=[]
    for index,row in enumerate(grid[1:],2):
        if not any(str(x or '').strip() for x in row): continue
        out.append({**{k:row[col] if col<len(row) else '' for k,col in columns.items()},'_row':index})
    if not out: raise EvidenceImportError('Dolu veri satırı bulunamadı.')
    return out


def _table_exists(con,name):
    return con.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(name,)).fetchone() is not None


def _stored(con,item):
    if not _table_exists(con,'soru_konu_kanit_v19'): return None
    found=con.execute('''SELECT sonuc,konu_adi,kazanim_kodu FROM soru_konu_kanit_v19
        WHERE deneme_id=? AND ogrenci_id=? AND ders_adi=? AND soru_no=?''',
        (item.exam_id,item.student_id,item.subject,item.question_no)).fetchall()
    if len(found)>1: raise EvidenceImportError('Mükerrer soru kanıtı bulundu; elle inceleme gerekli.')
    return tuple(found[0]) if found else None


def fetch_exams_for_student(con,student_id):
    if type(student_id) is not int or student_id <= 0: return []
    return con.execute('''SELECT DISTINCT d.id, COALESCE(d.deneme_adi,'Deneme'),
        COALESCE(d.tarih,''),COALESCE(d.tur,'') FROM denemeler d
        JOIN deneme_sonuclari s ON s.deneme_id=d.id
        WHERE s.ogrenci_id=? ORDER BY d.tarih DESC,d.id DESC''',(student_id,)).fetchall()


def prepare(con: sqlite3.Connection, exam_id: int, student_id: int,
            rows: Iterable[Mapping[str,object]]) -> Preview:
    """Validate everything before transaction; require an existing student exam result.

    The row itself supplies an EXPLICIT topic; never derive one from a course net.
    Missing topic in student's current map is a warning, not an invented match.
    """
    if type(exam_id) is not int or exam_id <= 0 or type(student_id) is not int or student_id <= 0:
        raise EvidenceImportError('Öğrenci ve deneme seçilmelidir.')
    person=con.execute('SELECT id,aktif FROM ogrenci WHERE id=?',(student_id,)).fetchone()
    if person is None or int(person[1] or 0)!=1:
        raise EvidenceImportError('Öğrenci bulunamadı veya aktif değil.')
    if con.execute('SELECT 1 FROM denemeler WHERE id=?',(exam_id,)).fetchone() is None:
        raise EvidenceImportError('Deneme kaydı bulunamadı.')
    results=con.execute('''SELECT ders_adi,dogru,yanlis,bos FROM deneme_sonuclari
        WHERE deneme_id=? AND ogrenci_id=?''',(exam_id,student_id)).fetchall()
    by_subject={}
    for subj,d,w,b in results:
        key=_key(subj)
        by_subject.setdefault(key,[]).append((str(subj),int(d or 0),int(w or 0),int(b or 0)))
    known_topics=set()
    for table,lesson_col,topic_col in [('odev','ders','konu_ad'),('odev_takip','ders_adi','konu_adi'),
                                        ('koc_konu_takip','ders_adi','konu_adi')]:
        if _table_exists(con,table):
            try:
                known_topics.update((_key(r[0]),_key(r[1])) for r in con.execute(
                    f'SELECT {lesson_col},{topic_col} FROM {table} WHERE ogrenci_id=?',(student_id,)))
            except sqlite3.OperationalError: pass
    changes=[]; errors=[]; warnings=[]; seen=set(); status_counts={}
    for ix,raw in enumerate(rows,2):
        line=int(raw.get('_row') or ix)
        try:
            if str(raw.get('ogrenci_id') or '').strip()!=str(student_id):
                raise EvidenceImportError('Öğrenci ID seçili öğrenciyle eşleşmiyor.')
            file_exam=str(raw.get('deneme_id') or '').strip()
            if file_exam and file_exam!=str(exam_id):
                raise EvidenceImportError('Deneme ID seçili sınavla eşleşmiyor.')
            options=by_subject.get(_key(raw.get('ders')),[])
            if len(options)!=1:
                raise EvidenceImportError('Ders sonucu yok veya ders adı belirsiz; deneme kaydını kontrol edin.')
            subject,correct,wrong,blank=options[0]
            q=str(raw.get('soru_no') or '').strip()
            if not q.isdecimal() or not 1<=int(q)<=200:
                raise EvidenceImportError('Soru numarası 1–200 arasında tam sayı olmalı.')
            result=ALLOWED_RESULTS.get(_key(raw.get('sonuc')))
            if result is None: raise EvidenceImportError('Sonuç doğru, yanlış veya boş olmalı.')
            raw_topic=str(raw.get('konu') or '')
            raw_outcome=str(raw.get('kazanim_kodu') or '')
            if any(ord(c)<32 for c in raw_topic+raw_outcome):
                raise EvidenceImportError('Kontrol karakteri veya satır sonu kullanılamaz.')
            topic=' '.join(raw_topic.split())
            outcome=' '.join(raw_outcome.split())
            if not topic or len(topic)>160 or len(outcome)>100 or len(subject)>100:
                raise EvidenceImportError('Konu adı zorunlu; metin uzunluğu sınırını kontrol edin.')
            if any(ord(c)<32 for c in topic+outcome):
                raise EvidenceImportError('Kontrol karakteri kullanılamaz.')
            item=EvidenceItem(exam_id,student_id,subject,int(q),result,topic,outcome,line)
            identity=(exam_id,student_id,subject,item.question_no)
            if identity in seen: raise EvidenceImportError('Aynı soru dosyada iki kez var.')
            seen.add(identity)
            before=_stored(con,item)
            after=(item.result,item.topic,item.outcome_code)
            status='same' if before==after else 'update' if before else 'new'
            changes.append(Change(item,before,status))
            key=(_key(subject),_key(topic))
            if key not in known_topics:
                warnings.append(f'Satır {line}: {subject}/{topic} öğrencinin mevcut konu kayıtlarıyla birebir eşleşmiyor; öğretmen kontrol etmeli.')
            status_counts[(subject,result)]=status_counts.get((subject,result),0)+1
        except EvidenceImportError as exc:
            errors.append(f'Satır {line}: {exc}')
    if not changes and not errors: errors.append('İçe aktarılacak satır bulunamadı.')
    # Also account for previously imported items in a different batch.
    # Otherwise multiple valid partial CSV files could exceed exam totals.
    existing={}
    if _table_exists(con,'soru_konu_kanit_v19'):
        for subject,number,result in con.execute('''SELECT ders_adi,soru_no,sonuc FROM soru_konu_kanit_v19
            WHERE deneme_id=? AND ogrenci_id=?''',(exam_id,student_id)):
            existing[(str(subject),int(number))]=str(result)
    for change in changes:
        item=change.item
        existing[(item.subject,item.question_no)]=item.result
    counts={}
    for (subject,_question),result in existing.items():
        counts[(subject,result)]=counts.get((subject,result),0)+1
    for (subject,result),count in counts.items():
        options=by_subject.get(_key(subject),[])
        if len(options)!=1:
            errors.append(f'{subject}: önceki soru kaydı sınav dersiyle eşleşmiyor.')
            continue
        values=options[0]
        limit={'dogru':values[1],'yanlis':values[2],'bos':values[3]}.get(result)
        if limit is None:
            errors.append(f'{subject}: bilinmeyen eski soru sonucu var.')
            continue
        if result!='bos' and count>limit:
            errors.append(f'{subject}: {count} {result} soru, deneme sonucundaki {limit} sayısını aşıyor.')
        if result=='bos' and limit>0 and count>limit:
            errors.append(f'{subject}: boş soru sayısı deneme sonucunu aşıyor.')
    if len(changes)>MAX_INPUT_ROWS: errors.append('Satır sınırı aşıldı.')
    return Preview(tuple(changes),tuple(errors),tuple(dict.fromkeys(warnings)),
                   tuple(sorted(row for options in by_subject.values() for row in options)))


def apply(con: sqlite3.Connection, preview: Preview, *, teacher_confirmed: bool=False):
    """All-or-nothing, append-only audit of updates; never touches original scores."""
    if not teacher_confirmed:
        raise EvidenceImportError('Konu eşleşmeleri öğretmen tarafından onaylanmadan kayıt yapılamaz.')
    if preview.errors or not preview.changes:
        raise EvidenceImportError('Önizlemede hata var veya kaydedilecek veri yok.')
    if con.in_transaction: raise EvidenceImportError('Açık işlem var; kaydetme reddedildi.')
    try:
        con.execute('BEGIN IMMEDIATE')
        current_scores=con.execute('''SELECT ders_adi,dogru,yanlis,bos
            FROM deneme_sonuclari WHERE deneme_id=? AND ogrenci_id=?''',
            (preview.changes[0].item.exam_id,preview.changes[0].item.student_id)).fetchall()
        score_state=tuple(sorted((str(s),int(d or 0),int(w or 0),int(b or 0))
                                 for s,d,w,b in current_scores))
        if score_state!=preview.score_baseline:
            raise EvidenceImportError('Deneme sonuçları önizlemeden sonra değişti; yenileyin.')
        con.execute(DDL); con.execute(LOG_DDL)
        result={'new':0,'update':0,'same':0}
        seen=set()
        for change in preview.changes:
            identity=(change.item.exam_id,change.item.student_id,
                      change.item.subject,change.item.question_no)
            if identity in seen or identity[:2] != (preview.changes[0].item.exam_id,
                                                    preview.changes[0].item.student_id):
                raise EvidenceImportError('Önizleme kimliği tutarsız.')
            seen.add(identity)
            item=change.item
            student=con.execute('SELECT aktif FROM ogrenci WHERE id=?',(item.student_id,)).fetchone()
            if student is None or int(student[0] or 0)!=1:
                raise EvidenceImportError('Öğrenci bilgisi değişti; yeniden önizleyin.')
            row=con.execute('SELECT 1 FROM deneme_sonuclari WHERE deneme_id=? AND ogrenci_id=? AND ders_adi=?',
                             (item.exam_id,item.student_id,item.subject)).fetchall()
            if len(row)!=1: raise EvidenceImportError('Deneme sonuç kaydı değişti; yeniden önizleyin.')
            current=_stored(con,item)
            if current!=change.before: raise EvidenceImportError('Kayıt başka işlemde değişti; önizlemeyi yenileyin.')
            if change.status=='same':
                result['same']+=1; continue
            if current is None:
                con.execute('''INSERT INTO soru_konu_kanit_v19
                    (deneme_id,ogrenci_id,ders_adi,soru_no,sonuc,konu_adi,kazanim_kodu)
                    VALUES (?,?,?,?,?,?,?)''',
                    (item.exam_id,item.student_id,item.subject,item.question_no,item.result,item.topic,item.outcome_code))
                result['new']+=1
            else:
                con.execute('''UPDATE soru_konu_kanit_v19 SET sonuc=?,konu_adi=?,kazanim_kodu=?,
                    guncelleme_tarihi=CURRENT_TIMESTAMP
                    WHERE deneme_id=? AND ogrenci_id=? AND ders_adi=? AND soru_no=?''',
                    (item.result,item.topic,item.outcome_code,item.exam_id,item.student_id,item.subject,item.question_no))
                result['update']+=1
            # Audit is extra metadata, no raw student names.
            con.execute('''INSERT INTO soru_konu_kanit_log_v19
                (deneme_id,ogrenci_id,ders_adi,soru_no,onceki,sonraki) VALUES (?,?,?,?,?,?)''',
                (item.exam_id,item.student_id,item.subject,item.question_no,
                 repr(current) if current else None,repr((item.result,item.topic,item.outcome_code))))
        con.commit()
        return result
    except Exception:
        con.rollback()
        raise
