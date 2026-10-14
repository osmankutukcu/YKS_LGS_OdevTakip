"""Opt-in equal spread: business rules, no Qt required."""
import unittest
from services.weekly_equal_distribution_v35 import DayLimit, distribute_week


def days(target=330, cap=4):
    return [DayLimit(str(i), target, cap) for i in range(7)]


class TestWeeklyEqualDistribution(unittest.TestCase):
    def test_19_tasks_75_minutes_use_all_seven_days(self):
        data = [{'ders':'fizik', 'dk':75} for _ in range(19)]
        result = distribute_week(data, days())
        self.assertEqual(sum(result.totals), 1425)
        self.assertEqual(len(result.unplaced), 0)
        self.assertEqual(sum(result.counts), 19)
        self.assertTrue(all(n > 0 for n in result.counts))
        self.assertTrue(all(n <= 4 for n in result.counts))
        self.assertTrue(all(t <= 300 for t in result.totals))

    def test_four_hours_target_cannot_create_tasks(self):
        data = [{'ders': 'kimya', 'dk': 75} for _ in range(19)]
        r = distribute_week(data, days(240,4))
        self.assertEqual(sum(r.totals), 1425)
        self.assertIn('255 dk', ' '.join(r.warnings))
        self.assertEqual(len(r.unplaced), 0)

    def test_600_minute_special_day_is_possible(self):
        limits = days(120,3)
        limits[5] = DayLimit('Cumartesi', 600, 12)
        limits[6] = DayLimit('Pazar', 600, 12)
        data = [{'ders':'fizik', 'dk':75} for _ in range(18)]
        r = distribute_week(data, limits)
        self.assertEqual(len(r.unplaced), 0)
        self.assertTrue(r.totals[5] > 120 and r.totals[6] > 120)
        self.assertEqual(sum(r.totals), 1350)

    def test_infeasible_is_reported_not_forced(self):
        r = distribute_week([{'dk':75} for _ in range(19)], days(100,2))
        self.assertGreater(len(r.unplaced), 0)
        self.assertTrue(all(x <= 100 for x in r.totals))
        self.assertTrue(all(n <= 2 for n in r.counts))
        self.assertEqual(sum(r.totals) + len(r.unplaced)*75,1425)

    def test_zero_target_means_day_disabled(self):
        ds = days()
        ds[0] = DayLimit('Pazartesi',0,10)
        r = distribute_week([{'dk':75} for _ in range(8)],ds)
        self.assertEqual(r.counts[0],0)

    def test_invalid_duration_errors_instead_of_guessing(self):
        for invalid in [None,0,-4,'abc',1001]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    distribute_week([{'dk':invalid}],days())

    def test_exact_once_and_deterministic(self):
        data = [{'ders':str(i%3),'dk':45+i%3*15} for i in range(100)]
        first=distribute_week(data,days(900,20),avoid_same_subject=True)
        self.assertEqual(first,distribute_week(data,days(900,20),avoid_same_subject=True))
        ids=[x.task_index for x in first.placements]+list(first.unplaced)
        self.assertEqual(sorted(ids),list(range(100)))

    def test_tolerance_and_capping(self):
        ds=[DayLimit('g',75,1) for _ in range(7)]
        r=distribute_week([{'dk':80} for _ in range(8)],ds,tolerance=5)
        self.assertEqual(len(r.placements),7)
        self.assertEqual(len(r.unplaced),1)

    def test_bounds(self):
        with self.assertRaises(ValueError): distribute_week([],days(1001))
        with self.assertRaises(ValueError): distribute_week([],days(),tolerance=-1)
        with self.assertRaises(ValueError): distribute_week([],days()[:6])

if __name__=='__main__': unittest.main()
