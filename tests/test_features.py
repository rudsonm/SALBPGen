import math

import pytest

from salbpgen import FeatureParams, critical_path, generate_nrps
from salbpgen.features import _longest


def fast_cp(inst, tasks):
    idx = {r: k for k, r in enumerate(tasks)}
    arcs = [(idx[u], idx[v]) for u, v in inst.arcs if u in idx and v in idx]
    return max(_longest(len(tasks), arcs, lambda k: math.ceil(inst.durations[tasks[k]] / 1.4))[0])


@pytest.mark.parametrize("T,ratio", [(40, 1.2), (80, 1.5), (120, 0.8)])
def test_critical_features_hit_target(T, ratio):
    inst = generate_nrps(FeatureParams(400, T, n_critical=2, cp_ratio=ratio), seed=3)
    crit = [f for f in inst.features if f.controlled]
    assert len(crit) == 2
    for f in crit:
        assert f.critical == (f.critical_path_fast > T)
        cp = fast_cp(inst, f.tasks)
        assert cp == f.critical_path_fast
        assert ratio * T <= cp < ratio * T + math.ceil(13 / 1.4)
    assert critical_path(inst) >= max(f.critical_path_fast for f in crit)


def test_partition_acyclic_and_values():
    inst = generate_nrps(FeatureParams(300, 40), seed=1)
    tasks = sorted(r for f in inst.features for r in f.tasks)
    assert tasks == list(range(300)) == list(range(inst.n))
    assert len(inst.values) == 300 and min(inst.values) >= 1
    _longest(inst.n, inst.arcs, lambda r: 1)  # raises on a cycle
    assert all(u != v for u, v in inst.arcs)


def test_alpha_puts_value_at_the_end():
    inst = generate_nrps(FeatureParams(200, 40, alpha=3.0), seed=2)
    f = next(f for f in inst.features if f.controlled)
    idx = {r: k for k, r in enumerate(f.tasks)}
    arcs = [(idx[u], idx[v]) for u, v in inst.arcs if u in idx and v in idx]
    _, depth = _longest(len(f.tasks), arcs, lambda k: 0)
    first = [inst.values[f.tasks[k]] for k, d in enumerate(depth) if d == 1]
    last = [inst.values[f.tasks[k]] for k, d in enumerate(depth) if d == max(depth)]
    assert max(first) < min(last)


def test_reproducible():
    p = FeatureParams(150, 40)
    a, b = generate_nrps(p, seed="x"), generate_nrps(p, seed="x")
    assert (a.durations, a.values, a.arcs) == (b.durations, b.values, b.arcs)


def test_write_classic_format(tmp_path):
    inst = generate_nrps(FeatureParams(120, 40), seed=5)
    path = tmp_path / "x.nrp"
    inst.write(path)
    tok = path.read_text().split()
    assert tok[:2] == ["1", "120"]
    assert list(map(int, tok[2:122])) == inst.durations
    n_dep = int(tok[122])
    deps = [(int(tok[123 + 2 * k]), int(tok[124 + 2 * k])) for k in range(n_dep)]
    # nrp_instance.py reads "a b" as (predecessor, successor) = (b-1, a-1)
    assert sorted((b - 1, a - 1) for a, b in deps) == sorted(inst.arcs)
    pos, value = 123 + 2 * n_dep, [0] * 120
    n_cli = int(tok[pos])
    pos += 1
    for _ in range(n_cli):
        w, k = int(tok[pos]), int(tok[pos + 1])
        for r in tok[pos + 2: pos + 2 + k]:
            value[int(r) - 1] += w
        pos += 2 + k
    assert value == inst.values
    assert (tmp_path / "x.json").exists()


def test_too_small_for_critical_features():
    with pytest.raises(ValueError):
        generate_nrps(FeatureParams(5, 160, n_critical=1), seed=0)


def test_read_roundtrip(tmp_path):
    from salbpgen import NRPSInstance
    inst = generate_nrps(FeatureParams(150, 40), seed=7)
    inst.write(tmp_path / "y.nrp")
    back = NRPSInstance.read(tmp_path / "y.nrp")
    assert (back.durations, back.values, sorted(back.arcs)) == (inst.durations, inst.values, sorted(inst.arcs))
    assert back.features == inst.features and back.horizon == 40


def test_periods_per_sp_scales_durations():
    base = generate_nrps(FeatureParams(n_tasks=120, horizon=40, n_critical=0), seed=3)
    hours = generate_nrps(FeatureParams(n_tasks=120, horizon=40, n_critical=0, periods_per_sp=8), seed=3)
    assert hours.durations == [8 * h for h in base.durations]
    with pytest.raises(ValueError):
        FeatureParams(n_tasks=120, horizon=40, periods_per_sp=0.5)


