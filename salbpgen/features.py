"""NRP-S instances built from features (one SALBPGen graph per feature).

An instance is a set of features. Every feature is a precedence graph made by
SALBPGen; a few random arcs link tasks of different features. Some features
are *controlled*: built so that their critical path hits cp_ratio * T. Any
feature (controlled or not) whose critical path is longer than the horizon T,
even when every task is done by the fastest developer, is marked *critical*:
delivering the whole feature within T is impossible (temporal infeasibility).

* **Feature sizes**: lognormal with median 6 and p90 23 tasks, truncated to
  [1, 200] (Epics of TAWOS, backlog tasks only).
* **Durations** (periods, MID developer): story points of TAWOS tasks planned
  in sprints, times ``periods_per_sp`` (integer periods of T per SP).
* **Critical features**: ``n_stages = K`` and ``critical_width`` tasks per
  stage, so a longest path has exactly K tasks. K grows (and graphs are
  resampled) until the critical path with the fastest developer, the sum of
  ceil(h / speedup), lies in [cp_ratio*T, cp_ratio*T + d), where d is the
  longest fast duration (one task). Links to other features can only make
  the critical path of the instance longer.
* **Links between features**: ``inter_share`` of all arcs (35% in TAWOS),
  always from an earlier to a later feature, so the graph stays acyclic.
* **Value**: feature f gets V_f = effort_f * U(0.5, 1.5) * value_scale,
  split over its tasks by depth: v_r proportional to (depth_r / depth_max)^alpha.
  alpha = 0 is uniform; a large alpha puts the value on the last tasks.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .precedence import GraphParams, generate_precedence_graph, os_max, os_min

# TAWOS, planned backlog tasks with 0 < SP <= 100 (n = 8,002); values under 1 SP
# rounded to 1, values with less than 0.39% of the tasks dropped.
TAWOS_SP = {1: 16.2, 2: 16.6, 3: 17.4, 4: 10.0, 5: 15.0, 6: 2.8, 8: 12.6, 10: 2.4, 13: 2.9,
            16: 0.8, 20: 0.5, 21: 0.5}


@dataclass
class FeatureParams:
    n_tasks: int
    horizon: int  # T, in periods
    n_critical: int = 1
    cp_ratio: float = 1.2  # critical path of each critical feature / T (fastest developer)
    speedup: float = 1.4  # fastest developer (SENIOR in nrp_instance.py)
    critical_width: int = 2  # tasks per stage of a critical feature
    feature_os: float = 0.1  # order strength of the other features
    size_median: float = 6.0
    size_p90: float = 23.0
    size_max: int = 200
    inter_share: float = 0.35
    alpha: float = 1.0
    value_scale: int = 10
    periods_per_sp: int = 1  # periods of T (e.g. hours) per story point
    sp_weights: dict = field(default_factory=lambda: dict(TAWOS_SP))

    def __post_init__(self):
        if self.n_tasks < 1 or self.horizon < 1:
            raise ValueError("n_tasks and horizon must be positive")
        if not isinstance(self.periods_per_sp, int) or self.periods_per_sp < 1:
            raise ValueError("periods_per_sp must be a positive integer")
        if not 0 <= self.inter_share < 1:
            raise ValueError("inter_share must be in [0, 1)")


@dataclass
class Feature:
    tasks: list[int]  # global 0-indexed task ids
    critical: bool  # critical path (fastest developer) > T, whether controlled or not
    critical_path_fast: int
    controlled: bool = False  # built by the generator to hit cp_ratio * T


@dataclass
class NRPSInstance:
    durations: list[int]  # MID developer, periods
    values: list[int]
    arcs: list[tuple[int, int]]  # 0-indexed (predecessor, successor)
    features: list[Feature]
    horizon: int
    meta: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.durations)

    def write(self, path: str | Path) -> None:
        """Classic NRP format read by ``nrp_instance.py`` (heuristic repo), one level.

        That reader turns a dependency line ``a b`` into the pair (b-1, a-1) =
        (predecessor, successor), so the arc u -> v is written as ``v+1 u+1``.
        Each distinct value becomes one stakeholder whose weight is the value.
        """
        by_value: dict[int, list[int]] = {}
        for r, v in enumerate(self.values):
            by_value.setdefault(v, []).append(r + 1)
        lines = ["1", str(self.n), " ".join(map(str, self.durations)), str(len(self.arcs))]
        lines += [f"{v + 1} {u + 1}" for u, v in sorted(self.arcs)]
        lines.append(str(len(by_value)))
        lines += [f"{v} {len(rs)} " + " ".join(map(str, rs)) for v, rs in sorted(by_value.items())]
        Path(path).write_text("\n".join(lines) + "\n")
        speedup = self.meta.get("params", {}).get("speedup", 1.4)
        meta = {**self.meta, "critical_path_fast": critical_path(self, speedup),
                "features": [asdict(f) for f in self.features]}
        Path(path).with_suffix(".json").write_text(json.dumps(meta, indent=1))

    @classmethod
    def read(cls, path: str | Path) -> "NRPSInstance":
        """Read a classic NRP file (any number of levels) and its ``.json``, if any."""
        tok = iter(Path(path).read_text().split())
        durations = []
        for _ in range(int(next(tok))):
            durations += [int(next(tok)) for _ in range(int(next(tok)))]
        deps = [(int(next(tok)), int(next(tok))) for _ in range(int(next(tok)))]
        values = [0] * len(durations)
        for _ in range(int(next(tok))):
            w, k = int(next(tok)), int(next(tok))
            for _ in range(k):
                values[int(next(tok)) - 1] += w
        meta, features, horizon = {}, [], 0
        side = Path(path).with_suffix(".json")
        if side.exists():
            meta = json.loads(side.read_text())
            features = [Feature(**f) for f in meta.pop("features")]
            horizon = meta["params"]["horizon"]
        arcs = [(b - 1, a - 1) for a, b in deps]
        return cls(durations, values, arcs, features, horizon, meta)


def _fast(h: int, speedup: float) -> int:
    return math.ceil(h / speedup)


def _longest(n: int, arcs, weight) -> tuple[list[int], list[int]]:
    """Longest path ending at each node: (sum of weights, number of nodes)."""
    succ = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in arcs:
        succ[u].append(v)
        indeg[v] += 1
    stack = [v for v in range(n) if indeg[v] == 0]
    dist = [weight(v) for v in range(n)]
    depth = [1] * n
    seen = 0
    while stack:
        u = stack.pop()
        seen += 1
        for v in succ[u]:
            dist[v] = max(dist[v], dist[u] + weight(v))
            depth[v] = max(depth[v], depth[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                stack.append(v)
    if seen != n:
        raise ValueError("graph contains a cycle")
    return dist, depth


def critical_path(inst: NRPSInstance, speedup: float = 1.4) -> int:
    """Critical path of the whole instance when every task gets the fastest developer."""
    return max(_longest(inst.n, inst.arcs, lambda r: _fast(inst.durations[r], speedup))[0], default=0)


def _feature_size(p: FeatureParams, rng: random.Random) -> int:
    sigma = math.log(p.size_p90 / p.size_median) / 1.2816
    return min(p.size_max, max(1, round(rng.lognormvariate(math.log(p.size_median), sigma))))


def _sp_to_periods(sp: float, p: FeatureParams) -> int:
    return sp * p.periods_per_sp


def _durations(k: int, p: FeatureParams, rng: random.Random) -> list[int]:
    sp = rng.choices(list(p.sp_weights), list(p.sp_weights.values()), k=k)
    return [_sp_to_periods(s, p) for s in sp]


def _graph(n: int, os_: float, rng: random.Random, n_stages: int | None = None) -> list[tuple[int, int]]:
    if n == 1:
        return []
    gp = GraphParams(n, os_, n_stages=n_stages) if n_stages else GraphParams(n, os_)
    return generate_precedence_graph(gp, rng).graph.arcs()


def _critical_feature(p: FeatureParams, rng: random.Random):
    target = p.cp_ratio * p.horizon
    # a path of K tasks is at most K * max_fast long, so smaller K cannot reach the target
    max_fast = _fast(_sp_to_periods(max(p.sp_weights), p), p.speedup)
    K = max(2, math.floor(target / max_fast))
    for _ in range(100):  # values of K
        below = True
        for _ in range(50):  # samples per K
            n = K * p.critical_width
            os_ = (os_min(n, K) + os_max(n, K)) / 2
            arcs = _graph(n, os_, rng, n_stages=K)
            dur = _durations(n, p, rng)
            cp = max(_longest(n, arcs, lambda r: _fast(dur[r], p.speedup))[0])
            if target <= cp < target + max_fast:
                return arcs, dur, cp
            below = below and cp < target
        if below:
            K += 1
    raise RuntimeError(f"no critical feature with critical path in [{target}, {target + max_fast})")


def generate_nrps(p: FeatureParams, seed: int | str | None = None) -> NRPSInstance:
    """Generate one instance; the same (params, seed) always gives the same instance."""
    rng = random.Random(seed)
    blocks = [(True, *_critical_feature(p, rng)) for _ in range(p.n_critical)]
    used = sum(len(d) for _, _, d, _ in blocks)
    if used > p.n_tasks:
        raise ValueError(f"critical features need {used} tasks, more than n_tasks={p.n_tasks}")
    while used < p.n_tasks:
        k = min(_feature_size(p, rng), p.n_tasks - used)
        arcs = _graph(k, p.feature_os, rng)
        dur = _durations(k, p, rng)
        blocks.append((False, arcs, dur, None))
        used += k
    rng.shuffle(blocks)

    durations, values, arcs, features = [], [], [], []
    for crit, f_arcs, dur, cp in blocks:
        o = len(durations)
        _, depth = _longest(len(dur), f_arcs, lambda r: 0)
        weights = [(d / max(depth)) ** p.alpha for d in depth]
        V = sum(dur) * rng.uniform(0.5, 1.5) * p.value_scale
        values += [max(1, round(V * w / sum(weights))) for w in weights]
        durations += dur
        arcs += [(o + u, o + v) for u, v in f_arcs]
        if cp is None:
            cp = max(_longest(len(dur), f_arcs, lambda r: _fast(dur[r], p.speedup))[0])
        features.append(Feature(list(range(o, o + len(dur))), cp > p.horizon, cp, controlled=crit))

    # arcs between features: earlier feature -> later feature keeps the graph acyclic
    n_inter = round(p.inter_share / (1 - p.inter_share) * len(arcs))
    existing = set(arcs)
    tries = 0
    while n_inter and len(features) > 1 and tries < 100 * n_inter:
        tries += 1
        a, b = sorted(rng.sample(range(len(features)), 2))
        e = (rng.choice(features[a].tasks), rng.choice(features[b].tasks))
        if e not in existing:
            existing.add(e)
            arcs.append(e)
            n_inter -= 1

    return NRPSInstance(durations, values, arcs, features, p.horizon,
                        meta={"seed": seed, "params": asdict(p)})
