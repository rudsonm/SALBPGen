"""Module connector (optional third part of SALBPGen, Section 5.1).

Single graphs are connected as modules l = 1..m according to a (super)
adjacency matrix M: if M[a][b] = 1, every task of module a precedes every task
of module b (the paper uses the transitive closure of the meta graph). This is
realised by arcs from the tasks without followers of module a to the tasks
without predecessors of module b; redundant arcs are dropped.

The automatic generation of M for a desired order strength, mentioned in the
paper, is not implemented.
"""

from __future__ import annotations

from .graph import PrecedenceGraph
from .instance import Instance


def _module_order(M: list[list[int]]) -> list[int]:
    m = len(M)
    indeg = [sum(M[a][b] for a in range(m) if a != b) for b in range(m)]
    ready = [b for b in range(m) if indeg[b] == 0]
    order = []
    while ready:
        a = ready.pop(0)
        order.append(a)
        for b in range(m):
            if b != a and M[a][b]:
                indeg[b] -= 1
                if indeg[b] == 0:
                    ready.append(b)
    if len(order) != m:
        raise ValueError("module matrix contains a cycle")
    return order


def connect_modules(modules: list[Instance], M: list[list[int]], cycle_time: int | None = None,
                    name: str = "") -> Instance:
    m = len(modules)
    if len(M) != m or any(len(row) != m for row in M):
        raise ValueError("M must be an m x m matrix")
    order = _module_order(M)
    offset, start = 0, {}
    for a in order:
        start[a] = offset
        offset += modules[a].n
    n = offset
    g = PrecedenceGraph(n)
    times = [0] * n
    sources, sinks = {}, {}
    for a, mod in enumerate(modules):
        o = start[a]
        for k, t in enumerate(mod.task_times):
            times[o + k] = t
        mg = mod.graph()
        for i, j in mg.arcs():
            if not g.reaches(o + i, o + j):
                g.add_arc(o + i, o + j)
        sources[a] = [o + v for v in range(mod.n) if mg.in_degree(v) == 0]
        sinks[a] = [o + v for v in range(mod.n) if mg.out_degree(v) == 0]
    # closure of M, so that "precedes" is transitive in the meta graph as well
    C = [[bool(M[a][b]) and a != b for b in range(m)] for a in range(m)]
    for k in range(m):
        for a in range(m):
            if C[a][k]:
                for b in range(m):
                    C[a][b] = C[a][b] or C[k][b]
    for a in order:  # topological order keeps the generated arcs non-redundant
        for b in order:
            if C[a][b]:
                for u in sinks[a]:
                    for v in sources[b]:
                        if not g.reaches(u, v):
                            g.add_arc(u, v)
    c = cycle_time or max(mod.cycle_time for mod in modules)
    arcs = [(i + 1, j + 1) for i, j in g.arcs()]
    return Instance(n, c, times, arcs, name=name, meta={"modules": [start[a] + 1 for a in range(m)]})
