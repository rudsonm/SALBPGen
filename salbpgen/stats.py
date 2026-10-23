"""Structure measures of SALBP-1 instances (Table 2 and Section 4.1.2)."""

from __future__ import annotations

import math
import statistics

from .graph import PrecedenceGraph
from .instance import Instance


def chain_tasks(g: PrecedenceGraph) -> set[int]:
    """Tasks lying on a path whose tasks have <= 1 direct predecessor and <= 1
    direct follower (chains have at least two tasks)."""
    out = set()
    for i in range(g.n):
        if g.out_degree(i) != 1 or g.in_degree(i) > 1:
            continue
        (j,) = g.succ[i]
        if g.in_degree(j) == 1 and g.out_degree(j) <= 1:
            out.update((i, j))
    return out


def bottleneck_tasks(g: PrecedenceGraph, min_degree: int = 4) -> list[int]:
    """Tasks that are the only direct follower of >= 2 of their direct predecessors
    and the only direct predecessor of >= 2 of their direct followers."""
    res = []
    for b in range(g.n):
        sole_pred = sum(g.out_degree(p) == 1 for p in g.pred[b])
        sole_succ = sum(g.in_degree(s) == 1 for s in g.succ[b])
        if sole_pred >= 2 and sole_succ >= 2 and g.in_degree(b) + g.out_degree(b) >= min_degree:
            res.append(b)
    return res


def stages(g: PrecedenceGraph) -> list[int]:
    """Stage (= depth, 1-based) of every task."""
    depth = [1] * g.n
    for v in g.topological_order():
        for w in g.succ[v]:
            depth[w] = max(depth[w], depth[v] + 1)
    return depth


def lower_bound(times: list[int], c: int) -> int:
    """max(LB1 = ceil(sum t / c), tasks > c/2 plus half of the tasks = c/2)."""
    lb1 = math.ceil(sum(times) / c)
    big = sum(t > c / 2 for t in times)
    half = sum(t == c / 2 for t in times)
    return max(lb1, big + math.ceil(half / 2))


def instance_stats(inst: Instance) -> dict:
    g = inst.graph()
    n = inst.n
    t = inst.task_times
    c = inst.cycle_time or max(t, default=1)
    indeg = [g.in_degree(v) for v in range(n)]
    outdeg = [g.out_degree(v) for v in range(n)]
    E = g.n_arcs
    s1 = sum(d == 0 for d in indeg)
    f = sum(d == 0 for d in outdeg)
    ed = E + s1 if s1 > 1 else E
    ec = E + f if f > 1 else E
    bn = bottleneck_tasks(g)
    st = stages(g) if n else []
    return {
        "name": inst.name,
        "n": n,
        "cycle_time": inst.cycle_time,
        # graph structure measures
        "order_strength": round(g.order_strength, 4),
        "arcs": E,
        "redundant_arcs_in_file": len(set(inst.arcs)) - E,
        "AIP": round(E / n, 3) if n else 0.0,
        "divergence": round(1 - (E + s1 - n) / ed, 4) if ed else 0.0,
        "convergence": round(1 - (E + f - n) / ec, 4) if ec else 0.0,
        "max_degree": max((a + b for a, b in zip(indeg, outdeg)), default=0),
        "stages": max(st, default=0),
        "no_pred_tasks": s1,
        "isolated": sum(a == 0 and b == 0 for a, b in zip(indeg, outdeg)),
        "chain_share": round(len(chain_tasks(g)) / n, 3) if n else 0.0,
        "bottleneck_share": round(len(bn) / n, 3) if n else 0.0,
        "bottleneck_avg_degree": round(statistics.fmean(indeg[b] + outdeg[b] for b in bn), 2) if bn else 0.0,
        # time structure measures
        "t_min": min(t, default=0),
        "t_max": max(t, default=0),
        "t_mean": round(statistics.fmean(t), 2) if t else 0.0,
        "t_std": round(statistics.pstdev(t), 2) if t else 0.0,
        "tmax/c": round(max(t) / c, 4) if t else 0.0,
        "time_variability": round(max(t) / min(t), 2) if t and min(t) > 0 else 0.0,
        "t_sum": sum(t),
        "sumtime_ratio": round(c / sum(t), 4) if sum(t) else 0.0,
        "lb": lower_bound(t, c) if c else 0,
    }
