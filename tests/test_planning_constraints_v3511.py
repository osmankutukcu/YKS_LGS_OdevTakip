"""Planning regressions; runnable without PyQt6 or external services."""
import json
from datetime import date, timedelta
from pathlib import Path
import sys
import types
import unittest
from tempfile import TemporaryDirectory

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from services.planning_constraints import (
    availability_for_week, find_slot, free_minutes, hhmm, parse_details,
    parse_block, serialize_details,
)
from services.plan_profile_store import save_profiles, load_profiles

if 'PyQt6' not in sys.modules:
    try:
        import PyQt6
    except ImportError:
        qt = types.ModuleType('PyQt6')
        for sub_name, names in {
            'QtPrintSupport': ('QPrinter',),
            'QtGui': ('QTextDocument', 'QPageSize'),
            'QtCore': ('QUrl',),
        }.items():
            mod = types.ModuleType('PyQt6.' + sub_name)
            for name in names:
                setattr(mod, name, type(name, (), {}))
            sys.modules[mod.__name__] = mod
        sys.modules['PyQt6'] = qt

from services.smart_calendar import SmartCalendarService


def sample(**overrides):
    data = {
        'planner_version': 2, 'school_by_day': {
            str(i): ['08:30', '15:40'] for i in range(5)
        },
        'wake': '07:00', 'sleep': '22:00',
        'blocks': ['Hafta İçi Her Gün [17:00-19:00] Kurs',
                   'Pazartesi [16:00-18:00] Özel Ders'],
        'max': 180, 'weekend_mode': 'Hafif', 'empty': 'Pazar',
        'biorhythm': '⚖️ Standart Dengeli Dağılım',
        'focus': 'Fizik',
    }
    data.update(overrides)
    return data


class ConstraintTests(unittest.TestCase):
    def test_repeated_blocks_overlap_once(self):
        windows = availability_for_week(sample())
        monday = windows[0]
        self.assertEqual(monday, [(420, 510), (940, 960), (1140, 1320)])
        self.assertEqual(free_minutes(monday), 290)
        self.assertEqual(windows[6], [])

    def test_weekend_and_every_day_rules(self):
        b = sample(school_by_day={}, blocks=[
            'Hafta Sonu [10:00-11:00] Kurs', 'Her Gün [12:00-13:00] Yemek'], empty='Yok')
        windows = availability_for_week(b)
        self.assertEqual(free_minutes(windows[0]), 840)
        self.assertEqual(free_minutes(windows[5]), 780)

    def test_day_specific_sleep_wake_school_buffer(self):
        data = sample(
            school_by_day={'0': ['08:00', '14:00']}, blocks=[], empty='Yok',
            wake='07:00', sleep='23:00', after_school_buffer=45,
            day_overrides={'0': {'wake': '10:00', 'sleep': '21:00', 'max': 60}}
        )
        windows = availability_for_week(data)
        self.assertEqual(windows[0], [(14 * 60 + 45, 21 * 60)])
        self.assertEqual(windows[1], [(7 * 60, 23 * 60)])

    def test_invalid_times_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            availability_for_week(sample(wake='23:00', sleep='07:00'))
        with self.assertRaises(ValueError):
            parse_block('Salı [19:00-17:00] Yanlış')
        with self.assertRaises(ValueError):
            availability_for_week(sample(blocks=['Hayalî Gün [12:00-14:00]']))

    def test_slot_is_real_and_has_gap(self):
        windows = [(600, 900)]
        first = find_slot(windows, [], 60)
        second = find_slot(windows, [first], 60)
        self.assertEqual(first, (600, 660))
        self.assertEqual(second, (670, 730))
        self.assertEqual(find_slot([(600, 630)], [], 45), None)

    def test_v2_json_roundtrip(self):
        data = sample(note='Özel: Matematik || Geometri')
        self.assertEqual(parse_details(serialize_details(data))['note'], data['note'])

    def test_store_atomic_and_readable(self):
        with TemporaryDirectory() as root:
            target = Path(root) / 'profiles.json'
            save_profiles({'ABC': sample()}, target)
            self.assertEqual(load_profiles(target)['ABC']['max'], 180)
            self.assertEqual(list(Path(root).glob('*.tmp')), [])


