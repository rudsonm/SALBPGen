"""Precedence graph generation following the SALBPGen idea.

Two phases:

1. **Skeleton** – imposes the requested structure type
   * ``MIXED``: no skeleton (no prominent structure);
   * ``BN`` (bottlenecks): a few tasks with many direct predecessors and
     successors, through which many paths run;
   * ``CH`` (chains): a share of the tasks is organised in linear chains
     (each inner task has exactly one predecessor and one successor).
2. **Fill** – random non-redundant arcs are added until the order strength
   reaches the target (within a tolerance). Ordinary tasks respect a maximum
   number of direct predecessors/successors, chain interiors stay untouched and
   skeleton arcs are never made redundant.

Tasks are numbered topologically up front (every arc goes from a lower to a
higher index), which is the usual convention of SALBP data files.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .graph import PrecedenceGraph, iter_bits, nth_set_bit

STRUCTURES = ("MIXED", "BN", "CH")


@dataclass
class GraphParams:
    n: int
    order_strength: float
    structure: str = "MIXED"
    os_tolerance: float = 0.005
    # limits on direct predecessors / successors for ordinary tasks
    max_pred: int = 3
    max_succ: int = 3
    # BN: number of bottlenecks (None -> max(1, round(n / 50))) and degree range
    n_bottlenecks: int | None = None
    bottleneck_degree: tuple[int, int] = (4, 7)
    # CH: share of tasks lying in chains and range of chain lengths
    chain_share: float = 0.5
    chain_length: tuple[int, int] = (3, 8)
    # fill phase
    connect_isolated: bool = True
    locality: float = 0.5  # probability of drawing a partner close in the numbering
    patience: int | None = None  # failed attempts before relaxing (None -> auto)
    max_relaxations: int = 10
    # renumber tasks with a random topological order at the end, so that the
    # construction (blocks, chain positions) is not visible in the numbering
    shuffle_labels: bool = True
    # full restarts (with fresh random numbers) if the OS target is missed
    restarts: int = 20

    def __post_init__(self):
        self.structure = self.structure.upper()
        if self.structure not in STRUCTURES:
            raise ValueError(f"structure must be one of {STRUCTURES}")
        if not 0.0 <= self.order_strength <= 1.0:
            raise ValueError("order_strength must be in [0, 1]")
        if self.n < 1:
            raise ValueError("n must be positive")


@dataclass
class GraphResult:
    graph: PrecedenceGraph
    bottlenecks: list[int] = field(default_factory=list)
    chains: list[list[int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class _Builder:
    def __init__(self, p: GraphParams, rng: random.Random):
        self.p = p
        self.rng = rng
        self.n = p.n
        self.g = PrecedenceGraph(p.n)
        self.protected: set[tuple[int, int]] = set()
        self.lock_in: set[int] = set()  # tasks that may not receive new predecessors
        self.lock_out: set[int] = set()  # tasks that may not receive new successors
        self.exempt: set[int] = set()  # tasks without degree limits (bottlenecks)
        self.isolated: set[int] = set(range(p.n))
        self.max_pred = p.max_pred
        self.max_succ = p.max_succ
        self.res = GraphResult(self.g)
        self.full = (1 << p.n) - 1

    # -------------------------------------------------------------- helpers
    def _add(self, i: int, j: int, protect: bool = False) -> None:
        removed = self.g.add_arc(i, j)
        for a, b in removed:
            self.protected.discard((a, b))
        if protect:
            self.protected.add((i, j))
        for v in (i, j, *(x for arc in removed for x in arc)):
            if self.g.in_degree(v) or self.g.out_degree(v):
                self.isolated.discard(v)
            else:
                self.isolated.add(v)

    # ------------------------------------------------------------- skeletons
    def skeleton_chains(self) -> None:
        p, rng, n = self.p, self.rng, self.n
        lmin, lmax = p.chain_length
        lmin = max(2, lmin)
        target = round(p.chain_share * n)
        lengths, used = [], 0
        while used < target:
            L = min(rng.randint(lmin, lmax), target - used)
            if L < 2:
                break
            lengths.append(L)
            used += L
        units = [("chain", L) for L in lengths] + [("single", 1)] * (n - used)
        rng.shuffle(units)
        pos = 0
        for kind, L in units:
            if kind == "chain":
                chain = list(range(pos, pos + L))
                for a, b in zip(chain, chain[1:]):
                    self._add(a, b, protect=True)
                self.lock_out.update(chain[:-1])
                self.lock_in.update(chain[1:])
                self.res.chains.append(chain)
            pos += L

    def skeleton_bottlenecks(self) -> None:
        p, rng, n = self.p, self.rng, self.n
        k = p.n_bottlenecks if p.n_bottlenecks is not None else max(1, round(n / 50))
        dmin, dmax = p.bottleneck_degree
        if dmin <= max(p.max_pred, p.max_succ):
            self.res.warnings.append(
                "bottleneck degree not above max_pred/max_succ: bottlenecks may not stand out"
            )
        # place bottlenecks evenly over the numbering, with a little jitter
        positions = []
        for q in range(k):
            centre = (q + 1) * n / (k + 1)
            jitter = rng.uniform(-0.25, 0.25) * n / (k + 1)
            positions.append(min(n - 1, max(0, int(round(centre + jitter)))))
        positions = sorted(set(positions))
        # Degree caps so the requested OS stays reachable:
        # * the direct predecessors (successors) of a bottleneck must remain pairwise
        #   incomparable, which costs 2*C(d, 2) incomparable pairs -> high OS limit;
        # * the skeleton alone orders (d+1)^2 - 1 pairs -> low OS limit.
        k = len(positions)
        total = n * (n - 1) / 2
        budget_inc = 0.75 * (1.0 - p.order_strength) * total / k
        budget_cmp = 0.75 * p.order_strength * total / k
        cap_hi = int((1 + (1 + 4 * budget_inc) ** 0.5) / 2)  # d(d-1) <= budget_inc
        cap_lo = int((budget_cmp + 1) ** 0.5) - 1  # (d+1)^2 - 1 <= budget_cmp
        d_cap = max(2, min(cap_hi, cap_lo))
        if d_cap < dmin:
            self.res.warnings.append(
                f"bottleneck degree capped at {d_cap} to make OS={p.order_strength} reachable"
            )
        bounds = [-1, *positions, n]
        for idx, b in enumerate(positions):
            # predecessors / successors form contiguous blocks next to the bottleneck
            # (the final random relabelling hides this in the numbering)
            n_before = b - bounds[idx] - 1
            n_after = bounds[idx + 2] - b - 1
            d_in = min(rng.randint(dmin, dmax), n_before, d_cap)
            d_out = min(rng.randint(dmin, dmax), n_after, d_cap)
            if min(d_in, d_out) < min(dmin, d_cap):
                self.res.warnings.append(f"bottleneck {b + 1}: segment too small for degree {dmin}")
            for u in range(b - d_in, b):
                if not self.g.reaches(u, b):
                    self._add(u, b, protect=True)
            for w in range(b + 1, b + 1 + d_out):
                if not self.g.reaches(b, w):
                    self._add(b, w, protect=True)
            self.exempt.add(b)
            self.res.bottlenecks.append(b)

    # ------------------------------------------------------------------ fill
    def _partner(self, u: int, as_tail: bool) -> int | None:
        n, g, rng = self.n, self.g, self.rng
        if as_tail:
            cand = ~g.reach[u] & self.full & ~((1 << (u + 1)) - 1)
        else:
            cand = ~g.reached_by[u] & ((1 << u) - 1)
        if not cand:
            return None
        if rng.random() < self.p.locality:
            w = max(3, n // 10)
            if as_tail:
                local = cand & ((1 << min(n, u + 1 + w)) - 1)
            else:
                local = cand & ~((1 << max(0, u - w)) - 1)
            if local:
                cand = local
        return nth_set_bit(cand, rng.randrange(cand.bit_count()))

    def _candidate(self) -> tuple[int, int] | None:
        rng = self.rng
        if self.p.connect_isolated and self.isolated and rng.random() < 0.5:
            u = rng.choice(tuple(self.isolated))
        else:
            u = rng.randrange(self.n)
        first = rng.random() < 0.5
        for as_tail in (first, not first):
            v = self._partner(u, as_tail)
            if v is not None:
                return (u, v) if as_tail else (v, u)
        return None

    def _allowed(self, i: int, j: int) -> bool:
        g = self.g
        if i in self.lock_out or j in self.lock_in:
            return False
        if i not in self.exempt and g.out_degree(i) >= self.max_succ:
            return False
        if j not in self.exempt and g.in_degree(j) >= self.max_pred:
            return False
        if self.protected and any(a in self.protected for a in g.made_redundant(i, j)):
            return False
        return True

    def fill(self) -> None:
        p, g = self.p, self.g
        total = g.max_pairs
        if total == 0:
            return
        target = p.order_strength * total
        tol = max(1, int(p.os_tolerance * total))
        if g.closure_size > target + tol:
            self.res.warnings.append(
                f"skeleton alone has OS={g.order_strength:.3f} > target {p.order_strength}"
            )
            return
        patience = p.patience or (20 * self.n + 200)
        fails, relaxations = 0, 0
        best = None  # (distance, arc) of the best overshooting candidate
        while g.closure_size < target - tol:
            cand = self._candidate()
            if cand is not None and self._allowed(*cand):
                gain = g.gain(*cand)
                if gain and g.closure_size + gain <= target + tol:
                    self._add(*cand)
                    fails, best = 0, None
                    continue
                if gain:
                    dist = abs(g.closure_size + gain - target)
                    if best is None or dist < best[0]:
                        best = (dist, cand)
            fails += 1
            if fails < patience:
                continue
            if best is not None and best[0] < abs(g.closure_size - target):
                self._add(*best[1])
                fails, best = 0, None
                continue
            if relaxations >= p.max_relaxations:
                self.res.warnings.append(
                    f"could not reach OS target: got {g.order_strength:.4f}, wanted {p.order_strength}"
                )
                return
            relaxations += 1
            self.max_pred += 1
            self.max_succ += 1
            self.res.warnings.append(
                f"relaxed degree limits to pred<={self.max_pred}, succ<={self.max_succ}"
            )
            fails, best = 0, None


def generate_precedence_graph(params: GraphParams, rng: random.Random | int | None = None) -> GraphResult:
    if not isinstance(rng, random.Random):
        rng = random.Random(rng)
    total = params.n * (params.n - 1) / 2
    tol = max(1, int(params.os_tolerance * total))
    target = params.order_strength * total
    best = None
    for attempt in range(params.restarts + 1):
        b = _Builder(params, rng)
        if params.structure == "CH":
            b.skeleton_chains()
        elif params.structure == "BN":
            b.skeleton_bottlenecks()
        b.fill()
        miss = abs(b.g.closure_size - target)
        if best is None or miss < best[0]:
            best = (miss, b.res)
        if miss <= tol:
            break
    res = best[1]
    if attempt:
        res.warnings.append(f"needed {attempt} restart(s)")
    if params.shuffle_labels:
        res = _relabel(res, rng)
    return res


def _relabel(res: GraphResult, rng: random.Random) -> GraphResult:
    """Renumber the tasks along a random topological order (random linear extension)."""
    g = res.graph
    indeg = [g.in_degree(v) for v in range(g.n)]
    ready = [v for v in range(g.n) if indeg[v] == 0]
    new_id = [0] * g.n
    k = 0
    while ready:
        v = ready.pop(rng.randrange(len(ready)))
        new_id[v] = k
        k += 1
        for w in g.succ[v]:
            indeg[w] -= 1
            if indeg[w] == 0:
                ready.append(w)
    ng = PrecedenceGraph.from_arcs(g.n, sorted((new_id[i], new_id[j]) for i, j in g.arcs()))
    return GraphResult(
        ng,
        bottlenecks=sorted(new_id[b] for b in res.bottlenecks),
        chains=[[new_id[v] for v in ch] for ch in res.chains],
        warnings=res.warnings,
    )


__all__ = ["GraphParams", "GraphResult", "STRUCTURES", "generate_precedence_graph", "iter_bits"]
