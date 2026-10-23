"""High-level API: generate single instances or a full-factorial data set."""

from __future__ import annotations

import csv
import itertools
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .instance import Instance
from .precedence import GraphParams, generate_precedence_graph
from .stats import instance_stats
from .times import generate_task_times


@dataclass
class InstanceParams:
    n: int
    order_strength: float
    structure: str = "MIXED"  # MIXED | BN | CH
    time_dist: str = "PM"  # PB | PM | BM
    cycle_time: int = 1000
    tmin: int = 1
    tmax: int | None = None  # None -> cycle_time
    graph: dict = field(default_factory=dict)  # extra GraphParams fields

    def graph_params(self) -> GraphParams:
        return GraphParams(self.n, self.order_strength, self.structure, **self.graph)


def generate_instance(params: InstanceParams, seed: int | str | None = None, name: str = "") -> Instance:
    """Generate one instance. The same (params, seed) always gives the same instance."""
    rng = random.Random(seed)
    res = generate_precedence_graph(params.graph_params(), rng)
    tmax = params.tmax if params.tmax is not None else params.cycle_time
    times = generate_task_times(params.n, params.time_dist, rng, params.tmin, tmax)
    arcs = [(i + 1, j + 1) for i, j in res.graph.arcs()]
    meta = {
        "seed": seed,
        "params": asdict(params),
        "bottlenecks": [b + 1 for b in res.bottlenecks],
        "chains": [[v + 1 for v in ch] for ch in res.chains],
        "warnings": res.warnings,
    }
    return Instance(params.n, params.cycle_time, times, arcs, name=name, meta=meta)


def instance_name(n: int, os_: float, structure: str, dist: str, rep: int) -> str:
    return f"n={n}_os={os_:g}_{structure}_{dist}_{rep:03d}"


def generate_dataset(
    outdir: str | Path,
    sizes=(20, 50, 100, 1000),
    order_strengths=(0.2, 0.6, 0.9),
    structures=("MIXED", "BN", "CH"),
    time_dists=("PB", "PM", "BM"),
    replicates: int = 1,
    seed: int = 0,
    cycle_time: int = 1000,
    graph: dict | None = None,
    progress=None,
) -> list[dict]:
    """Full-factorial design; writes one ``.alb`` per instance plus ``index.csv``."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    combos = list(itertools.product(sizes, order_strengths, structures, time_dists, range(1, replicates + 1)))
    for k, (n, os_, st, td, rep) in enumerate(combos, 1):
        name = instance_name(n, os_, st, td, rep)
        inst_seed = f"{seed}:{name}"  # independent, reproducible stream per instance
        p = InstanceParams(n, os_, st, td, cycle_time=cycle_time, graph=dict(graph or {}))
        inst = generate_instance(p, inst_seed, name)
        inst.write(outdir / f"{name}.alb")
        row = {
            "name": name,
            "target_os": os_,
            "structure": st,
            "time_dist": td,
            "replicate": rep,
            "seed": inst_seed,
            **{k2: v for k2, v in instance_stats(inst).items() if k2 != "name"},
            "warnings": " | ".join(inst.meta["warnings"]),
        }
        rows.append(row)
        if progress:
            progress(k, len(combos), name)
    with open(outdir / "index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows
