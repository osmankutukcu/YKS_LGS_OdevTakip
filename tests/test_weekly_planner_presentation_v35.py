"""Read-only summary and detailed PDF regressions without Qt installation."""
from datetime import date, timedelta
from html import unescape

from services.weekly_planner_presentation_v35 import overview, detailed_section
from services.planning_constraints import serialize_details
from tests.test_planning_constraints_v3511 import SmartCalendarService


def settings(**custom):
    d = {
        'planner_version': 2, 'school_by_day': {str(i): ['08:30','15:40'] for i in range(5)},
        'blocks':['Cumartesi [08:00-16:00] Kurs', 'Pazar [08:00-16:00] Kurs'],
        'after_school_buffer':30, 'after_routine_buffer':20, 'wake':'07:00',
        'sleep':'22:30','max':180,'empty':'Yok','focus':'Fizik','note':'Kısa tekrar.'
    }
    d.update(custom)
    return d


def two_homeworks():
    deadline=(date.today()+timedelta(days=8)).isoformat()
    return [{'ders':'Fizik','kitap':'FİZİK3','konu':'Yay Dalgaları','sure':75,'deadline':deadline},
            {'ders':'Fizik','kitap':'xxx','konu':'Yay Dalgaları','sure':75,'deadline':deadline}]


def test_overview_only_reads_input_and_does_not_invent_placement():
    hw=two_homeworks()
    original=[dict(x) for x in hw]
    result=overview(hw,settings())
    assert result['count']==2 and result['minutes']==150
    assert result['routines']==2 and result['school_days']==5
    assert hw==original
    assert 'placed' not in result and 'success_rate' not in result


def test_details_reflect_actual_appointments_exactly():
    bundle=SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci',two_homeworks(),serialize_details(settings()))
    html=bundle['html']
    assert 'GÜN VE SAAT BAZINDA GÖREVLER' in html
    assert 'PLANLAMADA DİKKATE ALINAN KISITLAR' in html
    assert 'Kısa tekrar' in html
    assert 'FİZİK3' in html and 'xxx' in html
    assert '2 oturum' in html and '150 dk' in html
    for day in bundle['days']:
        for t, start, end in day.appointments:
            assert t.sure == end-start
            assert t.kitap in unescape(html)
    assert '20 dk' in html and '30 dk' in html


def test_html_escapes_untrusted_student_notes_and_book_names():
    hw=[{'ders':'Fizik','kitap':'<b>evil</b>', 'konu':'Dalgalar','sure':30}]
    bundle=SmartCalendarService.create_weekly_plan_data('Örnek', hw,serialize_details(
        settings(note='<script>alert(1)</script>')))
    html=bundle['html']
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '&lt;b&gt;evil&lt;/b&gt;' in html


def test_unassigned_explained_without_dropping_source_tasks():
    hw=[{'ders':'Fizik','konu':f'Konu {i}', 'kitap':'K', 'sure':500}
        for i in range(8)]
    bundle=SmartCalendarService.create_weekly_plan_data('Öğrenci',hw,serialize_details(
        settings(max=30, school_by_day={}, blocks=[], wake='19:00',sleep='20:00')))
    profile=bundle['profile']
    assigned=sum(t.sure for day in bundle['days'] for t in day.tasks)
    remaining=sum(t.sure for t in profile['unassigned'])
    assert assigned+remaining==4000
    assert profile['unassigned']
    assert 'Yerleştirilemeyen görevler:' in bundle['html']
    assert 'Konu 0' in bundle['html']


def test_detailed_section_respects_print_preferences_false():
    s = settings(include_task_details=False, include_constraints=False)
    bundle = SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci', two_homeworks(), serialize_details(s))
    html = bundle['html']
    assert 'GÜN VE SAAT BAZINDA GÖREVLER' not in html
    assert 'PLANLAMADA DİKKATE ALINAN KISITLAR' not in html
    assert detailed_section(bundle['days'], bundle['profile'], s) == ''


def test_detailed_section_task_details_only():
    s = settings(include_task_details=True, include_constraints=False)
    bundle = SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci', two_homeworks(), serialize_details(s))
    html = bundle['html']
    assert 'GÜN VE SAAT BAZINDA GÖREVLER' in html
    assert 'PLANLAMADA DİKKATE ALINAN KISITLAR' not in html


def test_detailed_section_constraints_only():
    s = settings(include_task_details=False, include_constraints=True)
    bundle = SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci', two_homeworks(), serialize_details(s))
    html = bundle['html']
    assert 'GÜN VE SAAT BAZINDA GÖREVLER' not in html
    assert 'PLANLAMADA DİKKATE ALINAN KISITLAR' in html


def test_page_count_single_page_when_details_disabled():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtPrintSupport import QPrinter
    from PyQt6.QtGui import QTextDocument, QPageSize, QPageLayout
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    s = settings(include_task_details=False, include_constraints=False)
    bundle = SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci', two_homeworks(), serialize_details(s))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)

    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    doc.setHtml(bundle['html'])

    assert doc.pageCount() == 1

