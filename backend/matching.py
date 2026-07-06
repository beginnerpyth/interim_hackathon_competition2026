import random
from typing import List

import models


def create_random_teams(applications: List["models.Application"], team_size: int):
    """
    Shuffles all applicants randomly and splits them as evenly as possible
    into teams sized around `team_size`.

    Example: 22 applicants, team_size=5 -> num_teams = 22 // 5 = 4 teams.
    Round-robin distribution then gives sizes [6, 6, 5, 5] — the 2 "leftover"
    applicants (22 % 5 = 2) are spread one-per-team into the first 2 teams,
    instead of forming their own separate small team.

    Returns a list of teams, where each team is a list of Application objects.
    """
    if not applications:
        return []

    shuffled = applications.copy()
    random.shuffle(shuffled)

    num_teams = max(1, len(shuffled) // team_size)

    teams = [[] for _ in range(num_teams)]
    for i, applicant in enumerate(shuffled):
        teams[i % num_teams].append(applicant)

    return teams