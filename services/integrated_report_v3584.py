# -*- coding: utf-8 -*-
"""V3.5.84 - explainable, opt-in, read-only student report bridge.

Uses the existing Student360/V14/V15 and target readers. No business rules are
reimplemented for exam comparison, and no student writes/migrations/network calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import os
import sqlite3
import tempfile

from services.professional_pdf_v3583 import ReportSnapshot, get_report_snapshot, _register_fonts
from services.student360_v16.reader import read_student_overview
from services.student360_v16.advisor import suggestions
from services.target_analysis_v24.student_target import read_saved_target
from services.report_planner_bridge_v3585 import read_planner_evidence
from services.report_integrity_v3590 import audit_student_integrity
from services.report_academic_bridge_v3591 import read_academic_evidence
from services.report_intervention_plan_v3592 import plan_teacher_review


@dataclass(frozen=True)
class SourceSection:
    title: str
    value: str
    source: str
    scope: str
    status: str = 'kayıt'  # kayıt | eksik | doğrulanamadı


@dataclass(frozen=True)
class IntegratedReport:
    homework: ReportSnapshot
    sections: tuple[SourceSection, ...]
    coaching_actions: tuple[str, ...]
    notes: tuple[str, ...]

    def section(self, title: str) -> SourceSection:
        return next(s for s in self.sections if s.title == title)


def _clean(value, cap=420) -> str:
    return ' '.join(str(value or '').split())[:cap]


def _available_table(con, table: str, columns: set[str]) -> bool:
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return False
    return columns.issubset({str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")')})


def read_integrated_report(con: sqlite3.Connection, student_id: int, *,
                           period_days: int = 30, reference_day: date | None = None) -> IntegratedReport:
    """Only same-ID verified inputs; optional source failures remain visible.

    The date scope of V16's exam, target and week-plan readers is NOT presumed
    equal to the selected homework due-date cohort.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği.')
    day = reference_day or date.today()
    if not isinstance(day, date):
        raise ValueError('Rapor tarihi geçersiz.')
    # Fail closed for inactive / missing student rather than accidentally reading
    # another row; existing V3583 reader alone does not check active status.
    identity = con.execute('SELECT id, COALESCE(aktif, 1) FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if not identity or int(identity[1]) != 1:
        raise ValueError('Öğrenci bulunamadı veya aktif değil.')
    hw = get_report_snapshot(con, student_id, period_days, day)
    sections: list[SourceSection] = []
    notes = list(hw.warnings)
    # V3590: separate read-only ownership check. Do not change or substitute
    # legacy PDF numerators, student identity, or due-date period semantics.
    integrity = audit_student_integrity(con, student_id)
    if integrity.state != 'checked':
        notes.append('Ödev kaynak güvenilirliği: ' + (
            'Sahiplik/çift sayım incelemesi gerekli.' if integrity.state == 'review'
            else 'Kısmi veri veya şema; kesin yorum yapılamaz.'))
        notes.extend(integrity.reasons)
    actions: tuple[str, ...] = ()

    # V16's reader validates the exact active student ID and reuses V14/V15
    # without claiming an exam grade from assignment completion percentages.
    try:
        overview = read_student_overview(con, student_id, as_of=day)
        if overview.student_id != student_id or overview.student_name != hw.name:
            raise ValueError('Öğrenci kimlikleri çakışıyor; rapor oluşturulmadı.')
    except (sqlite3.Error, ValueError, TypeError, OverflowError) as exc:
        # Student mismatch is a hard failure, not a recoverable source absence.
        if isinstance(exc, ValueError) and 'kimlikleri çakışıyor' in str(exc):
            raise
        overview = None
        notes.append('Öğrenci 360 / deneme / koçluk özeti okunamadı; bu alanlar rapora alınmadı.')

    if overview is not None:
        evidence = _clean(overview.exam_evidence, 90)
        exam_present = evidence not in ('Yok', '')
        exam_schema = (
            _available_table(con, 'denemeler', {'id', 'tarih', 'tur'})
            and _available_table(con, 'deneme_sonuclari', {'id', 'deneme_id', 'ogrenci_id', 'ders_adi', 'dogru', 'yanlis', 'net'})
        ) or (
            _available_table(con, 'deneme', {'id', 'ogrenci_id', 'tarih', 'tur'})
            and _available_table(con, 'deneme_sonuc', {'id', 'deneme_id', 'ders', 'net'})
        )
        sections.append(SourceSection('Deneme sonuçları',
                (_clean(overview.exam_summary, 260) + ' | Kanıt: ' + (evidence or 'Belirsiz'))
                if exam_schema else 'Deneme kayıt şeması mevcut değil; yokluk veya başarı sonucu çıkarılmadı.',
                'Deneme Sınavları / Öğrenci 360 / V15',
                'Geçerli kayıtlardaki en güncel karşılaştırılabilir sonuç; ödev döneminden bağımsız',
                ('kayıt' if exam_present else 'eksik') if exam_schema else 'doğrulanamadı'))
        if overview.exam_explanation:
            notes.append('Deneme açıklaması: ' + _clean(overview.exam_explanation, 300))
        plan_schema = _available_table(con, 'koc_plan',
                       {'id', 'ogrenci_id', 'baslangic_tarihi', 'bitis_tarihi'})
        sections.append(SourceSection('Koçluk planı',
                (_clean(overview.coaching_plan, 160) +
                f' | Hedef sayısı: {overview.coaching_goals}, program girdisi: {overview.coaching_program_entries}')
                if plan_schema else 'Koçluk planı kayıt tablosu bu veritabanında mevcut değil.',
                'Koçluk Planı / Öğrenci 360 / V16',
                f'{day:%d.%m.%Y} tarihini kapsayan kayıtlı koçluk planı',
                ('eksik' if 'kayıtlı değil' in overview.coaching_plan.casefold() else 'kayıt')
                if plan_schema else 'doğrulanamadı'))
        topic_schema = _available_table(con, 'koc_konu_takip', {'ogrenci_id', 'durum'})
        sections.append(SourceSection('Konu takibi',
                f'{overview.tracked_topics} kayıt / {overview.marked_topics} öğretmen işareti'
                if topic_schema else 'Konu takibi kayıt tablosu mevcut değil.',
                'Koçluk konu takibi / V16',
                'Öğretmen takibi; öğrenmenin kanıtlanması anlamına gelmez',
                ('kayıt' if overview.tracked_topics else 'eksik') if topic_schema else 'doğrulanamadı'))
        notes.extend(_clean(n, 230) for n in overview.source_warnings)
        actions = tuple(_clean(s, 225) for s in suggestions(overview)[:4] if _clean(s, 225))
    else:
        for title, source in (
            ('Deneme sonuçları', 'Deneme Sınavları / V15'),
            ('Koçluk planı', 'Koçluk Planı / V16'),
            ('Konu takibi', 'Koçluk konu takibi / V16'),
        ):
            sections.append(SourceSection(title, 'Veri doğrulanamadı; tahmin yapılmadı.',
                             source, 'İsteğe bağlı modül', 'doğrulanamadı'))

    # V3591: sidecar academic evidence. No inferred cause/effect from exam nets
    # to teacher topic markings, and no changes to any legacy PDF numerators.
    try:
        academic = read_academic_evidence(con, student_id, reference_day=day)
        sections.append(SourceSection('Ders ölçümleri ve konu işaretleri', academic.value,
                        'Deneme Sınavları / V15 + Koçluk konu takibi / V3591',
                        academic.scope, academic.status))
        notes.extend(academic.warnings)
        # V3592 opt-in sidecar: explanatory teacher review, not a diagnosis
        # and not a mutation of earlier coaching or PDF success metrics.
        review = plan_teacher_review(academic)
        sections.append(SourceSection('Öğretmen için kontrollü sonraki adımlar',
                        ' | '.join(f'{i+1}. {step.short}'
                                   for i, step in enumerate(review.steps)),
                        'V3592 öğretmen rehberi / V3591 ders kanıtı',
                        'Öneri; tanı veya otomatik atama değildir. Öğretmen doğrulamalıdır.',
                        'kayıt' if review.level == 'ölçüm var'
                        else 'doğrulanamadı' if review.level == 'önce doğrula' else 'eksik'))
    except (sqlite3.Error, ValueError, TypeError, OverflowError):
        sections.append(SourceSection('Ders ölçümleri ve konu işaretleri',
                        'Ölçüm ve konu kaynağı doğrulanamadı; tahmin üretilmedi.',
                        'Deneme Sınavları / Koçluk', 'Yerel kayıtlar', 'doğrulanamadı'))
        notes.append('Ders ölçümü/konu eşleştirme kaynağı okunamadı; öğretmen kontrolü gerekli.')
        sections.append(SourceSection('Öğretmen için kontrollü sonraki adımlar',
                        'Önce aynı öğrenciye ait sınav ve konu kayıtlarını doğrulayın; '
                        'eksik veya okunamayan kaynaktan otomatik müdahale belirlenmedi.',
                        'V3592 doğrulama rehberi', 'Öğretmen incelemesi', 'doğrulanamadı'))

    # Target columns are optional across supported old databases. Absence must
    # be labeled instead of presenting teacher targets as calculated results.
    if _available_table(con, 'ogrenci', {'hedef_bolum', 'hedef_tyt', 'hedef_ayt', 'hedef_lgs'}):
        try:
            target_label = _clean(read_saved_target(con, student_id), 250)
            lowered = target_label.casefold()
            if 'doğrulanamadı' in lowered or 'okunamadı' in lowered:
                status = 'doğrulanamadı'
            elif 'henüz hedef' in lowered or 'hedef bulunamadı' in lowered:
                status = 'eksik'
            else:
                status = 'kayıt'
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            target_label = 'Kayıtlı hedef alanı okunamadı; hedef tahmin edilmedi.'
            status = 'doğrulanamadı'
            notes.append('Hedef Analizi kaynağı okunamadı; hedef verisi rapora aktarılmadı.')
        sections.append(SourceSection('Kayıtlı hedef', target_label,
                        'Hedef Analizi / V24, ogrenci.hedef_*',
                        'Öğretmen tarafından kaydedilmiş hedef; resmî başarı veya yerleşme tahmini değil', status))
    else:
        sections.append(SourceSection('Kayıtlı hedef', 'Hedef alanları bu veri sürümünde mevcut değil.',
                        'Hedef Analizi / V24', 'Eksik veri şeması', 'doğrulanamadı'))

    # The optional planner bridge reads explicit student-ID mappings only.
    # Read-only summaries cannot prove the student followed the timetable.
    planner = read_planner_evidence(student_id, reference_day=day)
    for title, source, result in (
        ('Haftalık çalışma planı', 'Haftalık Planlayıcı / V2 rutin profili', planner.routine),
        ('Onaylı haftalık plan özeti', 'Haftalık Planlayıcı / ID anahtarlı kayıt', planner.approved_plan),
    ):
        sections.append(SourceSection(title, result.value, source, result.scope, result.status))
        if result.warning:
            notes.append(result.warning)
    if not actions:
        actions = (hw.suggestion,)
    # Keep warnings deterministic and avoid repeating V14 / V3583 notices.
    return IntegratedReport(hw, tuple(sections), actions,
                            tuple(dict.fromkeys(_clean(n, 340) for n in notes if _clean(n, 340))))


def preview_text(result: IntegratedReport) -> str:
    """Student-scoped evidence summary for review before PDF export."""
    s = result.homework
    pct = s.evidence.percent
    lines = [
        'BÜTÜNLEŞİK ÖĞRENCİ RAPORU · PİLOT',
        f'{s.name} (ID: {s.student_id}) | Grup: {s.group}',
        f'ÖDEV DÖNEMİ: {s.period_start:%d.%m.%Y}–{s.as_of:%d.%m.%Y}',
        f'Ödev: {s.done}/{s.total} | Oran: {"Veri yok" if pct is None else f"%{pct:.1f}"}',
        f'Dönem içinde geciken: {s.overdue_in_period} | Açık geciken (tüm dönemler): {s.overdue_all}',
        'Ödev tamamlama akademik başarı veya sınav neti değildir.',
    ]
    for section in result.sections:
        lines += ['', f'{section.title.upper()} [{section.status}]',
                  section.value, f'Kaynak: {section.source}',
                  f'Kapsam: {section.scope}']
    lines += ['', 'ÖĞRETMENİN KONTROLÜNE SUNULAN ÖNERİLER']
    lines += ['• ' + action for action in result.coaching_actions]
    if result.notes:
        lines += ['', 'KANIT VE VERİ KALİTESİ UYARILARI']
        lines += ['• ' + warning for warning in result.notes[:8]]
    lines += ['', 'Rapor, yerel kayıtlar üzerinden üretilir; otomatik ödev veya plan oluşturmaz.']
    return '\n'.join(lines)


def _render_pdf(report: IntegratedReport, filepath: str) -> None:
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, KeepTogether
    from reportlab.lib.enums import TA_CENTER
    from reportlab.graphics.shapes import Drawing, Rect

    regular, bold = _register_fonts()
    navy, blue, gray = (colors.HexColor(x) for x in ('#17263e', '#1c64d1', '#53657c'))
    line, light = (colors.HexColor(x) for x in ('#dde6f1', '#f0f5fc'))
    pwidth = A4[0] - 90
    styles = {
        'mark': ParagraphStyle('ir-mark', fontName=bold, fontSize=8, leading=11, textColor=blue),
        'title': ParagraphStyle('ir-title', fontName=bold, fontSize=18, leading=25, textColor=navy),
        'sub': ParagraphStyle('ir-sub', fontName=regular, fontSize=9, leading=14, textColor=gray),
        'h': ParagraphStyle('ir-h', fontName=bold, fontSize=10.3, leading=15, textColor=navy, spaceBefore=12, spaceAfter=5),
        'text': ParagraphStyle('ir-text', fontName=regular, fontSize=8.1, leading=12, textColor=navy),
        'small': ParagraphStyle('ir-small', fontName=regular, fontSize=7.2, leading=10.8, textColor=gray),
        'value': ParagraphStyle('ir-value', fontName=bold, fontSize=14, leading=20, textColor=navy, alignment=TA_CENTER),
        'caption': ParagraphStyle('ir-caption', fontName=regular, fontSize=7, leading=11, textColor=gray, alignment=TA_CENTER),
    }
    def p(txt, key='text'):
        return Paragraph(escape(str(txt)), styles[key])

    document = SimpleDocTemplate(filepath, pagesize=A4, leftMargin=45, rightMargin=45,
                                 topMargin=36, bottomMargin=43,
                                 title='KoçPilot 360 - Bütünleşik Öğrenci Raporu',
                                 author='KoçPilot 360')
    data = report.homework
    pct = data.evidence.percent
    content = [p('KOÇPİLOT 360 / RAPORLAMA MERKEZİ', 'mark'), Spacer(1, 6),
               p('Bütünleşik Öğrenci Raporu', 'title'), Spacer(1, 6),
               p(f'{data.name}  ·  Öğrenci ID: {data.student_id}  ·  {data.group}', 'sub'),
               p(f'Ödev dönemi: {data.period_start:%d.%m.%Y} – {data.as_of:%d.%m.%Y} '
                 '  |  Sınav/koçluk kayıtları farklı dönemlerde olabilir.', 'small'), Spacer(1, 14)]
    metrics = [('Ödev tamamlanma', 'Veri yok' if pct is None else f'%{pct:.1f}'),
               ('Tamamlanan / Toplam', f'{data.done}/{data.total}'),
               ('Dönemde geciken', data.overdue_in_period),
               ('Tüm açık geciken', data.overdue_all)]
    cards = []
    for label, value in metrics:
        card = Table([[p(str(value), 'value')], [p(label, 'caption')]], colWidths=[pwidth / 4 - 10])
        cards.append(card)
    row = Table([cards], colWidths=[pwidth / 4] * 4)
    row.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), light),
                             ('BOX', (0,0), (-1,-1), 0.65, line),
                             ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                             ('TOPPADDING', (0,0), (-1,-1), 11),
                             ('BOTTOMPADDING', (0,0), (-1,-1), 11)]))
    content += [row, p('Ders bazlı ödev özeti', 'h')]
    subs = [[p('Ders', 'small'), p('Görev', 'small'), p('Tamamlanma', 'small')]]
    for subject, done, total in data.by_subject[:6]:
        # A visual completion meter uses only the same verified done/total
        # counts; it is NOT a measurement of exam success or mastery.
        ratio = done / total if total else 0
        meter = Drawing(105, 12)
        meter.add(Rect(0, 1, 88, 9, fillColor=line, strokeColor=None, rx=3, ry=3))
        if ratio:
            meter.add(Rect(0, 1, 88 * ratio, 9, fillColor=blue, strokeColor=None, rx=3, ry=3))
        subs.append([p(_clean(subject, 72)), p(f'{done} / {total}'),
                     Table([[meter, p(f'%{100 * ratio:.0f}', 'small')]],
                           colWidths=[94, 34], style=[('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                                         ('LEFTPADDING', (0,0), (-1,-1), 0),
                                                         ('RIGHTPADDING', (0,0), (-1,-1), 0)])])
    if not data.by_subject:
        subs.append([p('Seçilen dönemde tarihli görev bulunamadı.', 'small'), '', ''])
    tab = Table(subs, colWidths=[pwidth * .50, pwidth * .18, pwidth * .32], repeatRows=1)
    tab.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dbeafe')),
                             ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light]),
                             ('BOX', (0,0), (-1,-1), .5, line),
                             ('VALIGN', (0,0), (-1,-1), 'TOP'),
                             ('TOPPADDING', (0,0), (-1,-1), 5),
                             ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    content += [tab]
    if len(data.by_subject) > 6:
        content.append(p(f'{len(data.by_subject)-6} ders daha var. Tam ders dağılımı için Öğretmen Gelişim raporunu kullanın.', 'small'))
    def source_block(section):
        status = {'kayıt': 'Kayıt bulundu', 'eksik': 'Kayıt eksik',
                  'doğrulanamadı': 'Bu raporda doğrulanamadı'}.get(section.status, section.status)
        return KeepTogether([
            p(section.title, 'h'),
            p(status + '  ·  ' + section.value),
            Spacer(1, 3), p('Kaynak: ' + section.source, 'small'),
            p('Kapsam: ' + section.scope, 'small'),
        ])

    content += [Spacer(1, 10), p('Bu sayıların anlamı', 'h'),
                p('Ödev tamamlanma yüzdesi, teslim tarihi gelmiş görevlerin BUGÜNKÜ durumunu gösterir. '
                  'Sınav neti, kazanım düzeyi veya geçmişteki gerçek anlık durum değildir.', 'small'),
                p('Hedef ve deneme bilgileri', 'h')]
    for title in ('Kayıtlı hedef', 'Deneme sonuçları'):
        content.append(source_block(report.section(title)))
    content += [PageBreak(),
                p('Koçluk ve izleme değerlendirmesi', 'title'), Spacer(1, 5),
                p('Diğer modüllerin kapsamı ve veri kaynakları açık biçimde gösterilir.', 'sub')]
    for section in report.sections:
        if section.title not in ('Kayıtlı hedef', 'Deneme sonuçları'):
            content.append(source_block(section))
    content += [p('Öğretmen için izleme gündemi', 'h')]
    for action in report.coaching_actions[:4]:
        content.append(p('• ' + action))
        content.append(Spacer(1, 4))
    if report.notes:
        content.append(p('Veri kalitesi ve sınırlamalar', 'h'))
        for note in report.notes[:8]:
            content.append(p('• ' + note, 'small'))
            content.append(Spacer(1, 3))
    content += [Spacer(1, 10), p('Bu rapor öğretmenin incelemesine sunulur. Başka öğrenciye ait sonuçlar '
                               'kullanılmaz; otomatik ödev, koçluk planı veya hedef kaydı oluşturulmaz.', 'small')]
    def footer(canv, doc):
        canv.saveState()
        canv.setStrokeColor(line)
        canv.line(45, 32, A4[0] - 45, 32)
        canv.setFont(regular, 7)
        canv.setFillColor(gray)
        canv.drawString(45, 20, 'KoçPilot 360  |  Bütünleşik rapor • Yerel, salt okunur kaynaklar')
        canv.drawRightString(A4[0]-45, 20, f'Sayfa {doc.page}')
        canv.restoreState()
    document.build(content, onFirstPage=footer, onLaterPages=footer)


def export_integrated_pdf(report: IntegratedReport, output_path: str) -> str:
    """Atomic no-overwrite save, even if the GUI is bypassed."""
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != '.pdf' or not destination.parent.is_dir():
        raise ValueError('Geçerli bir PDF kayıt konumu seçin.')
    if destination.exists():
        raise FileExistsError('Bu dosya zaten mevcut. Farklı bir ad seçin.')
    fd, temporary = tempfile.mkstemp(prefix='.kocpilot_integrated_', suffix='.pdf', dir=destination.parent)
    os.close(fd)
    created = False
    try:
        _render_pdf(report, temporary)
        with open(temporary, 'rb') as source, open(destination, 'xb') as target:
            created = True
            for chunk in iter(lambda: source.read(256 * 1024), b''):
                target.write(chunk)
        return str(destination)
    except Exception:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass
