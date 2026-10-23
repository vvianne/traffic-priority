"""Deterministic experiment scheduling without privileged dependencies."""

import random


def scenario_schedule(scenarios, repetitions, order, seed):
    """Yield (scenario, repetition numbers) for each isolated network session."""
    if order == "legacy":
        return [(scenario, tuple(range(1, repetitions + 1))) for scenario in scenarios]
    rng = random.Random(seed)
    initial = list(scenarios)
    rng.shuffle(initial)
    schedule = []
    for repetition in range(1, repetitions + 1):
        selected = list(initial)
        if order == "random":
            rng.shuffle(selected)
        elif repetition % 2 == 0:
            selected.reverse()
        schedule.extend((scenario, (repetition,)) for scenario in selected)
    return schedule
