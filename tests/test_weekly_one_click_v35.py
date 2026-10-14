import random
import unittest
from services.weekly_equal_distribution_v35 import DayLimit
from services.weekly_one_click_v35 import plan_one_click


class TestOneClickWeekly(unittest.TestCase):
    def test_19_tasks_spread_every_day(self):
        tasks=[{'dk':75,'ders':'fizik' if i%2 else 'kimya'} for i in range(19)]
        days=[DayLimit(str(d),330,4) for d in range(7)]
        p=plan_one_click(tasks,days)
        self.assertEqual(p.counts,(3,3,3,3,3,2,2))
        self.assertEqual(sum(p.totals),1425)
        self.assertFalse(p.unplaced)
        self.assertEqual(len({x.task_index for x in p.placements}),19)

    def test_manual_row_preserved(self):
        tasks=[{'dk':75,'ders':'fizik'} for _ in range(12)]
        days=[DayLimit(str(d),300,4) for d in range(7)]
        p=plan_one_click(tasks, days, manual_assignments={0:(5,),1:(),2:(6,)})
        self.assertEqual([x.day_index for x in p.placements if x.task_index==0],[5])
        self.assertFalse(any(x.task_index==1 for x in p.placements))
        self.assertEqual([x.day_index for x in p.placements if x.task_index==2],[6])
        self.assertEqual(p.excluded,(1,))

    def test_600_minute_allowed(self):
        tasks=[{'dk':75} for _ in range(12)]
        days=[DayLimit(str(d),600 if d==5 else 0,12 if d==5 else 0) for d in range(7)]
        p=plan_one_click(tasks,days)
        self.assertEqual(p.totals[5],600)
        self.assertEqual(len(p.unplaced),4)

    def test_overloaded_manual_cannot_force_auto_over_limit(self):
        tasks=[{'dk':75} for _ in range(4)]
        days=[DayLimit(str(d),100,1) for d in range(7)]
        p=plan_one_click(tasks, days, manual_assignments={0:(0,),1:(0,)})
        self.assertEqual(p.counts[0],2)
        self.assertEqual(set((2,3)),{x.task_index for x in p.placements if x.day_index!=0})
        self.assertTrue(any('aşıyor' in x for x in p.warnings))

    def test_repeated_manual_is_reported_not_deleted(self):
        tasks=[{'dk':45}]
        p=plan_one_click(tasks,[DayLimit(str(d),100,2) for d in range(7)],manual_assignments={0:(0,1)})
        self.assertEqual(sum(p.totals),90)
        self.assertEqual(p.requested_minutes,45)
        self.assertTrue(any('tekrarlar' in w for w in p.warnings))

    def test_validation(self):
        days=[DayLimit(str(d),240,4) for d in range(7)]
        for task in ({'dk':'x'},{'dk':-10},{'dk':True}):
            with self.assertRaises(ValueError):plan_one_click([task],days)
        with self.assertRaises(ValueError):plan_one_click([{'dk':75}],days,manual_assignments={0:(7,)})

    def test_random_invariants(self):
        rand=random.Random(414)
        for _ in range(500):
            n=rand.randrange(0,30)
            tasks=[{'dk':rand.randrange(15,181),'ders':rand.choice(['fizik','kimya','mat'])} for _ in range(n)]
            days=[DayLimit(str(d),rand.randrange(0,721),rand.randrange(0,13)) for d in range(7)]
            pinned={r:(rand.randrange(7),) if rand.random()<.8 else () for r in range(n) if rand.random()<.16}
            p=plan_one_click(tasks,days,manual_assignments=pinned)
            self.assertEqual(set(range(n)),set(x.task_index for x in p.placements)|set(p.unplaced)|set(p.excluded))
            self.assertEqual(tuple(sum(x.minutes for x in p.placements if x.day_index==d) for d in range(7)),p.totals)
            self.assertEqual(p.scheduled_minutes,sum(p.totals))
            for d in range(7):
                a=sum(x.minutes for x in p.placements if x.day_index==d and x.task_index in pinned)
                b=sum(x.minutes for x in p.placements if x.day_index==d and x.task_index not in pinned)
                fixed_cnt=sum(1 for x in p.placements if x.day_index==d and x.task_index in pinned)
                self.assertTrue(b==0 or a+b<=days[d].minutes)
                self.assertLessEqual(p.counts[d]-fixed_cnt,max(0,days[d].max_tasks-fixed_cnt))

if __name__=='__main__':unittest.main()
