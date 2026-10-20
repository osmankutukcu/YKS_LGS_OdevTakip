# -*- coding: utf-8 -*-
"""V3.5.86: explicit-selection, read-only, atomic batch report PDF.

Never creates work items, sends messages, mutates student records or edits an
existing PDF. Uses the V3583/V3584 report builders for per-student evidence.
PyMuPDF (fitz) is required only when this optional batch feature is invoked.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import os
import shutil
import sqlite3
import tempfile

from services.professional_pdf_v3583 import get_report_snapshot, export_professional_pdf, _register_fonts
from services.integrated_report_v3584 import read_integrated_report, export_integrated_pdf

MAX_BATCH_STUDENTS = 60
TEMPLATES = ('veli', 'ogretmen', 'butunlesik')


@dataclass(frozen=True)
class BatchRow:
    student_id: int
    name: str
    group: str
    done: int
    total: int
    percent: float | None
    warnings: int


def active_students(con: sqlite3.Connection) -> tuple[tuple[int, str, str, str], ...]:
    """ID, name, primary-group, subgroup; no silent inclusion of inactive rows."""
    rows = con.execute('SELECT id, COALESCE(ad, \'\'), COALESCE(soyad, \'\'), '
                       'COALESCE(ana_grup, \'\'), COALESCE(alt_grup, \'\') '
                       'FROM ogrenci WHERE COALESCE(aktif, 1)=1 ORDER BY ad COLLATE NOCASE, soyad COLLATE NOCASE, id').fetchall()
    return tuple((int(r[0]), ' '.join([str(r[1]),str(r[2])]).strip() or f'Öğrenci #{r[0]}',
                  str(r[3]).strip(), str(r[4]).strip()) for r in rows)


def validate_selection(con, student_ids, *, maximum=MAX_BATCH_STUDENTS) -> tuple[int, ...]:
    if not isinstance(student_ids, (list, tuple)) or not student_ids or len(student_ids) > maximum:
        raise ValueError(f'En az 1, en fazla {maximum} öğrenci seçin.')
    if any(type(sid) is not int or sid <= 0 for sid in student_ids):
        raise ValueError('Geçersiz öğrenci kimliği; yalnızca gerçek sayısal ID kullanılabilir.')
    if len(set(student_ids)) != len(student_ids):
        raise ValueError('Aynı öğrenci iki kez seçilemez.')
    valid = {r[0] for r in active_students(con)}
    if any(sid not in valid for sid in student_ids):
        raise ValueError('Seçimde pasif veya kaydı olmayan öğrenci var. Listeyi yenileyin.')
    return tuple(student_ids)


def _prepare(con, ids, period_days, template, today):
    if template not in TEMPLATES:
        raise ValueError('Rapor türü desteklenmiyor.')
    if period_days not in (7, 30, 90):
        raise ValueError('Desteklenen dönem: 7, 30 veya 90 gün.')
    ids = validate_selection(con, ids)
    snapshots, summaries = [], []
    for sid in ids:
        report = (read_integrated_report(con, sid, period_days=period_days, reference_day=today)
                  if template == 'butunlesik' else
                  get_report_snapshot(con, sid, period_days, reference_day=today))
        s = report.homework if template == 'butunlesik' else report
        # Do not trust a returned report that belongs to another student.
        if s.student_id != sid:
            raise ValueError('Öğrenci eşleşmesi bozuk; toplu PDF oluşturulmadı.')
        summaries.append(BatchRow(sid, s.name, s.group, s.done, s.total,
                                  s.evidence.percent, len(s.warnings)))
        snapshots.append(report)
    return tuple(snapshots), tuple(summaries)


def _make_cover(path: Path, rows: tuple[BatchRow,...], template, days, today):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    normal, bold = _register_fonts()
    ink = colors.HexColor('#17263e')
    styles = {
        'title': ParagraphStyle('b86-title', fontName=bold, fontSize=20, leading=26, textColor=ink),
        'normal': ParagraphStyle('b86-normal', fontName=normal, fontSize=9, leading=14, textColor=ink),
        'cell': ParagraphStyle('b86-cell', fontName=normal, fontSize=7.5, leading=11, textColor=ink),
        'head': ParagraphStyle('b86-head', fontName=bold, fontSize=8, leading=12, textColor=ink),
    }
    def p(s, k='cell'):
        return Paragraph(escape(str(s)),styles[k])
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=42, rightMargin=42,
                            topMargin=42, bottomMargin=43, title='KoçPilot 360 - Toplu Rapor İçindekiler')
    kind = {'veli':'Veli Bilgilendirme','ogretmen':'Öğretmen Gelişim','butunlesik':'Bütünleşik Öğrenci 360'}[template]
    pages = [p('KOÇPİLOT 360 / RAPOR MERKEZİ','head'), Spacer(1,7),
             p('Toplu Rapor · İçindekiler','title'), Spacer(1,7),
             p(f'{kind}  ·  Son {days} gün  ·  {today:%d.%m.%Y}  ·  {len(rows)} öğrenci','normal'),
             Spacer(1,13),p('Yalnızca açıkça seçilmiş aktif öğrenciler bulunur. Bir öğrencinin verisi '
                           'doğrulanamazsa tüm çıktı durdurulur. Ödev tamamlama sınav başarısı değildir.', 'normal'),
             Spacer(1,13)]
    tab = [[p(v,'head') for v in ('ID','Öğrenci / Grup','Tamamlanan','Ödev oranı')]]
    for r in rows:
        value = 'Veri yok' if r.percent is None else f'%{r.percent:.1f}'
        tab.append([p(r.student_id),p(f'{r.name}  ·  {r.group}'),p(f'{r.done}/{r.total}'),p(value)])
    table=Table(tab, colWidths=[42, 270, 92, 91], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0), colors.HexColor('#dbeafe')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f4f7fb')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.3, colors.HexColor('#dce5f0'))]))
    pages += [table, Spacer(1,12),p('Gizlilik: Bu rapor kişisel öğrenci verileri içerir. '
                  'Paylaşım öncesi alıcı ve erişim yetkisini kontrol edin.', 'normal')]
    doc.build(pages)


def export_batch_pdf(con, student_ids, output_path, *, period_days=30, template='veli',
                     reference_day=None, progress=None) -> tuple[str, tuple[BatchRow, ...]]:
    """Create one combined PDF with cover + exact student selection.

    All-or-nothing. Existing destination NEVER overwritten. DB never modified.
    Callback may raise for cancellation. No successful file is left on failure.
    """
    dest = Path(output_path).expanduser().absolute()
    if dest.suffix.lower() != '.pdf' or not dest.parent.is_dir():
        raise ValueError('Geçerli PDF kayıt konumu seçin.')
    if dest.exists():
        raise FileExistsError('Bu adda rapor zaten mevcut; üzerine yazılmadı.')
    today = reference_day or date.today()
    if type(today) is not date:
        raise ValueError('Rapor tarihi geçersiz.')
    snaps, summaries = _prepare(con, student_ids, period_days, template, today)
    # Never persist temporary student reports in the user's documents folder.
    with tempfile.TemporaryDirectory(prefix='kocpilot_batch_') as td:
        home = Path(td)
        _make_cover(home/'cover.pdf', summaries, template, period_days, today)
        for i, report in enumerate(snaps):
            if progress:
                progress(i, len(snaps))
            single = home/f'student_{i:03d}.pdf'
            if template == 'butunlesik':
                export_integrated_pdf(report, str(single))
            else:
                export_professional_pdf(report, str(single), template)
        if progress:
            progress(len(snaps), len(snaps))
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError('Toplu PDF için PyMuPDF gerekli. Bu isteğe bağlı bileşeni kurun.') from exc
        merged = home/'merged.pdf'
        with fitz.open() as pdf:
            for source in [home/'cover.pdf'] + [home/f'student_{i:03d}.pdf' for i in range(len(snaps))]:
                with fitz.open(str(source)) as child:
                    if child.page_count <= 0:
                        raise ValueError('Öğrenci PDF sayfası boş.')
                    pdf.insert_pdf(child)
            pdf.set_metadata({'title':'KoçPilot 360 - Toplu Öğrenci Raporu', 'author':'KoçPilot 360'})
            pdf.save(str(merged), garbage=3, deflate=True)
        # V3.5.87: publish only a *complete* report. In V3586 a caller could
        # briefly observe a partially copied destination while export ran.
        # Stage in the same directory/filesystem with private permissions;
        # a hard link publishes the completed inode atomically and with
        # no-overwrite semantics (including a pre-existing symlink).
        # Fail closed on filesystems without hard-link support: we must not
        # expose an incomplete or silently overwritten personal-data PDF.
        fd, staging_name = tempfile.mkstemp(
            prefix='.kocpilot_report_', suffix='.part', dir=str(dest.parent))
        staging = Path(staging_name)
        try:
            with os.fdopen(fd, 'wb') as out, open(merged, 'rb') as src:
                shutil.copyfileobj(src, out, 256 * 1024)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.link(str(staging), str(dest))
            except FileExistsError:
                raise FileExistsError('Bu adda rapor zaten mevcut; üzerine yazılmadı.') from None
            except OSError as exc:
                raise OSError('Bu hedef diskte güvenli/atomik PDF kaydı desteklenmiyor. '
                              'Lütfen yerel bir klasör seçin. Eski dosyalar korunur.') from exc
        finally:
            staging.unlink(missing_ok=True)
    return str(dest), summaries
