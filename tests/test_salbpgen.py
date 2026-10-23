import random

import pytest

from salbpgen import (
    PAPER_BLOCKS,
    GraphParams,
    Instance,
    InstanceParams,
    PrecedenceGraph,
    bottleneck_tasks,
    chain_tasks,
    connect_modules,
    default_stages,
    generate_dataset,
    generate_instance,
    generate_precedence_graph,
    generate_task_times,
    instance_stats,
    is_trivial,
    max_flexibility_stages,
    os_max,
    os_min,
    structure_preset,
    trickiness,
)
from salbpgen.graph import nth_set_bit
from salbpgen.precedence import TABLE3_STAGES
from salbpgen.stats import stages


def brute_force_os(n, arcs):
    succ = [[] for _ in range(n)]
    for i, j in arcs:
        succ[i].append(j)
    reach = [set() for _ in range(n)]
    for v in reversed(range(n)):  # arcs go forward in the numbering
        for w in succ[v]:
            reach[v] |= {w} | reach[w]
    return sum(map(len, reach)) / (n * (n - 1) / 2)


# ------------------------------------------------------------------- graph
def test_nth_set_bit():
    x = 0b1011_0100
    assert [nth_set_bit(x, k) for k in range(x.bit_count())] == [2, 4, 5, 7]


def test_closure_and_reduction():
    g = PrecedenceGraph(4)
    g.add_arc(0, 2)
    g.add_arc(2, 3)
    g.add_arc(0, 1)
    assert g.gain(1, 2) == 2  # new pairs (1, 2) and (1, 3)
    assert g.add_arc(1, 2) == [(0, 2)]  # 0->2 now implied by 0->1->2
    assert g.arcs() == [(0, 1), (1, 2), (2, 3)]
    assert g.order_strength == 1.0
    g.remove_arc(1, 2)
    assert g.closure_size == 2


# --------------------------------------------------------- Theorem 1 / Table 3
@pytest.mark.parametrize("n,K", sorted(TABLE3_STAGES.items()))
def test_table3_matches_theorem(n, K):
    best = max(range(1, n + 1), key=lambda k: os_max(n, k) - os_min(n, k))
    rule = min(range(1, n + 1), key=lambda k: abs(k * k * (2 * k - 1) - n * n))
    assert rule == K
    assert abs(best - K) <= 1  # discrete maximiser of OSmax - OSmin
    assert max_flexibility_stages(n) == K


def test_default_stages_extreme_os():
    assert default_stages(100, 0.6) == 17
    assert default_stages(20, 0.9) == 18  # 0.9 > OSmax(20, 6) -> linear rule


# ------------------------------------------------------------ precedence
@pytest.mark.parametrize("n", [20, 50, 100])
@pytest.mark.parametrize("structure,os_", PAPER_BLOCKS)
def test_paper_blocks(structure, os_, n):
    p = GraphParams(n, os_, **structure_preset(structure, n))
    res = generate_precedence_graph(p, random.Random(7))
    g = res.graph
    arcs = g.arcs()
    assert all(i < j for i, j in arcs)  # topological numbering
    tol = max(1, int(p.os_tolerance * g.max_pairs)) / g.max_pairs
    assert abs(g.order_strength - os_) <= tol + 1e-12
    assert brute_force_os(n, arcs) == pytest.approx(g.order_strength)
    for i, j in arcs:  # transitively reduced
        assert not any(g.reaches(k, j) for k in g.succ[i] if k != j)
    # stages: depth of every task equals its generated stage
    assert stages(g) == res.stages
    assert all(res.stages[i] < res.stages[j] for i, j in arcs)
    if structure == "CH":
        assert len(chain_tasks(g)) >= 0.4 * n
    if structure == "BN":
        bn = set(bottleneck_tasks(g, min_degree=4 if n <= 20 else 8))
        assert set(res.bottlenecks) <= bn and bn


def test_isolated_and_explicit_structures():
    p = GraphParams(60, 0.5, n_chains=3, n_bottlenecks=1, bottleneck_in=(3, 3),
                    bottleneck_out=(3, 3), n_isolated=2)
    res = generate_precedence_graph(p, 1)
    g = res.graph
    for v in res.isolated:
        assert g.in_degree(v) == 0 and g.out_degree(v) == 0
    for ch in res.chains:
        assert set(ch) <= chain_tasks(g)
    (b,) = res.bottlenecks
    assert g.in_degree(b) >= 3 and g.out_degree(b) >= 3
    assert b in bottleneck_tasks(g)


