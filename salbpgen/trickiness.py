"""Trickiness measure (Section 4.2): statistically estimated share of
non-optimal solutions in the solution space.

Solutions are sampled by a random search with the maximum load rule
(station-oriented: at every step a task is chosen at random among the
assignable ones; a new station is opened only when no task fits anymore).
"""

from __future__ import annotations

import math
import random
from collections import Counter

from .instance import Instance
from .stats import lower_bound

CATEGORIES = (
    (0.995, "extremely tricky"),
    (0.95, "very tricky"),
    (0.5, "tricky"),
)


class _Sampler:
    def __init__(self, inst: Instance):
        n = inst.n
        self.n = n
        self.t = inst.task_times
        self.c = inst.cycle_time
        if max(self.t, default=0) > self.c:
            raise ValueError("task time exceeds the cycle time")
        self.succ = [[] for _ in range(n)]
        self.indeg = [0] * n
        for i, j in set(inst.arcs):
            self.succ[i - 1].append(j - 1)
            self.indeg[j - 1] += 1
        self.roots = [v for v in range(n) if self.indeg[v] == 0]

    def run(self, rng: random.Random) -> int:
        t, c, succ = self.t, self.c, self.succ
        indeg = self.indeg[:]
        avail = self.roots[:]
        stations, rem, left = 1, c, self.n
        while left:
            fit = [k for k, v in enumerate(avail) if t[v] <= rem]
            if not fit:
                stations += 1
                rem = c
                continue
            k = rng.choice(fit)
            v = avail[k]
            avail[k] = avail[-1]
            avail.pop()
            rem -= t[v]
            left -= 1
            for w in succ[v]:
                indeg[w] -= 1
                if indeg[w] == 0:
                    avail.append(w)
        return stations


def random_search(inst: Instance, runs: int = 10_000, seed=None) -> Counter:
    """Distribution of the number of stations over ``runs`` random solutions."""
    rng = random.Random(seed)
    s = _Sampler(inst)
    return Counter(s.run(rng) for _ in range(runs))


def is_trivial(inst: Instance, runs: int = 10_000, seed=None) -> bool:
    """True if all random solutions have the same number of stations (Tr = 0);
    stops at the first differing solution."""
    rng = random.Random(seed)
    s = _Sampler(inst)
    first = s.run(rng)
    return all(s.run(rng) == first for _ in range(runs - 1))


def wilson_interval(p: float, runs: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (Appendix A, eq. A.1)."""
    den = 1 + z * z / runs
    centre = p + z * z / (2 * runs)
    half = z * math.sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs))
    return (max(0.0, (centre - half) / den), min(1.0, (centre + half) / den))


def trickiness(inst: Instance, runs: int = 10_000, optimum: int | None = None, seed=None) -> dict:
    """Estimate Tr. Without a known optimum, the best found solution counts as
    optimal if it reaches the lower bound; otherwise the category is "open",
    unless the best solution was found in < 0.5% of the runs (then the instance
    is "extremely tricky")."""
    dist = random_search(inst, runs, seed)
    best = min(dist)
    lb = lower_bound(inst.task_times, inst.cycle_time)
    opt = optimum if optimum is not None else (best if best <= lb else None)
    res = {"runs": runs, "best": best, "lb": lb, "optimum": opt, "distribution": dict(sorted(dist.items()))}
    if opt is None:
        share_best = dist[best] / runs
        res["tr"] = None
        res["category"] = "extremely tricky" if share_best < 0.005 else "open"
        return res
    p_opt = dist.get(opt, 0) / runs
    tr = 1.0 - p_opt
    res["tr"] = tr
    res["tr_ci95"] = tuple(1 - x for x in reversed(wilson_interval(p_opt, runs)))
    if tr == 0:
        res["category"] = "trivial"
    else:
        res["category"] = next((name for thr, name in CATEGORIES if tr >= thr), "less tricky")
    return res
