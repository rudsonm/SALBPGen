"""Task time generation (task times part of SALBPGen, Sections 4.1.1, 5.1, 5.3).

Task times are drawn independently from a (truncated) distribution on
[tmin, tmax] and rounded to integers; the default cycle time is 1000.

* ``PB`` - normal with peak at small tasks ("peak at the bottom");
* ``BM`` - bimodal: combination of two normals with a higher peak at small
  tasks (the SALBPGen default; real-world shape after Kilbridge & Wester 1961:
  most tasks around 1/10 of the maximal time, aggregated tasks near c/2);
* ``PM`` - normal with peak at 0.5 * c ("peak in the middle").

The paper does not report standard deviations or mixture weights; the values
below are assumptions (fractions of the cycle time c) and can be overridden
with a list of ``(weight, mean_frac, sd_frac)`` components.
"""

from __future__ import annotations

import random

Component = tuple[float, float, float]  # (weight, mean / c, sd / c)

DISTRIBUTIONS: dict[str, list[Component]] = {
    "PB": [(1.0, 0.1, 0.1)],
    "BM": [(2 / 3, 0.1, 0.1), (1 / 3, 0.5, 0.1)],
    "PM": [(1.0, 0.5, 0.1)],
}


def generate_task_times(
    n: int,
    dist: str | list[Component] = "BM",
    rng: random.Random | int | None = None,
    cycle_time: int = 1000,
    tmin: int = 1,
    tmax: int | None = None,
    sum_multiple_of_c: bool = False,
) -> list[int]:
    """Draw n integer task times in [tmin, tmax] (tmax defaults to the cycle time).

    With ``sum_multiple_of_c`` the times are adjusted so that their sum is a
    multiple of the cycle time (as proposed by Hoffmann, 1992).
    """
    if not isinstance(rng, random.Random):
        rng = random.Random(rng)
    tmax = cycle_time if tmax is None else tmax
    comps = DISTRIBUTIONS[dist.upper()] if isinstance(dist, str) else list(dist)
    if not comps:
        raise ValueError("empty distribution")
    if not 1 <= tmin <= tmax:
        raise ValueError("need 1 <= tmin <= tmax")
    weights = [w for w, _, _ in comps]
    times = []
    for _ in range(n):
        _, mu, sd = rng.choices(comps, weights)[0]
        for _attempt in range(10_000):  # truncation by rejection
            t = round(rng.gauss(mu * cycle_time, sd * cycle_time))
            if tmin <= t <= tmax:
                break
        else:
            t = rng.randint(tmin, tmax)
        times.append(t)
    if sum_multiple_of_c:
        _adjust_sum(times, cycle_time, tmin, tmax, rng)
    return times


def _adjust_sum(times: list[int], c: int, tmin: int, tmax: int, rng: random.Random) -> None:
    r = sum(times) % c
    if r == 0:
        return
    # move to the nearer multiple when feasible, otherwise to the other one
    up, down = c - r, r
    room_up = sum(tmax - t for t in times)
    room_down = sum(t - tmin for t in times)
    if (up <= down and up <= room_up) or down > room_down:
        delta, sign = up, 1
    else:
        delta, sign = down, -1
    if (sign > 0 and delta > room_up) or (sign < 0 and delta > room_down):
        raise ValueError("cannot make the sum of task times a multiple of the cycle time")
    idx = list(range(len(times)))
    while delta:
        i = rng.choice(idx)
        room = tmax - times[i] if sign > 0 else times[i] - tmin
        if room:
            step = min(room, delta, max(1, delta // len(times) + 1))
            times[i] += sign * step
            delta -= step
