"""Task time distributions.

Each distribution is a mixture of normal components, truncated to
[tmin, tmax] by rejection and rounded to integers. Means and standard
deviations are given as fractions of ``tmax``:

* ``PB`` – peak at the bottom: most tasks are short;
* ``PM`` – peak in the middle: times concentrate around tmax/2;
* ``BM`` – bimodal: mix of the PB and PM components.

The default shape parameters are a reconstruction and can be overridden
with ``custom`` (a list of ``(weight, mean_frac, sd_frac)`` tuples).
"""

from __future__ import annotations

import random

Component = tuple[float, float, float]  # (weight, mean / tmax, sd / tmax)

DISTRIBUTIONS: dict[str, list[Component]] = {
    "PB": [(1.0, 0.1, 0.1)],
    "PM": [(1.0, 0.5, 0.1)],
    "BM": [(0.5, 0.1, 0.1), (0.5, 0.5, 0.1)],
}


def generate_task_times(
    n: int,
    dist: str | list[Component],
    rng: random.Random | int | None = None,
    tmin: int = 1,
    tmax: int = 1000,
) -> list[int]:
    if not isinstance(rng, random.Random):
        rng = random.Random(rng)
    comps = DISTRIBUTIONS[dist.upper()] if isinstance(dist, str) else list(dist)
    if not comps:
        raise ValueError("empty distribution")
    if tmin > tmax:
        raise ValueError("tmin > tmax")
    weights = [w for w, _, _ in comps]
    times = []
    for _ in range(n):
        _, mu, sd = rng.choices(comps, weights)[0]
        for _attempt in range(10_000):
            t = round(rng.gauss(mu * tmax, sd * tmax))
            if tmin <= t <= tmax:
                break
        else:  # pathological parameters: fall back to uniform
            t = rng.randint(tmin, tmax)
        times.append(t)
    return times
