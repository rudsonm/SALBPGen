"""Command line interface: ``salbpgen {generate,dataset,stats}``."""

from __future__ import annotations

import argparse
import csv
import sys

from .generator import InstanceParams, generate_dataset, generate_instance
from .instance import Instance
from .precedence import STRUCTURES
from .stats import instance_stats
from .times import DISTRIBUTIONS


def _graph_opts(a: argparse.Namespace) -> dict:
    opts = {}
    for key in ("os_tolerance", "max_pred", "max_succ", "n_bottlenecks", "chain_share"):
        v = getattr(a, key)
        if v is not None:
            opts[key] = v
    if a.bottleneck_degree:
        opts["bottleneck_degree"] = tuple(a.bottleneck_degree)
    if a.chain_length:
        opts["chain_length"] = tuple(a.chain_length)
    return opts


def _add_graph_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("precedence graph")
    g.add_argument("--os-tolerance", type=float)
    g.add_argument("--max-pred", type=int)
    g.add_argument("--max-succ", type=int)
    g.add_argument("--n-bottlenecks", type=int)
    g.add_argument("--bottleneck-degree", type=int, nargs=2, metavar=("MIN", "MAX"))
    g.add_argument("--chain-share", type=float)
    g.add_argument("--chain-length", type=int, nargs=2, metavar=("MIN", "MAX"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="salbpgen", description="SALBPGen-style instance generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate a single instance")
    g.add_argument("-n", type=int, required=True)
    g.add_argument("--os", type=float, required=True, help="target order strength")
    g.add_argument("--structure", choices=STRUCTURES, default="MIXED", type=str.upper)
    g.add_argument("--times", choices=tuple(DISTRIBUTIONS), default="PM", type=str.upper)
    g.add_argument("--cycle-time", type=int, default=1000)
    g.add_argument("--tmin", type=int, default=1)
    g.add_argument("--tmax", type=int)
    g.add_argument("--seed", default=None)
    g.add_argument("-o", "--output", help="output .alb file (default: stdout)")
    _add_graph_args(g)

    d = sub.add_parser("dataset", help="generate a full-factorial data set")
    d.add_argument("outdir")
    d.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 1000])
    d.add_argument("--os", type=float, nargs="+", default=[0.2, 0.6, 0.9])
    d.add_argument("--structures", nargs="+", default=list(STRUCTURES), type=str.upper)
    d.add_argument("--times", nargs="+", default=list(DISTRIBUTIONS), type=str.upper)
    d.add_argument("--replicates", type=int, default=1)
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--cycle-time", type=int, default=1000)
    _add_graph_args(d)

    s = sub.add_parser("stats", help="print statistics of .alb files as CSV")
    s.add_argument("files", nargs="+")

    a = ap.parse_args(argv)

    if a.cmd == "generate":
        p = InstanceParams(a.n, a.os, a.structure, a.times, a.cycle_time, a.tmin, a.tmax, _graph_opts(a))
        inst = generate_instance(p, a.seed)
        for w in inst.meta["warnings"]:
            print(f"warning: {w}", file=sys.stderr)
        if a.output:
            inst.write(a.output)
        else:
            sys.stdout.write(inst.to_alb())
    elif a.cmd == "dataset":
        def progress(k, total, name):
            print(f"[{k}/{total}] {name}", file=sys.stderr)

        generate_dataset(
            a.outdir, a.sizes, a.os, a.structures, a.times, a.replicates, a.seed,
            a.cycle_time, _graph_opts(a), progress,
        )
    else:
        rows = [instance_stats(Instance.read(f)) for f in a.files]
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
