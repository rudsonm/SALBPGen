"""High-level API: single instances and the 2013 data set design (Section 5.3)."""

from __future__ import annotations

import csv
import itertools
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .instance import Instance
from .precedence import GraphParams, generate_precedence_graph, structure_preset
from .stats import instance_stats
from .times import generate_task_times
from .trickiness import is_trivial


@dataclass
class InstanceParams:
    n: int
    order_strength: float
    structure: str = "MIXED"  # MIXED | BN | CH (presets of the 2013 data sets)
    time_dist: str = "BM"  # PB | BM | PM (BM is the SALBPGen default)
    cycle_time: int = 1000
    tmin: int = 1
    tmax: int | None = None  # None -> cycle time
    sum_multiple_of_c: bool = False
    graph: dict = field(default_factory=dict)  # overrides of GraphParams fields

    def graph_params(self) -> GraphParams:
        opts = {**structure_preset(self.structure, self.n), **self.graph}
        return GraphParams(self.n, self.order_strength, **opts)


def generate_instance(params: InstanceParams, seed: int | str | None = None, name: str = "") -> Instance:
    """Generate one instance; the same (params, seed) always gives the same instance."""
    rng = random.Random(seed)
    res = generate_precedence_graph(params.graph_params(), rng)
    times = generate_task_times(params.n, params.time_dist, rng, params.cycle_time,
                                params.tmin, params.tmax, params.sum_multiple_of_c)
    arcs = [(i + 1, j + 1) for i, j in res.graph.arcs()]
    meta = {
        "seed": seed,
        "params": asdict(params),
        "n_stages": res.n_stages,
        "attempts": res.attempts,
        "bottlenecks": [b + 1 for b in res.bottlenecks],
        "chains": [[v + 1 for v in ch] for ch in res.chains],
        "warnings": res.warnings,
    }
    return Instance(params.n, params.cycle_time, times, arcs, name=name, meta=meta)


def permute_times(inst: Instance, rng: random.Random, name: str = "") -> Instance:
    """Same graph, randomly permuted assignment of task times ("medium permuted" set)."""
    times = inst.task_times[:]
    rng.shuffle(times)
    return Instance(inst.n, inst.cycle_time, times, list(inst.arcs), name=name, meta=dict(inst.meta))


# (graph structure, order strength) blocks of the 2013 data sets (Table 4)
PAPER_BLOCKS = (
    ("MIXED", 0.2), ("MIXED", 0.6), ("MIXED", 0.9),
    ("CH", 0.2), ("CH", 0.6),
    ("BN", 0.2), ("BN", 0.6),
)
PAPER_SIZES = (20, 50, 100, 1000)
PAPER_TIME_DISTS = ("PB", "BM", "PM")


def instance_name(n: int, os_: float, structure: str, dist: str, rep: int) -> str:
    return f"n={n}_{structure}_os={os_:g}_{dist}_{rep:03d}"


def generate_dataset(
    outdir: str | Path,
    sizes=PAPER_SIZES,
    blocks=PAPER_BLOCKS,
    time_dists=PAPER_TIME_DISTS,
    replicates: int = 25,
    seed: int = 0,
    cycle_time: int = 1000,
    exclude_trivial: bool = True,
    trivial_runs: int = 10_000,
    permutations: int = 0,
    graph: dict | None = None,
    progress=None,
) -> list[dict]:
    """Generate a block design (default: the 2013 data sets, 525 instances per size).

    Trivial instances (all random max-load solutions have the same number of
    stations) are regenerated when ``exclude_trivial`` is set. ``permutations``
    adds that many copies of each instance with permuted task times (the paper
    uses 9 for the "medium permuted" set). Writes ``.alb`` files and ``index.csv``.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    combos = list(itertools.product(sizes, blocks, time_dists, range(1, replicates + 1)))
    for k, (n, (st, os_), td, rep) in enumerate(combos, 1):
        name = instance_name(n, os_, st, td, rep)
        p = InstanceParams(n, os_, st, td, cycle_time=cycle_time, graph=dict(graph or {}))
        regenerations = 0
        while True:
            inst_seed = f"{seed}:{name}:{regenerations}"
            inst = generate_instance(p, inst_seed, name)
            if not exclude_trivial or not is_trivial(inst, trivial_runs, inst_seed):
                break
            regenerations += 1
        variants = [inst]
        prng = random.Random(f"{inst_seed}:perm")
        variants += [permute_times(inst, prng, f"{name}_p{q:02d}") for q in range(1, permutations + 1)]
        for v in variants:
            v.write(outdir / f"{v.name}.alb")
            rows.append({
                "name": v.name, "structure": st, "target_os": os_, "time_dist": td, "replicate": rep,
                "seed": inst_seed, "n_stages_generated": inst.meta["n_stages"],
                "attempts": inst.meta["attempts"], "trivial_regenerations": regenerations,
                **{key: val for key, val in instance_stats(v).items() if key != "name"},
            })
        if progress:
            progress(k, len(combos), name)
    with open(outdir / "index.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows
