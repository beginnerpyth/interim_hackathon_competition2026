import random
from collections import defaultdict
from typing import List, Tuple

import models


def _chunk_round_robin(applicants: list, team_size: int) -> List[list]:
    """
    Shared helper: shuffles a list of applicants and splits them into
    `num_teams = len // team_size` teams via round robin, so any remainder
    is spread one-per-team instead of forming its own tiny team.
    Returns [] if the list is empty.
    """
    if not applicants:
        return []

    shuffled = applicants.copy()
    random.shuffle(shuffled)

    num_teams = max(1, len(shuffled) // team_size)
    teams = [[] for _ in range(num_teams)]
    for i, applicant in enumerate(shuffled):
        teams[i % num_teams].append(applicant)

    return teams


def create_random_teams(applications: List["models.Application"], team_size: int):
    """
    Original behavior: ignore grade entirely, one random pool, round-robin
    into teams. Kept for events where year-based grouping isn't wanted.
    """
    return _chunk_round_robin(applications, team_size)


def create_year_grouped_teams(
    applications: List["models.Application"], team_size: int
) -> List[Tuple[list, str]]:
    """
    Groups applicants by grade/year first (1年生 together, 2年生 together,
    etc.), forms teams within each year group, and merges any year group
    too small to form even one full team into a single shared "mixed"
    group so nobody gets left without a team.

    Returns a list of (members, group_label) tuples, e.g.:
        ([app1, app2, app3], "1年生グループ")
        ([app4, app5, app6], "2年生グループ")
        ([app7, app8], "混合グループ（学年混合）")
    """
    if not applications:
        return []

    by_grade = defaultdict(list)
    for app in applications:
        key = app.grade if app.grade else "unknown"
        by_grade[key].append(app)

    grade_labels = {
        "1": "1年生グループ",
        "2": "2年生グループ",
        "3": "3年生グループ",
        "4": "4年生グループ",
        "unknown": "学年未設定グループ",
    }

    results: List[Tuple[list, str]] = []
    leftover_pool: list = []

    for grade_key, members in by_grade.items():
        if len(members) >= team_size:
            teams = _chunk_round_robin(members, team_size)
            label = grade_labels.get(grade_key, f"{grade_key}年生グループ")
            for team in teams:
                results.append((team, label))
        else:
            # Not enough same-year students to form a full team on their
            # own — pool them together across years instead of leaving
            # them teamless.
            leftover_pool.extend(members)

    if leftover_pool:
        mixed_teams = _chunk_round_robin(leftover_pool, team_size)
        for team in mixed_teams:
            results.append((team, "混合グループ（学年混合）"))

    return results