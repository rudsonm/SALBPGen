"""Descriptive statistics of an instance, e.g. to compare generated instances
with the original benchmark files."""

from __future__ import annotations

import math
import statistics

from .instance import Instance


def instance_stats(inst: Instance, bottleneck_degree: int = 4) -> dict:
    g = inst.graph()
    n = inst.n
    indeg = [g.in_degree(v) for v in range(n)]
    outdeg = [g.out_degree(v) for v in range(n)]
    t = inst.task_times
    c = inst.cycle_time or max(t, default=1)
    return {
        "name": inst.name,
        "n": n,
        "cycle_time": inst.cycle_time,
        "order_strength": round(g.order_strength, 4),
        "arcs": g.n_arcs,
        "redundant_arcs_in_file": len(inst.arcs) - g.n_arcs,
        "levels": g.longest_path_nodes(),
        "sources": sum(d == 0 for d in indeg),
        "sinks": sum(d == 0 for d in outdeg),
        "isolated": sum(a == 0 and b == 0 for a, b in zip(indeg, outdeg)),
        "max_pred": max(indeg, default=0),
        "max_succ": max(outdeg, default=0),
        "avg_degree": round(g.n_arcs / n, 3) if n else 0.0,
        # tasks with exactly one predecessor and one successor (chain interiors)
        "chain_share": round(sum(a == 1 and b == 1 for a, b in zip(indeg, outdeg)) / n, 3),
        "bottlenecks": sum(
            a >= bottleneck_degree and b >= bottleneck_degree for a, b in zip(indeg, outdeg)
        ),
        "t_min": min(t, default=0),
        "t_max": max(t, default=0),
        "t_mean": round(statistics.fmean(t), 2) if t else 0.0,
        "t_sum": sum(t),
        "share_t_gt_c/2": round(sum(x > c / 2 for x in t) / n, 3),
        "share_t_gt_c/3": round(sum(x > c / 3 for x in t) / n, 3),
        "lb1": math.ceil(sum(t) / c) if c else 0,  # SALBP-1 capacity bound
    }