# ------------------------------------------------------------------ times
@pytest.mark.parametrize("dist", ["PB", "PM", "BM"])
def test_task_times(dist):
    t = generate_task_times(3000, dist, 1, cycle_time=1000)
    assert all(1 <= x <= 1000 for x in t)
    small = sum(x < 300 for x in t) / len(t)
    mean = sum(t) / len(t)
    if dist == "PB":
        assert small > 0.9
    elif dist == "PM":
        assert 450 < mean < 550
    else:
        assert 0.55 < small < 0.8  # higher peak at small tasks


def test_sum_multiple_of_c():
    for seed in range(20):
        t = generate_task_times(37, "BM", seed, cycle_time=1000, sum_multiple_of_c=True)
        assert sum(t) % 1000 == 0 and all(1 <= x <= 1000 for x in t)


# --------------------------------------------------------- instance / io
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
    assert s["n"] == 50 and s["redundant_arcs_in_file"] == 0 and s["bottleneck_share"] > 0


def test_structure_measures_on_paper_example():
    # Fig. 2: tasks 2, 6, 8, 12 form the only chain; 7 is a bottleneck of degree 6
    arcs = [(1, 2), (1, 3), (1, 4), (1, 5), (2, 6), (3, 7), (4, 7), (5, 7), (6, 8), (7, 9),
            (7, 10), (7, 11), (8, 12), (9, 13), (10, 13), (11, 13), (12, 13)]
    inst = Instance(13, 10, [1] * 13, arcs)
    g = inst.graph()
    assert sorted(v + 1 for v in chain_tasks(g)) == [2, 6, 8, 12]
    assert [b + 1 for b in bottleneck_tasks(g)] == [7]
    assert max(stages(g)) == 6


# ------------------------------------------------------------- trickiness
def test_trickiness_trivial_and_tricky():
    chain = Instance(4, 10, [5, 5, 5, 5], [(1, 2), (2, 3), (3, 4)])
    assert is_trivial(chain, 200)
    assert trickiness(chain, 200)["category"] == "trivial"
    # free tasks 6,6,4,4 with c=10: optimum 2 stations, random packing often needs 3
    free = Instance(4, 10, [6, 6, 4, 4], [])
    r = trickiness(free, 2000, seed=1)
    assert r["optimum"] == 2 and 0 < r["tr"] < 1
    assert not is_trivial(free, 2000, seed=1)


# ---------------------------------------------------------------- modules
def test_connect_modules():
    a = Instance(2, 10, [1, 2], [(1, 2)])
    b = Instance(3, 10, [3, 4, 5], [(1, 3)])
    c = Instance(1, 10, [6], [])
    M = [[0, 1, 0], [0, 0, 1], [0, 0, 0]]  # a -> b -> c
    inst = connect_modules([a, b, c], M)
    g = inst.graph()
    assert inst.n == 6 and g.order_strength == pytest.approx(brute_force_os(6, g.arcs()))
    # every task of a precedes every task of c
    assert all(g.reaches(i, 5) for i in range(2))
    assert inst.task_times == [1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------------- dataset
def test_dataset(tmp_path):
    rows = generate_dataset(tmp_path, sizes=[20], blocks=[("MIXED", 0.6), ("CH", 0.2)],
                            time_dists=["PM"], replicates=2, seed=5, permutations=2, trivial_runs=500)
    assert len(rows) == 2 * 2 * 3
    assert len(list(tmp_path.glob("*.alb"))) == 12
    assert (tmp_path / "index.csv").exists()
    base = Instance.read(tmp_path / "n=20_MIXED_os=0.6_PM_001.alb")
    perm = Instance.read(tmp_path / "n=20_MIXED_os=0.6_PM_001_p01.alb")
    assert sorted(base.arcs) == sorted(perm.arcs) and sorted(base.task_times) == sorted(perm.task_times)
    assert not is_trivial(base, 500, "x")
