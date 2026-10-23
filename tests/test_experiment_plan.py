import unittest

from experiment_plan import scenario_schedule


class ScheduleTests(unittest.TestCase):
    def test_counterbalanced_order_reverses_each_pair(self):
        plan = scenario_schedule(("baseline", "static"), 4, "counterbalanced", 42)
        self.assertEqual(plan[0][0], plan[3][0])
        self.assertEqual(plan[1][0], plan[2][0])
        self.assertEqual(8, len(plan))
        self.assertEqual(plan, scenario_schedule(("baseline", "static"), 4, "counterbalanced", 42))

    def test_random_schedule_preserves_every_condition(self):
        plan = scenario_schedule(("baseline", "static"), 3, "random", 17)
        self.assertEqual(plan, scenario_schedule(("baseline", "static"), 3, "random", 17))
        self.assertEqual({(s, (r,)) for s in ("baseline", "static") for r in range(1, 4)}, set(plan))

    def test_legacy_groups_all_repetitions(self):
        self.assertEqual([("baseline", (1, 2)), ("static", (1, 2))],
                         scenario_schedule(("baseline", "static"), 2, "legacy", 17))
