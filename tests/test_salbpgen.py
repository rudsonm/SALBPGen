import random

import pytest

from salbpgen import (
    GraphParams,
    Instance,
    InstanceParams,
    PrecedenceGraph,
    generate_dataset,
    generate_instance,
    generate_precedence_graph,
    generate_task_times,
    instance_stats,
)
from salbpgen.graph import nth_set_bit


def brute_force_os(n, arcs):
    reach = [set() for _ in range(n)]
    succ = [[] for _ in range(n)]
    for i, j in arcs:
        succ[i].append(j)
    for v in reversed(range(n)):  # arcs go forward in the numbering
        for w in succ[v]:
            reach[v] |= {w} | reach[w]
    return sum(map(len, reach)) / (n * (n - 1) / 2)


def test_nth_set_bit():
    x = 0b1011_0100
    assert [nth_set_bit(x, k) for k in range(x.bit_count())] == [2, 4, 5, 7]


def test_closure_and_reduction():
    g = PrecedenceGraph(4)
    g.add_arc(0, 2)
    g.add_arc(2, 3)
    removed = g.add_arc(0, 1)
    assert removed == []
    assert g.gain(1, 2) == 2  # new pairs (1, 2) and (1, 3)
    removed = g.add_arc(1, 2)
    assert removed == [(0, 2)]  # 0->2 now implied by 0->1->2
    assert g.arcs() == [(0, 1), (1, 2), (2, 3)]
    assert g.order_strength == 1.0
    g.remove_arc(1, 2)
    assert g.closure_size == 2  # (0,1), (2,3)


def test_gain_counts_new_pairs():
    g = PrecedenceGraph(4)
    g.add_arc(0, 1)
    g.add_arc(2, 3)
    assert g.gain(1, 2) == 4  # {0,1} x {2,3}


@pytest.mark.parametrize("structure", ["MIXED", "BN", "CH"])
@pytest.mark.parametrize("n", [20, 50, 100])
@pytest.mark.parametrize("os_", [0.2, 0.6, 0.9])
def test_order_strength_hit(structure, n, os_):
    p = GraphParams(n, os_, structure)
    res = generate_precedence_graph(p, random.Random(7))
    g = res.graph
    arcs = g.arcs()
    assert all(i < j for i, j in arcs)  # topological numbering
    tol = max(1, int(p.os_tolerance * g.max_pairs)) / g.max_pairs
    assert abs(g.order_strength - os_) <= tol + 1e-12, res.warnings
    assert brute_force_os(n, arcs) == pytest.approx(g.order_strength)
    # transitively reduced: no arc implied by another path
    for i, j in arcs:
        assert not any(g.reaches(k, j) for k in g.succ[i] if k != j)


def test_chain_structure_preserved():
    res = generate_precedence_graph(GraphParams(100, 0.6, "CH"), 3)
    g = res.graph
    assert res.chains
    for chain in res.chains:
        for a, b in zip(chain, chain[1:]):
            assert g.succ[a] == {b} and g.pred[b] == {a}


def test_bottlenecks_stand_out():
    res = generate_precedence_graph(GraphParams(100, 0.6, "BN"), 3)
    g = res.graph
    assert len(res.bottlenecks) == 2
    for b in res.bottlenecks:
        assert g.in_degree(b) >= 4 and g.out_degree(b) >= 4
    others = [v for v in range(100) if v not in res.bottlenecks]
    assert max(g.in_degree(v) for v in others) <= 3
    assert max(g.out_degree(v) for v in others) <= 3


@pytest.mark.parametrize("dist", ["PB", "PM", "BM"])
def test_task_times(dist):
    t = generate_task_times(2000, dist, 1, tmin=1, tmax=1000)
    assert all(1 <= x <= 1000 for x in t)
    mean = sum(t) / len(t)
    if dist == "PB":
        assert mean < 200
    elif dist == "PM":
        assert 450 < mean < 550
    else:
        low = sum(x < 300 for x in t) / len(t)
        assert 0.35 < low < 0.65


def test_alb_roundtrip_and_determinism(tmp_path):
    p = InstanceParams(50, 0.6, "BN", "BM")
    a = generate_instance(p, seed=11, name="x")
    b = generate_instance(p, seed=11, name="x")
    assert a.to_alb() == b.to_alb()
    path = tmp_path / "x.alb"
    a.write(path)
    r = Instance.read(path)
    assert (r.n, r.cycle_time, r.task_times, sorted(r.arcs)) == (a.n, a.cycle_time, a.task_times, sorted(a.arcs))
    assert r.meta["order_strength_file"] == pytest.approx(a.order_strength, abs=5e-4)
    s = instance_stats(r)
    assert s["n"] == 50 and s["redundant_arcs_in_file"] == 0


def test_dataset(tmp_path):
    rows = generate_dataset(tmp_path, sizes=[20], order_strengths=[0.2, 0.9], structures=["CH"],
                            time_dists=["PB", "PM"], replicates=2, seed=5)
    assert len(rows) == 8
    assert len(list(tmp_path.glob("*.alb"))) == 8
    assert (tmp_path / "index.csv").exists()