class CalendarTests(unittest.TestCase):
    def _plan(self, data, tasks):
        encoded = serialize_details(data)
        normalized = SmartCalendarService._normalize_tasks(tasks)
        profile = SmartCalendarService._extract_profile(encoded, tasks, normalized)
        days = SmartCalendarService._build_days(profile)
        SmartCalendarService._smart_distribute(normalized, days, profile)
        return days, profile, SmartCalendarService._build_html('Öğrenci <A>', encoded, days, profile), normalized

    def test_holiday_capacity_schedule_and_no_collisions(self):
        tasks = [{'ders': 'Fizik', 'konu': f'Konular {i}', 'kitap': 'Kaynak', 'sure': 45} for i in range(8)]
        days, profile, html, normalized = self._plan(sample(), tasks)
        self.assertIn('Öğrenci &lt;A&gt;', html)
        self.assertEqual(sum(len(d.tasks) for d in days) + len(profile['unassigned']), len(normalized))
        for d in days:
            self.assertLessEqual(d.total_minutes, d.day_cap)
            if d.date_.weekday() == 6:
                self.assertFalse(d.tasks)
            for _, start, end in d.appointments:
                self.assertTrue(any(a <= start and end <= b for a, b in d.windows))
            times = sorted((s, e) for _, s, e in d.appointments)
            for (_, end), (nxt, _) in zip(times, times[1:]):
                self.assertGreaterEqual(nxt - end, 10)

    def test_zero_availability_preserves_unassigned(self):
        data = sample(school_by_day={}, wake='07:00', sleep='07:10',
                      blocks=[], empty='Yok', max=60)
        tasks = [{'ders': 'Matematik', 'konu': 'Test', 'sure': 45}]
        days, profile, html, norm = self._plan(data, tasks)
        self.assertEqual(sum(d.total_minutes for d in days), 0)
        self.assertEqual(len(profile['unassigned']), len(norm))
        self.assertIn('KAPASİTE AŞIMI', html)
        self.assertIn('Matematik', html)

    def test_deadline_kept_and_unassigned_if_past(self):
        yesterday = date.today() - timedelta(days=1)
        tasks = [{'ders': 'Kimya', 'konu': 'Asit', 'sure': 40, 'deadline': yesterday.isoformat()}]
        days, profile, html, norm = self._plan(sample(), tasks)
        self.assertFalse(any(d.tasks for d in days))
        self.assertEqual(len(profile['unassigned']), 1)

    def test_per_day_max_is_strict(self):
        data = sample(school_by_day={}, blocks=[], empty='Yok', max=180,
                      day_overrides={str(i): {'wake': '08:00', 'sleep': '20:00',
                                             'max': (0 if i == 0 else 40)} for i in range(7)})
        tasks = [{'ders': 'Tarih', 'konu': f'Konu {i}', 'sure': 25} for i in range(14)]
        days, profile, html, norm = self._plan(data, tasks)
        for day in days:
            self.assertLessEqual(day.total_minutes, 40)
            if day.date_.weekday() == 0:
                self.assertEqual(day.total_minutes, 0)
        self.assertEqual(sum(len(d.tasks) for d in days) + len(profile['unassigned']), len(norm))

    def test_html_untrusted_fields_are_escaped(self):
        data = sample(school_by_day={}, blocks=[], empty='Yok')
        tasks = [{'ders': '<img src=x>', 'konu': '<script>evil</script>',
                  'kitap': '<b>kitap</b>', 'sure': 30}]
        days, profile, html, norm = self._plan(data, tasks)
        self.assertNotIn('<script>evil</script>', html)
        self.assertIn('&lt;script&gt;evil&lt;/script&gt;', html)

    def test_weekend_custom_school_and_max_not_exceeded(self):
        data = sample(school_by_day={'5': ['08:30', '18:00']}, blocks=[], empty='Yok', max=30)
        tasks = [{'ders':'TYT Matematik', 'konu':'Problemler', 'sure': 25} for _ in range(15)]
        days, profile, _, norm = self._plan(data, tasks)
        for d in days:
            self.assertLessEqual(d.total_minutes, 30)
            if d.date_.weekday() == 5:
                self.assertFalse(any(s < 18*60 and e > 8*60+30 for _, s,e in d.appointments))


if __name__ == '__main__':
    unittest.main()