def test_critical_flag_marks_every_feature_longer_than_T():
    inst = generate_nrps(FeatureParams(600, 40, n_critical=1, periods_per_sp=8), seed=1)
    for f in inst.features:
        assert f.critical == (fast_cp(inst, f.tasks) > 40)
    assert sum(f.critical for f in inst.features) > sum(f.controlled for f in inst.features)


def test_value_mode_uncorrelated_breaks_value_effort_link():
    import statistics
    from salbpgen.features import FeatureParams, generate_nrps

    def corr(inst):
        # per feature: value vs effort relative to size (both scale with the number of tasks)
        eff = [sum(inst.durations[r] for r in f.tasks) / len(f.tasks) for f in inst.features]
        val = [sum(inst.values[r] for r in f.tasks) / len(f.tasks) for f in inst.features]
        return statistics.correlation(eff, val)

    base = dict(n_tasks=600, horizon=160, n_critical=1, alpha=0.0, periods_per_sp=1)
    c = corr(generate_nrps(FeatureParams(**base), seed=3))
    u = corr(generate_nrps(FeatureParams(**base, value_mode="uncorrelated"), seed=3))
    assert c > 0.5 and abs(u) < 0.3


def test_feature_pool_tawos_copies_real_epics():
    from salbpgen.features import FeatureParams, _tawos_epics, generate_nrps

    inst = generate_nrps(FeatureParams(n_tasks=500, horizon=160, n_critical=1, feature_pool="tawos"), seed=7)
    shapes = {(e[0], tuple(map(tuple, e[1]))) for e in _tawos_epics()}
    arcs = set(inst.arcs)
    assert inst.n == 500
    for f in inst.features:
        if f.controlled:
            continue
        pos = {t: i for i, t in enumerate(f.tasks)}
        local = tuple(sorted((pos[u], pos[v]) for u, v in arcs if u in pos and v in pos))
        assert (len(f.tasks), local) in shapes


def test_clients_ask_for_features_and_set_values():
    from salbpgen.features import FeatureParams, generate_nrps

    p = FeatureParams(n_tasks=300, horizon=160, n_critical=2, clients=True, feature_pool="tawos")
    inst = generate_nrps(p, seed=5)
    clients = inst.meta["clients"]
    nf = len(inst.features)
    assert len(clients) == max(1, round(2.0 * nf / 3))
    demand = [0] * nf
    for c in clients:
        assert 1 <= c["weight"] <= 5
        for f, imp in c["requests"]:
            assert 0 <= f < nf and 1 <= imp <= 5
            demand[f] += c["weight"] * imp
    for f, feat in enumerate(inst.features):
        total = sum(inst.values[r] for r in feat.tasks)
        if feat.controlled:
            assert demand[f] > 0 and total > 0
        if demand[f] == 0:
            assert total == 0
    # same params and seed -> same instance
    assert generate_nrps(p, seed=5).values == inst.values


def test_without_clients_values_unchanged():
    from salbpgen.features import FeatureParams, generate_nrps

    inst = generate_nrps(FeatureParams(n_tasks=200, horizon=160, n_critical=1), seed=11)
    assert "clients" not in inst.meta and min(inst.values) >= 1


def test_fixed_number_of_clients():
    from salbpgen.features import FeatureParams, generate_nrps

    p = FeatureParams(n_tasks=300, horizon=160, n_critical=2, clients=True, feature_pool="tawos",
                      n_clients=100)
    inst = generate_nrps(p, seed=5)
    assert len(inst.meta["clients"]) == 100
    with pytest.raises(ValueError):
        FeatureParams(n_tasks=10, horizon=10, n_clients=0)


def test_critical_preference_shifts_demand_to_controlled_features():
    from salbpgen.features import FeatureParams, generate_nrps

    def share(beta):
        p = FeatureParams(n_tasks=600, horizon=160, n_critical=6, clients=True, feature_pool="tawos",
                          n_clients=300, critical_preference=beta)
        inst = generate_nrps(p, seed=3)
        ctrl = {i for i, f in enumerate(inst.features) if f.controlled}
        req = [f for c in inst.meta["clients"] for f, _ in c["requests"]]
        return sum(f in ctrl for f in req) / len(req)

    assert share(4.0) > 1.5 * share(1.0)
    with pytest.raises(ValueError):
        FeatureParams(n_tasks=10, horizon=10, critical_preference=0)


def test_clients_do_not_change_structure():
    from salbpgen.features import FeatureParams, generate_nrps

    def structure(**kw):
        p = FeatureParams(n_tasks=600, horizon=160, n_critical=4, clients=True, feature_pool="tawos", **kw)
        inst = generate_nrps(p, seed=1)
        return inst.durations, sorted(inst.arcs), [f.tasks for f in inst.features]

    base = structure(n_clients=100, critical_preference=1.0)
    assert structure(n_clients=100, critical_preference=4.0) == base
    assert structure(n_clients=300, critical_preference=1.0) == base
