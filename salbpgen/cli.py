"""Command line interface: ``salbpgen {generate,dataset,stats,trickiness}``."""

from __future__ import annotations

import argparse
import csv
import json
import sys

from .generator import (
    PAPER_BLOCKS, PAPER_SIZES, PAPER_TIME_DISTS, InstanceParams, generate_dataset, generate_instance,
)
from .instance import Instance
from .precedence import STRUCTURES
from .stats import instance_stats
from .times import DISTRIBUTIONS
from .trickiness import trickiness

_GRAPH_SCALARS = ("os_tolerance", "n_stages", "stage_size_sd", "n_chains", "chain_share",
                  "n_bottlenecks", "n_isolated", "max_pred", "max_succ", "max_attempts")
_GRAPH_PAIRS = ("chain_length", "bottleneck_in", "bottleneck_out")


def _add_graph_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("precedence graph (override the structure presets)")
    g.add_argument("--os-tolerance", type=float)
    g.add_argument("--n-stages", type=int)
    g.add_argument("--stage-size-sd", type=float)
    g.add_argument("--n-chains", type=int)
    g.add_argument("--chain-share", type=float)
    g.add_argument("--chain-length", type=int, nargs=2, metavar=("MIN", "MAX"))
    g.add_argument("--n-bottlenecks", type=int)
    g.add_argument("--bottleneck-in", type=int, nargs=2, metavar=("MIN", "MAX"))
    g.add_argument("--bottleneck-out", type=int, nargs=2, metavar=("MIN", "MAX"))
    g.add_argument("--n-isolated", type=int)
    g.add_argument("--max-pred", type=int)
    g.add_argument("--max-succ", type=int)
    g.add_argument("--max-attempts", type=int)


def _graph_opts(a: argparse.Namespace) -> dict:
    opts = {k: getattr(a, k) for k in _GRAPH_SCALARS if getattr(a, k) is not None}
    opts.update({k: tuple(getattr(a, k)) for k in _GRAPH_PAIRS if getattr(a, k)})
    return opts


def _block(s: str) -> tuple[str, float]:
    st, os_ = s.split(":")
    st = st.upper()
    if st not in STRUCTURES:
        raise argparse.ArgumentTypeError(f"structure must be one of {STRUCTURES}")
    return st, float(os_)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="salbpgen", description="SALBPGen instance generator (Otto et al., 2013)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate a single instance")
    g.add_argument("-n", type=int, required=True)
    g.add_argument("--os", type=float, required=True, help="target order strength")
    g.add_argument("--structure", choices=STRUCTURES, default="MIXED", type=str.upper)
    g.add_argument("--times", choices=tuple(DISTRIBUTIONS), default="BM", type=str.upper)
    g.add_argument("--cycle-time", type=int, default=1000)
    g.add_argument("--tmin", type=int, default=1)
    g.add_argument("--tmax", type=int)
    g.add_argument("--sum-multiple-of-c", action="store_true")
    g.add_argument("--seed", default=None)
    g.add_argument("-o", "--output", help="output .alb file (default: stdout)")
    _add_graph_args(g)

    d = sub.add_parser("dataset", help="generate a block design (default: the 2013 data sets)")
    d.add_argument("outdir")
    d.add_argument("--sizes", type=int, nargs="+", default=list(PAPER_SIZES))
    d.add_argument("--blocks", type=_block, nargs="+", default=list(PAPER_BLOCKS),
                   help="STRUCTURE:OS pairs, e.g. MIXED:0.2 CH:0.6 (default: the 7 blocks of the paper)")
    d.add_argument("--times", nargs="+", default=list(PAPER_TIME_DISTS), type=str.upper)
    d.add_argument("--replicates", type=int, default=25)
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--cycle-time", type=int, default=1000)
    d.add_argument("--keep-trivial", action="store_true", help="do not regenerate trivial instances")
    d.add_argument("--trivial-runs", type=int, default=10_000)
    d.add_argument("--permutations", type=int, default=0,
                   help="extra copies with permuted task times (9 for the 'medium permuted' set)")
    _add_graph_args(d)

    s = sub.add_parser("stats", help="structure measures of .alb files as CSV")
    s.add_argument("files", nargs="+")

    t = sub.add_parser("trickiness", help="estimate the trickiness of .alb files")
    t.add_argument("files", nargs="+")
    t.add_argument("--runs", type=int, default=10_000)
    t.add_argument("--optimum", type=int, help="known optimal number of stations (single file)")
    t.add_argument("--seed", default=None)

    a = ap.parse_args(argv)

    if a.cmd == "generate":
        p = InstanceParams(a.n, a.os, a.structure, a.times, a.cycle_time, a.tmin, a.tmax,
                           a.sum_multiple_of_c, _graph_opts(a))
        inst = generate_instance(p, a.seed)
        for w in inst.meta["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
        if a.output:
            inst.write(a.output)
        else:
            sys.stdout.write(inst.to_alb())
    elif a.cmd == "dataset":
        generate_dataset(
            a.outdir, a.sizes, a.blocks, a.times, a.replicates, a.seed, a.cycle_time,
            exclude_trivial=not a.keep_trivial, trivial_runs=a.trivial_runs,
            permutations=a.permutations, graph=_graph_opts(a),
            progress=lambda k, total, name: print(f"[{k}/{total}] {name}", file=sys.stderr),
        )
    elif a.cmd == "stats":
        rows = [instance_stats(Instance.read(f)) for f in a.files]
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    else:
        for f in a.files:
            res = trickiness(Instance.read(f), a.runs, a.optimum, a.seed)
            print(json.dumps({"file": f, **res}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
