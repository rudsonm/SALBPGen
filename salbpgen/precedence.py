"""Precedence graph generation (arc generation part of SALBPGen).

Follows Section 5.1 of Otto, Otto & Scholl (2013). The centrepiece is the
concept of *stages*: the stage of a task is its depth, i.e. the maximal number
of arcs on a path from a dummy source to the task.

1. Choose the number of stages K (default: maximal precedence flexibility,
   Theorem 1 / Table 3; for extreme OS values K grows linearly with OS).
2. Generate the optional graph structures (chains, bottlenecks, isolated
   tasks) and place them randomly into the stages.
3. Assign the remaining tasks to the stages. Stage sizes follow a truncated
   normal distribution, every stage holds at least one task and at least one
   task that can precede the tasks of the next stage.
4. Renumber the tasks topologically (stage by stage) and connect every task to
   the previous stage.
5. Add random arcs between not yet connected task pairs until the order
   strength lies within the tolerance. If that fails, the whole procedure is
   repeated; after ``max_attempts`` attempts an error is raised.

Definitions (Section 4.1.2):

* a *bottleneck* is the only direct follower of at least two of its direct
  predecessors and the only direct predecessor of at least two of its direct
  followers (degree >= 4);
* *chain* tasks form a path and each has at most one direct predecessor and
  at most one direct follower; a chain has at least two tasks.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .graph import PrecedenceGraph, iter_bits, nth_set_bit

STRUCTURES = ("MIXED", "BN", "CH")

# Table 3: number of stages with maximal flexibility in order strength
TABLE3_STAGES = {20: 6, 30: 8, 40: 9, 50: 11, 60: 12, 70: 14, 80: 15, 90: 16, 100: 17,
                 125: 20, 150: 23, 175: 25, 200: 27, 300: 36}


class GenerationError(RuntimeError):
    pass


# ---------------------------------------------------------------- OS bounds
def os_min(n: int, K: int) -> float:
    """Lowest achievable OS with K stages (Theorem 1): a single path through all stages."""
    return K * (K - 1) / (n * (n - 1)) if n > 1 else 0.0


def os_max(n: int, K: int) -> float:
    """Highest achievable OS with K stages (Theorem 1): equal stage sizes, complete
    connections between consecutive stages."""
    if n < 2:
        return 0.0
    q, h = divmod(n, K)
    within = h * math.comb(q + 1, 2) + (K - h) * math.comb(q, 2)
    return 1.0 - within / math.comb(n, 2)


def max_flexibility_stages(n: int) -> int:
    """K with the largest OSmax - OSmin, attained where n^2 = K^2 (2K - 1)."""
    if n in TABLE3_STAGES:
        return TABLE3_STAGES[n]
    return min(range(1, n + 1), key=lambda K: abs(K * K * (2 * K - 1) - n * n))


def default_stages(n: int, order_strength: float) -> int:
    """Default K: maximal flexibility unless the OS lies outside its bounds; then K
    is linear in OS (K = 1 for OS = 0, K = n for OS = 1)."""
    K = max_flexibility_stages(n)
    if os_min(n, K) <= order_strength <= os_max(n, K):
        return K
    return min(n, max(1, round(1 + order_strength * (n - 1))))


# ------------------------------------------------------------------- params
@dataclass
class GraphParams:
    n: int
    order_strength: float
    os_tolerance: float = 0.005
    n_stages: int | None = None  # None -> default_stages(n, OS), adapted on failures
    stage_size_sd: float = 0.5  # sd of the truncated normal stage size, relative to n/K
    # chains: either a number of chains or a target share of chain tasks
    n_chains: int = 0
    chain_share: float = 0.0
    chain_length: tuple[int, int] = (2, 6)
    # bottlenecks: number and range of direct predecessors / followers each
    n_bottlenecks: int = 0
    bottleneck_in: tuple[int, int] = (4, 7)
    bottleneck_out: tuple[int, int] = (4, 7)
    n_isolated: int = 0
    # optional limits on direct predecessors / followers of ordinary tasks
    max_pred: int | None = None
    max_succ: int | None = None
    max_attempts: int = 100
    patience: int | None = None  # rejected arcs before an attempt is given up

    def __post_init__(self):
        if self.n < 1:
            raise ValueError("n must be positive")
        if not 0.0 <= self.order_strength <= 1.0:
            raise ValueError("order_strength must be in [0, 1]")


def structure_preset(structure: str, n: int) -> dict:
    """Settings of the graph categories of the 2013 data sets (Section 5.3).

    * CH: at least 40% chain tasks;
    * BN: bottlenecks with degree >= 8 (>= 4 for small instances);
    * MIXED: default settings, no control of chains / bottlenecks.

    The number of bottlenecks (2% of the tasks, at least 1), the degree ranges
    and the chain lengths are not given in the paper; they are chosen inside
    the ranges observed for real-world graphs (Table 1: 1-6% bottleneck tasks
    with average degree 5-14, 30-45% chain tasks).
    """
    s = structure.upper()
    if s == "MIXED":
        return {}
    if s == "CH":
        return {"chain_share": 0.4, "chain_length": (2, 6)}
    if s == "BN":
        small = n <= 20
        rng_deg = (2, 3) if small else (4, 7)
        return {
            "n_bottlenecks": max(1, round(0.02 * n)),
            "bottleneck_in": rng_deg,
            "bottleneck_out": rng_deg,
        }
    raise ValueError(f"structure must be one of {STRUCTURES}")


@dataclass
class GraphResult:
    graph: PrecedenceGraph
    stages: list[int]  # stage (1..K) of every task
    bottlenecks: list[int] = field(default_factory=list)
    chains: list[list[int]] = field(default_factory=list)
    isolated: list[int] = field(default_factory=list)
    attempts: int = 1
    warnings: list[str] = field(default_factory=list)

    @property
    def n_stages(self) -> int:
        return max(self.stages, default=0)


class _AttemptFailed(Exception):
    def __init__(self, reason: str):
        self.reason = reason  # "too_high" | "too_low" | "layout"


# ------------------------------------------------------------------ attempt
class _Attempt:
    def __init__(self, p: GraphParams, K: int, rng: random.Random):
        self.p, self.K, self.rng, self.n = p, K, rng, p.n

    # -- step 1-3: layout ------------------------------------------------
    def _stage_sizes(self) -> list[int]:
        n, K, rng = self.n, self.K, self.rng
        mu = n / K
        sd = self.p.stage_size_sd * mu
        sizes = []
        for _ in range(K):
            while True:
                x = round(rng.gauss(mu, sd)) if sd > 0 else round(mu)
                if 1 <= x <= n - K + 1:
                    break
            sizes.append(x)
        while sum(sizes) > n:
            k = rng.choice([k for k in range(K) if sizes[k] > 1])
            sizes[k] -= 1
        while sum(sizes) < n:
            sizes[rng.randrange(K)] += 1
        return sizes

    def layout(self):
        p, K, rng = self.p, self.K, self.rng
        free = self._stage_sizes()  # remaining planned capacity per stage (0-based)
        stage, cap_in, cap_out = [], [], []
        arcs, chains, bottlenecks, isolated = [], [], [], []

        def new(k, ci=None, co=None):
            stage.append(k)
            cap_in.append(ci)
            cap_out.append(co)
            free[k] -= 1
            return len(stage) - 1

        def pick_start(span_needs):
            """Choose a stage k so that stage k + d needs span_needs[d] slots."""
            L = len(span_needs)
            starts = list(range(K - L + 1))
            if not starts:
                return None
            fitting = [k for k in starts if all(free[k + d] >= m for d, m in enumerate(span_needs))]
            return rng.choice(fitting or starts)

        # chains: whole chain has <=1 predecessor / follower per task
        lengths = []
        if p.chain_share > 0:
            target = math.ceil(p.chain_share * self.n)
            while sum(lengths) < target:
                lengths.append(rng.randint(max(2, p.chain_length[0]), max(2, p.chain_length[1])))
        lengths += [rng.randint(max(2, p.chain_length[0]), max(2, p.chain_length[1])) for _ in range(p.n_chains)]
        for L in lengths:
            L = min(L, K)
            if L < 2:
                raise _AttemptFailed("layout")
            k0 = pick_start([1] * L)
            chain = [new(k0 + d, 1, 1) for d in range(L)]
            arcs += list(zip(chain, chain[1:]))
            chains.append(chain)

        # bottlenecks: b at stage k, its predecessors at k-1, followers at k+1
        for _ in range(p.n_bottlenecks):
            if K < 3:
                raise _AttemptFailed("layout")
            d_in = rng.randint(*p.bottleneck_in)
            d_out = rng.randint(*p.bottleneck_out)
            k0 = pick_start([d_in, 1, d_out])
            b = new(k0 + 1)
            for _ in range(d_in):
                arcs.append((new(k0, None, 1), b))  # b is its only follower
            for _ in range(d_out):
                arcs.append((b, new(k0 + 2, 1, None)))  # b is its only predecessor
            bottlenecks.append(b)

        for _ in range(p.n_isolated):
            isolated.append(new(0, 0, 0))

        rest = self.n - len(stage)
        if rest < 0:
            raise _AttemptFailed("layout")
        # "required" tasks: every stage non-empty, and every stage below K holds a
        # task without a follower limit, able to precede the next stage
        by_stage = [[] for _ in range(K)]
        for v, k in enumerate(stage):
            by_stage[k].append(v)
        for k in range(K):
            needs = not by_stage[k] or (k < K - 1 and all(cap_out[v] is not None for v in by_stage[k]))
            if needs:
                if rest == 0:
                    raise _AttemptFailed("layout")
                by_stage[k].append(new(k))
                rest -= 1
        # remaining tasks follow the planned stage sizes
        for _ in range(rest):
            weights = [max(f, 0) for f in free]
            if not any(weights):
                weights = [1] * K
            k = rng.choices(range(K), weights)[0]
            new(k)

        # step 4: topological renumbering, stage by stage (random order inside a stage)
        order = sorted(range(len(stage)), key=lambda v: (stage[v], rng.random()))
        nid = [0] * len(order)
        for i, v in enumerate(order):
            nid[v] = i
        self.stage = [stage[v] + 1 for v in order]
        self.cap_in = [cap_in[v] for v in order]
        self.cap_out = [cap_out[v] for v in order]
        for v in range(self.n):  # global limits for ordinary tasks
            if self.cap_in[v] is None and p.max_pred is not None:
                self.cap_in[v] = p.max_pred
            if self.cap_out[v] is None and p.max_succ is not None:
                self.cap_out[v] = p.max_succ
        self.struct_arcs = [(nid[a], nid[b]) for a, b in arcs]
        self.chains = [[nid[v] for v in ch] for ch in chains]
        self.bottlenecks = [nid[b] for b in bottlenecks]
        self.isolated = [nid[v] for v in isolated]

    # -- helpers on capacities -------------------------------------------
    def _in_ok(self, v):
        c = self.cap_in[v]
        return c is None or self.g.in_degree(v) < c

    def _out_ok(self, v):
        c = self.cap_out[v]
        return c is None or self.g.out_degree(v) < c

    def _refresh(self, v):
        bit = 1 << v
        self.in_free = self.in_free | bit if self._in_ok(v) else self.in_free & ~bit
        self.out_free = self.out_free | bit if self._out_ok(v) else self.out_free & ~bit

    def _add(self, u, v):
        removed = self.g.add_arc(u, v)
        for x in {u, v, *(y for arc in removed for y in arc)}:
            self._refresh(x)

    # -- step 4-5: arcs ----------------------------------------------------
    def build(self) -> GraphResult:
        self.layout()
        n, K, rng, p = self.n, self.K, self.rng, self.p
        self.g = g = PrecedenceGraph(n)
        self.in_free = self.out_free = 0
        for v in range(n):
            self._refresh(v)
        for u, v in self.struct_arcs:
            self._add(u, v)

        first = [0] * (K + 2)  # first id of every stage (ids are stage-ordered)
        for v in reversed(range(n)):
            first[self.stage[v]] = v
        first[K + 1] = n
        members = [list(range(first[k], first[k + 1])) for k in range(K + 1)]

        # connect every task to the previous stage
        for k in range(2, K + 1):
            prev = members[k - 1]
            for v in members[k]:
                if any(self.stage[u] == k - 1 for u in g.pred[v]):
                    continue
                cands = [u for u in prev if self._out_ok(u)]
                if not cands or not self._in_ok(v):
                    raise _AttemptFailed("layout")
                self._add(rng.choice(cands), v)

        total = g.max_pairs
        if total == 0:
            return self._result()
        target = p.order_strength * total
        tol = max(1, int(p.os_tolerance * total))
        if g.closure_size > target + tol:
            raise _AttemptFailed("too_high")

        later = [((1 << n) - 1) & ~((1 << first[k + 1]) - 1) for k in range(K + 1)]
        out_list = list(range(n))
        patience = p.patience or (10 * n + 500)
        fails = 0
        while g.closure_size < target - tol:
            # random not yet connected pair (u, v) with stage(u) < stage(v);
            # u is accepted with probability |candidates(u)| / n -> pairs are uniform
            u = rng.choice(out_list)
            if not (self.out_free >> u) & 1:
                fails += 1
            else:
                cand = later[self.stage[u]] & ~g.reach[u] & self.in_free
                cnt = cand.bit_count()
                if cnt == 0 or rng.random() * n >= cnt:
                    fails += 1
                else:
                    v = nth_set_bit(cand, rng.randrange(cnt))
                    gain = g.gain(u, v)
                    if g.closure_size + gain <= target + tol:
                        self._add(u, v)
                        fails = 0
                        continue
                    fails += 1
            if fails > patience:
                raise _AttemptFailed("too_low")
        return self._result()

    def _result(self) -> GraphResult:
        return GraphResult(self.g, self.stage, self.bottlenecks, self.chains, self.isolated)


def generate_precedence_graph(params: GraphParams, rng: random.Random | int | None = None) -> GraphResult:
    """Generate a precedence graph; raises GenerationError after max_attempts failures."""
    if not isinstance(rng, random.Random):
        rng = random.Random(rng)
    K = params.n_stages or default_stages(params.n, params.order_strength)
    fixed_K = params.n_stages is not None
    reasons: dict[str, int] = {}
    warnings = []
    for attempt in range(1, params.max_attempts + 1):
        try:
            res = _Attempt(params, K, rng).build()
        except _AttemptFailed as e:
            reasons[e.reason] = reasons.get(e.reason, 0) + 1
            # extension of the paper: if attempts keep failing in the same direction,
            # move K towards the linear K(OS) rule
            if not fixed_K and attempt % 5 == 0:
                if e.reason == "too_high" and K > 1:
                    K -= 1
                    warnings.append(f"number of stages lowered to {K}")
                elif e.reason in ("too_low", "layout") and K < params.n:
                    K += 1
                    warnings.append(f"number of stages raised to {K}")
            continue
        res.attempts = attempt
        res.warnings = warnings
        return res
    raise GenerationError(
        f"no graph with n={params.n}, OS={params.order_strength} after {params.max_attempts} attempts {reasons}"
    )


__all__ = [
    "GenerationError", "GraphParams", "GraphResult", "STRUCTURES", "TABLE3_STAGES",
    "default_stages", "generate_precedence_graph", "max_flexibility_stages",
    "os_max", "os_min", "structure_preset", "iter_bits",
]
