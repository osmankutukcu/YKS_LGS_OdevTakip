# -*- coding: utf-8 -*-
"""KoçPilot 360 / V3.5.83 -- opt-in professional, read-only PDF reports.

This is deliberately independent of the existing parent_report generator.
Neither the database nor any original PDF template is modified.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import os
import sqlite3
import tempfile

from services.performance_evidence_v14 import DONE, OPEN, TRANSFERRED, _date
from services.report_evidence_v3582 import completion_evidence


@dataclass(frozen=True)
class ReportSnapshot:
    student_id: int
    name: str
    group: str
    as_of: date
    period_days: int
    period_start: date
    total: int
    done: int
    overdue_in_period: int
    overdue_all: int
    pending: int
    by_subject: tuple[tuple[str, int, int], ...]
    shadow_rows: int
    unknown_rows: int
    undated_rows: int
    excluded_rows: int
    source: str = 'odev / odev_satir, odev_kume (birincil kayıt)' 

    @property
    def evidence(self):
        return completion_evidence(self.done, self.total)

    @property
    def warnings(self) -> tuple[str, ...]:
        notices = []
        if self.shadow_rows:
            notices.append(f'{self.shadow_rows} ikincil kaynak satırı mükerrer sayımı önlemek için dışarıda tutuldu.')
        if self.unknown_rows:
            notices.append(f'{self.unknown_rows} görevde tanınmayan durum bulundu; hesaplamaya alınmadı.')
        if self.undated_rows:
            notices.append(f'{self.undated_rows} görevde geçerli teslim tarihi yok; dönem oranına alınmadı.')
        if self.excluded_rows:
            notices.append(f'{self.excluded_rows} silinmiş / aktarılmış / iptal edilmiş görev hesaplamaya alınmadı.')
        if self.total == 0:
            notices.append('Seçilen dönemde teslim tarihi gelen, değerlendirilebilir görev kaydı bulunamadı.')
        elif self.total < 5:
            notices.append('Örneklem küçüktür (5 görevden az); oran genellenmemelidir.')
        return tuple(notices)

    @property
    def suggestion(self) -> str:
        if not self.total:
            return 'Önce görev kaydı ve teslim tarihleri kontrol edilmelidir.'
        if self.unknown_rows or self.shadow_rows:
            return 'İlk adım olarak görevlerin kaynak ve durum kayıtlarını doğrulayın.'
        if self.overdue_all:
            return 'Gecikmiş açık görevleri öğrenciyle doğrulayın; uygulanabilir bir telafi sırası belirleyin.'
        if self.total < 5:
            return 'Yeni gözlemler birikene kadar performans hükmü vermeyin; takip edin.'
        if (self.evidence.percent or 0) < 60:
            return 'Tamamlanmayan görevleri ve olası engelleri öğrenciyle görüşün.'
        return 'Düzenli takibi sürdürün; sınav başarısını ayrı ölçümle değerlendirin.'


def _table_cols(con, table):
    if table not in {'odev', 'odev_satir', 'ogrenci', 'odev_kume'}:
        raise ValueError('Geçersiz tablo')
    return {str(row[1]) for row in con.execute(f'PRAGMA table_info({table})')}


def _rows(con, table, student_id):
    cols = _table_cols(con, table)
    required = {'id', 'kume_id', 'ogrenci_id', 'ders', 'durum'}
    if not required.issubset(cols):
        raise ValueError(f'{table} tablosunda gerekli alanlar yok: {sorted(required - cols)}')
    columns = ', '.join(('d.' + col if col in cols else 'NULL') + ' AS ' + col
                        for col in ('silindi', 'aktarildi'))
    statement = (f'SELECT d.id, d.kume_id, d.ders, d.durum, {columns}, k.bitis_tarihi '
                 f'FROM {table} d JOIN odev_kume k '
                 'ON k.id=d.kume_id AND k.ogrenci_id=d.ogrenci_id '
                 'WHERE d.ogrenci_id=?')
    cur = con.execute(statement, (student_id,))
    names = [item[0] for item in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def get_report_snapshot(con: sqlite3.Connection, student_id: int,
                        period_days: int = 30, reference_day: date | None = None) -> ReportSnapshot:
    """Read-only student report. Never merge unverified shadow rows from same group.

    Percentage is a *current-state, due-date cohort*, not a historic snapshot.
    Future deadlines do not inflate the denominator. SQL is parameterized.
    """
    if period_days not in (7, 30, 90):
        raise ValueError('Desteklenen dönemler: 7, 30 veya 90 gündür.')
    today = reference_day or date.today()
    start = today - timedelta(days=period_days - 1)
    cur = con.execute('SELECT id, ad, soyad, COALESCE(ana_grup, \'\'), '
                      'COALESCE(alt_grup, \'\') FROM ogrenci WHERE id=?', (student_id,))
    student = cur.fetchone()
    if not student:
        raise ValueError('Öğrenci bulunamadı.')
    name = ' '.join(str(v or '').strip() for v in student[1:3]).strip() or f'Öğrenci #{student_id}'
    group = ' / '.join(str(v).strip() for v in student[3:5] if str(v).strip()) or 'Belirtilmedi'

    groups = defaultdict(lambda: {'odev': [], 'odev_satir': []})
    excluded = 0
    for table in ('odev', 'odev_satir'):
        for rec in _rows(con, table, student_id):
            status = str(rec.get('durum') or '').strip().lower()
            if rec.get('silindi') or rec.get('aktarildi') or status in TRANSFERRED:
                excluded += 1
                continue
            groups[rec['kume_id']][table].append(rec)

    active = []
    shadow = 0
    for group_rec in groups.values():
        core, secondary = group_rec['odev'], group_rec['odev_satir']
        if core and secondary:
            shadow += len(secondary)
        active.extend(core if core else secondary)

    total = done = overdue = pending = overdue_all = undated = unknown = 0
    by_subject = defaultdict(lambda: [0, 0])
    for row in active:
        status = str(row.get('durum') or '').strip().lower()
        if status not in DONE and status not in OPEN:
            unknown += 1
            continue
        due = _date(row.get('bitis_tarihi'))
        if due is None:
            undated += 1
            continue
        is_done = status in DONE
        if not is_done and due < today:
            overdue_all += 1
        if not start <= due <= today:
            continue
        subject = str(row.get('ders') or '').strip() or 'Ders belirtilmemiş'
        by_subject[subject][1] += 1
        total += 1
        if is_done:
            done += 1
            by_subject[subject][0] += 1
        else:
            pending += 1
            if due < today:
                overdue += 1

    subject_rows = tuple((k, v[0], v[1]) for k, v in sorted(
        by_subject.items(), key=lambda x: (-x[1][1], x[0].casefold())))
    return ReportSnapshot(int(student[0]), name, group, today, period_days, start,
                          total, done, overdue, overdue_all, pending, subject_rows,
                          shadow, unknown, undated, excluded)


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    root = Path(__file__).resolve().parents[1]
    regular = root / 'fonts' / 'DejaVuSans.ttf'
    bold = root / 'fonts' / 'DejaVuSans-Bold.ttf'
    if not regular.is_file() or not bold.is_file():
        raise FileNotFoundError('Türkçe PDF fontları kurulumda bulunamadı; rapor üretilmedi.')
    for name, file in (('KocPilotReportRegular', regular), ('KocPilotReportBold', bold)):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(file)))
    return 'KocPilotReportRegular', 'KocPilotReportBold'


def _make_pdf(snapshot: ReportSnapshot, target_path: str, template: str):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
    )

    regular, bold = _register_fonts()
    navy = colors.HexColor('#14243f')
    muted = colors.HexColor('#55667d')
    blue = colors.HexColor('#2463d9')
    green = colors.HexColor('#087b65')
    border = colors.HexColor('#dde5f0')
    pale = colors.HexColor('#f3f7fb')
    doc = SimpleDocTemplate(target_path, pagesize=A4, leftMargin=42, rightMargin=42,
                            topMargin=34, bottomMargin=42, title='KoçPilot 360 - Profesyonel Rapor',
                            author='KoçPilot 360')
    page_width = A4[0] - 84
    styles = {
        'eyebrow': ParagraphStyle('report-eyebrow', fontName=bold, fontSize=9, leading=14, textColor=blue),
        'header': ParagraphStyle('report-title', fontName=bold, fontSize=20, leading=28, textColor=navy),
        'name': ParagraphStyle('report-name', fontName=bold, fontSize=12, leading=19, textColor=navy),
        'body': ParagraphStyle('report-body', fontName=regular, fontSize=8.5, leading=14, textColor=navy),
        'hint': ParagraphStyle('report-hint', fontName=regular, fontSize=7.4, leading=11.3, textColor=muted),
        'section': ParagraphStyle('report-section', fontName=bold, fontSize=11, leading=16, textColor=navy, spaceBefore=15, spaceAfter=7),
        'metric': ParagraphStyle('report-metric', fontName=bold, fontSize=15, leading=19, textColor=navy, alignment=TA_CENTER),
        'metricLabel': ParagraphStyle('report-metric-label', fontName=regular, fontSize=7.2, leading=11, textColor=muted, alignment=TA_CENTER),
        'cell': ParagraphStyle('report-cell', fontName=regular, fontSize=8, leading=12, textColor=navy),
        'cellbold': ParagraphStyle('report-cell-bold', fontName=bold, fontSize=8, leading=12, textColor=navy),
    }
    def para(text, style='body'):
        return Paragraph(escape(str(text)), styles[style])

    story = []
    title = 'Veli Bilgilendirme Raporu' if template == 'veli' else 'Öğretmen Gelişim Raporu'
    story.extend([para('KOÇPİLOT 360  /  RAPORLAMA MERKEZİ', 'eyebrow'), Spacer(1, 5),
                  para(title, 'header'), Spacer(1, 8)])
    period_label = f'{snapshot.period_start:%d.%m.%Y} - {snapshot.as_of:%d.%m.%Y}'
    info = Table([
        [para(snapshot.name, 'name'), para(period_label, 'cellbold')],
        [para('Grup: ' + snapshot.group, 'hint'), para(f'{snapshot.period_days} gün / rapor tarihi: {snapshot.as_of:%d.%m.%Y}', 'hint')],
    ], colWidths=[page_width * .55, page_width * .45])
    info.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), pale),
                              ('BOX', (0,0), (-1,-1), 0.7, border),
                              ('TOPPADDING', (0,0), (-1,-1), 8),
                              ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                              ('LEFTPADDING', (0,0), (-1,-1), 12)]))
    story.extend([info, Spacer(1, 15)])
    pct = snapshot.evidence.percent
    items = (
        ('Ödev tamamlama', 'Veri yok' if pct is None else f'%{pct:.1f}'),
        ('Tamamlanan / Toplam', f'{snapshot.done} / {snapshot.total}'),
        ('Dönemde geciken', str(snapshot.overdue_in_period)),
        ('Açık geciken (tümü)', str(snapshot.overdue_all)),
    )
    metric_columns = []
    for label, value in items:
        metric_columns.append(Table([[para(value, 'metric')], [para(label, 'metricLabel')]],
                                    colWidths=[page_width / 4 - 14]))
    cards = Table([metric_columns],
                  colWidths=[page_width / 4] * 4)
    cards.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eaf3ff')),
                               ('BOX', (0,0), (-1,-1), .6, border),
                               ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                               ('TOPPADDING', (0,0), (-1,-1), 11),
                               ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
    story.append(cards)

    class _CompletionBar(Flowable):
        """Compact visual gauge; NULL data never becomes a 0-percent gauge."""
        def __init__(self, value):
            super().__init__()
            self.width, self.height = page_width, 10
            self.value = value
        def draw(self):
            self.canv.setFillColor(colors.HexColor('#e2e8f0'))
            self.canv.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
            if self.value is not None and self.value > 0:
                self.canv.setFillColor(blue if self.value < 80 else green)
                self.canv.roundRect(0, 0, self.width * max(0, min(100, self.value)) / 100,
                                    self.height, 5, fill=1, stroke=0)
    story.append(Spacer(1, 8))
    story.append(_CompletionBar(pct))
    story.append(para('Derse Göre Ödev Takibi', 'section'))
    rows = [[para('Ders', 'cellbold'), para('Tamamlanan / Toplam', 'cellbold'),
             para('Tamamlama', 'cellbold')]]
    # Veli özeti her veri hacminde tek sayfada kalacak şekilde sınırlıdır.
    # Tam ders dökümü, ek sayfalı öğretmen şablonundadır.
    maximum = 5 if template == 'veli' else 30
    for subj, completed, count in snapshot.by_subject[:maximum]:
        display_subject = subj if template != 'veli' or len(subj) <= 48 else subj[:45].rstrip() + '...'
        rows.append([para(display_subject, 'cell'), para(f'{completed} / {count}', 'cell'),
                     para(f'%{(100 * completed / count):.1f}', 'cell')])
    if not snapshot.by_subject:
        rows.append([para('Seçilen dönem için ders bazlı kayıt bulunamadı.', 'hint'), '', ''])
    subjects = Table(rows, colWidths=[page_width * .48, page_width * .29, page_width * .23], repeatRows=1)
    subjects.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dbeafe')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, pale]),
        ('LINEBELOW', (0,0), (-1,0), .8, border),
        ('BOX', (0,0), (-1,-1), .6, border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 9),
    ]))
    story.append(subjects)
    if len(snapshot.by_subject) > maximum:
        story.append(Spacer(1, 5))
        story.append(para(f'{len(snapshot.by_subject) - maximum} ders daha vardır; tüm dersler öğretmen şablonunda gösterilir.', 'hint'))

    story.append(para('Öğretmenin Takip Gündemi', 'section'))
    story.append(para(snapshot.suggestion))
    story.extend([Spacer(1, 9), para('Ölçüm ve veri güvenilirliği', 'section')])
    if snapshot.warnings:
        for message in snapshot.warnings:
            story.append(para('• ' + message, 'hint'))
            story.append(Spacer(1, 3))
    else:
        story.append(para('Kayıt kalitesine ilişkin ek uyarı tespit edilmedi.', 'hint'))
    story.extend([Spacer(1, 6), para('Not: Yüzdeler teslim tarihi gelen ödevlerin bugünkü kayıt durumunu gösterir. '
                                    'Sınav başarısı, net veya akademik yeterlilik anlamına gelmez.', 'hint')])

    if template == 'ogretmen':
        story.append(PageBreak())
        story.append(para('Analiz ve İzleme Notları', 'header'))
        story.append(Spacer(1, 8))
        story.append(para('Gösterge açıklamaları', 'section'))
        for head, body in [
            ('Tamamlanan / Toplam', 'Seçilen dönemde teslim tarihi gelmiş, geçerli durumdaki görevler üzerinden hesaplanır.'),
            ('Dönemde geciken', 'Seçilen dönemde teslim tarihi geçmiş fakat tamamlanmamış görev sayısıdır.'),
            ('Açık geciken (tümü)', 'Seçilen dönemin dışında kalan eski açık gecikmeler dahil, toplam gecikmiş açık görev sayısıdır.'),
            ('Veri kaynağı', 'Aynı kümede odev ve odev_satir bulunursa birincil odev satırları kullanılır.'),
            ('Tarihsel karşılaştırma', 'Bu çıktı geçmişe ait dondurulmuş durum fotoğrafı değildir; geçerli kayıtların bugünkü durumunu raporlar.'),
        ]:
            story.append(para(head, 'cellbold'))
            story.append(para(body, 'hint'))
            story.append(Spacer(1, 6))
        story.append(para('Koçluk görüşmesi için kontrol listesi', 'section'))
        for line in (
            'Öğrencinin tamamlanmayan görevlerini ve mümkünse nedenlerini teyit edin.',
            'Teslim tarihi veya kaynak belirsizliklerini düzeltmeden kesin değerlendirme yapmayın.',
            'Gerekiyorsa mevcut haftalık planı ve ödev yükünü birlikte gözden geçirin.',
            'Sınav neti ve hedef analizi için ilgili modüllerin kendi sonuçlarını ayrıca inceleyin.',
        ):
            story.append(para('□  ' + line, 'body'))
            story.append(Spacer(1, 6))
        story.extend([Spacer(1, 15), para('Öğretmen Notları: _________________________________________________'),
                      Spacer(1, 12), para('_________________________________________________________________')])

    def draw_page(canv, page_doc):
        canv.saveState()
        w, h = A4
        canv.setStrokeColor(border)
        canv.line(42, 32, w - 42, 32)
        canv.setFont(regular, 7)
        canv.setFillColor(muted)
        canv.drawString(42, 20, 'KoçPilot 360  |  Öğrenciye özel, yerel olarak üretilen rapor')
        canv.drawRightString(w - 42, 20, f'Sayfa {page_doc.page}')
        canv.restoreState()
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def export_professional_pdf(snapshot: ReportSnapshot, output_path: str, template: str = 'veli') -> str:
    """Create a PDF without replacing an existing output file.

    The caller must confirm overwrite separately. This function refuses to
    overwrite an existing destination even if called outside the dialog.
    """
    if template not in ('veli', 'ogretmen'):
        raise ValueError('Bilinmeyen rapor şablonu.')
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != '.pdf':
        raise ValueError('PDF uzantılı bir dosya seçin.')
    if not destination.parent.is_dir():
        raise FileNotFoundError('Kayıt klasörü bulunamadı.')
    if destination.exists():
        raise FileExistsError('Bu adda dosya zaten mevcut. Farklı ad seçin.')
    fd, temp_file = tempfile.mkstemp(prefix='.kocpilot_rapor_', suffix='.pdf', dir=str(destination.parent))
    os.close(fd)
    destination_created = False
    try:
        _make_pdf(snapshot, temp_file, template)
        # Avoid clobber even in a race. Exclusive destination creation.
        with open(temp_file, 'rb') as src, open(destination, 'xb') as dst:
            destination_created = True
            while True:
                buf = src.read(256 * 1024)
                if not buf:
                    break
                dst.write(buf)
    except Exception:
        # Remove only a destination this exporter created exclusively.
        if destination_created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            os.unlink(temp_file)
        except OSError:
            pass
    return str(destination)
