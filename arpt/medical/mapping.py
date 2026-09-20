"""
Condition <-> test mapping and test-selection logic.

Given a set of suspected condition ids (from LLM triage of the patient's
spoken complaint), produce a deduplicated, ordered battery of movement tests
that maximally discriminates between them.
"""
from __future__ import annotations

from collections import Counter

from .conditions import CONDITIONS, Condition, Region
from .tests import TESTS, MovementTest


def tests_for_condition(condition_id: str) -> list[MovementTest]:
    c = CONDITIONS[condition_id]
    return [TESTS[t] for t in c.recommended_tests if t in TESTS]


def conditions_for_test(test_id: str) -> list[Condition]:
    return [c for c in CONDITIONS.values() if test_id in c.recommended_tests]


def select_test_battery(condition_ids: list[str], max_tests: int = 4) -> list[MovementTest]:
    """
    Choose the most informative tests covering the suspected conditions.

    Strategy: rank tests by how many of the suspected conditions they probe,
    then greedily pick to cover all conditions with as few tests as possible.
    """
    valid = [cid for cid in condition_ids if cid in CONDITIONS]
    if not valid:
        return [TESTS["squat"], TESTS["single_leg_balance"]]

    # Count how many suspected conditions each test addresses.
    coverage: Counter[str] = Counter()
    for cid in valid:
        for tid in CONDITIONS[cid].recommended_tests:
            coverage[tid] += 1

    remaining = set(valid)
    chosen: list[str] = []
    while remaining and len(chosen) < max_tests:
        # pick the test covering the most still-uncovered conditions
        best_tid, best_gain = None, -1
        for tid, _ in coverage.most_common():
            if tid in chosen or tid not in TESTS:
                continue
            gain = sum(1 for cid in remaining if tid in CONDITIONS[cid].recommended_tests)
            if gain > best_gain:
                best_tid, best_gain = tid, gain
        if best_tid is None or best_gain <= 0:
            break
        chosen.append(best_tid)
        remaining = {cid for cid in remaining
                     if best_tid not in CONDITIONS[cid].recommended_tests}

    return [TESTS[tid] for tid in chosen]


def regions_for_conditions(condition_ids: list[str]) -> list[Region]:
    seen: list[Region] = []
    for cid in condition_ids:
        if cid in CONDITIONS:
            r = CONDITIONS[cid].region
            if r not in seen:
                seen.append(r)
    return seen
