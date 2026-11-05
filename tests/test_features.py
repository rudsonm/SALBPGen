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
    crit = [f for f in inst.features if f.critical]
    assert len(crit) == 2
    for f in crit:
        cp = fast_cp(inst, f.tasks)
        assert cp == f.critical_path_fast
        assert ratio * T <= cp < ratio * T + math.ceil(21 / 1.4)
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
    f = next(f for f in inst.features if f.critical)
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
