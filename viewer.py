"""Visualizador de instâncias NRP-S: ``streamlit run viewer.py [-- pasta]``.

Lista os arquivos ``.nrp`` da pasta (padrão: ``instances``) com os parâmetros
do ``.json`` gerado por ``salbpgen nrps``. Ao selecionar uma instância, mostra
o grafo de precedência: uma feature por vez, ou a instância inteira, com o
caminho crítico (desenvolvedor mais rápido) em vermelho.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from salbpgen import NRPSInstance

MAX_NODES = 400  # acima disso o grafo da instância inteira fica lento no navegador

st.set_page_config(page_title="Instâncias NRP-S", layout="wide")


@st.cache_data
def load(path: str, mtime: float) -> NRPSInstance:
    return NRPSInstance.read(path)


def critical_nodes(n, arcs, w):
    """Nós e arcos de um caminho crítico (pesos nos nós)."""
    succ, pred, indeg = [[] for _ in range(n)], [[] for _ in range(n)], [0] * n
    for u, v in arcs:
        succ[u].append(v)
        pred[v].append(u)
        indeg[v] += 1
    stack, order = [v for v in range(n) if indeg[v] == 0], []
    while stack:
        u = stack.pop()
        order.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                stack.append(v)
    dist, back = [w(v) for v in range(n)], [None] * n
    for u in order:
        for v in succ[u]:
            if dist[u] + w(v) > dist[v]:
                dist[v], back[v] = dist[u] + w(v), u
    if not n:
        return set(), set(), 0
    v = max(range(n), key=dist.__getitem__)
    best, nodes, edges = dist[v], {v}, set()
    while back[v] is not None:
        edges.add((back[v], v))
        v = back[v]
        nodes.add(v)
    return nodes, edges, best


def dot(inst: NRPSInstance, tasks: list[int], speedup: float, clusters: bool) -> tuple[str, int]:
    idx = {r: k for k, r in enumerate(tasks)}
    arcs = [(idx[u], idx[v]) for u, v in inst.arcs if u in idx and v in idx]
    cn, ce, cp = critical_nodes(len(tasks), arcs, lambda k: math.ceil(inst.durations[tasks[k]] / speedup))
    vmax = max((inst.values[r] for r in tasks), default=1)
    feat_of = {r: i for i, f in enumerate(inst.features) for r in f.tasks}
    lines = ['digraph G { rankdir=LR; node [shape=box style="rounded,filled" fontsize=10 fontname=Helvetica];']

    def node(k):
        r = tasks[k]
        shade = 95 - round(45 * inst.values[r] / vmax)  # mais escuro = mais valor
        color = 'color="#d62728" penwidth=2' if k in cn else 'color="#888888"'
        return (f'n{r} [label="{r + 1}\\nh={inst.durations[r]} v={inst.values[r]}" '
                f'fillcolor="gray{shade}" {color}];')

    if clusters and inst.features:
        groups: dict[int, list[int]] = {}
        for k, r in enumerate(tasks):
            groups.setdefault(feat_of.get(r, -1), []).append(k)
        for i, ks in groups.items():
            f = inst.features[i] if i >= 0 else None
            label = f"F{i + 1}{' (crítica)' if f and f.critical else ''}"
            style = 'color="#d62728"' if f and f.critical else 'color="#bbbbbb"'
            lines.append(f'subgraph cluster_{i + 1} {{ label="{label}" {style};')
            lines += [node(k) for k in ks]
            lines.append("}")
    else:
        lines += [node(k) for k in range(len(tasks))]
    for u, v in arcs:
        ru, rv = tasks[u], tasks[v]
        inter = feat_of.get(ru) != feat_of.get(rv)
        attrs = 'color="#d62728" penwidth=2.5' if (u, v) in ce else (
            'color="#999999" style=dashed' if inter else 'color="#555555"')
        lines.append(f"n{ru} -> n{rv} [{attrs}];")
    lines.append("}")
    return "\n".join(lines), cp


folder = Path(sys.argv[1] if len(sys.argv) > 1 else "instances")
folder = Path(st.sidebar.text_input("Pasta das instâncias", str(folder)))
files = sorted(folder.glob("*.nrp"))
st.title("Instâncias NRP-S")
if not files:
    st.info(f"Nenhum arquivo .nrp em {folder.resolve()}. Gere com `salbpgen nrps ... -o {folder}/x.nrp`.")
    st.stop()

rows = []
for f in files:
    inst = load(str(f), f.stat().st_mtime)
    p = inst.meta.get("params", {})
    cp = inst.meta.get("critical_path_fast")
    rows.append({
        "instância": f.stem, "tarefas": inst.n, "T": p.get("horizon"), "features": len(inst.features) or None,
        "controladas": p.get("n_critical"), "críticas (CP>T)": sum(x.critical for x in inst.features),
        "cp_ratio": p.get("cp_ratio"), "alpha": p.get("alpha"),
        "feature_os": p.get("feature_os"), "inter_share": p.get("inter_share"), "arcos": len(inst.arcs),
        "CP (rápido)": cp, "CP/T": round(cp / p["horizon"], 2) if cp and p.get("horizon") else None,
        "seed": inst.meta.get("seed"),
    })
table = pd.DataFrame(rows)
st.caption("Clique numa linha para ver o grafo.")
sel = st.dataframe(table, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row")
if not sel.selection.rows:
    st.stop()

f = files[sel.selection.rows[0]]
inst = load(str(f), f.stat().st_mtime)
p = inst.meta.get("params", {})
speedup = p.get("speedup", 1.4)
st.subheader(f.stem)
c = st.columns(5)
c[0].metric("Tarefas", inst.n)
c[1].metric("Features", len(inst.features) or "–")
c[2].metric("Arcos", len(inst.arcs))
c[3].metric("Horizonte T", inst.horizon or "–")
c[4].metric("CP (desenv. mais rápido)", inst.meta.get("critical_path_fast", "–"))

if inst.features:
    ft = pd.DataFrame([{"feature": f"F{i + 1}", "crítica": x.critical, "controlada": x.controlled, "tarefas": len(x.tasks),
                        "CP (rápido)": x.critical_path_fast,
                        "esforço (MID)": sum(inst.durations[r] for r in x.tasks),
                        "valor": sum(inst.values[r] for r in x.tasks)}
                       for i, x in enumerate(inst.features)])
    with st.expander("Features", expanded=False):
        st.dataframe(ft, hide_index=True, use_container_width=True)
    order = sorted(range(len(inst.features)), key=lambda i: (not inst.features[i].critical, i))
    options = ["Instância inteira"] + [f"F{i + 1}{' (crítica)' if inst.features[i].critical else ''} "
                                       f"– {len(inst.features[i].tasks)} tarefas" for i in order]
    choice = st.selectbox("Mostrar", options, index=1)
    if choice == "Instância inteira":
        tasks, clusters = list(range(inst.n)), True
    else:
        i = order[options.index(choice) - 1]
        tasks, clusters = inst.features[i].tasks, False
else:
    tasks, clusters = list(range(inst.n)), False

if len(tasks) > MAX_NODES and not st.checkbox(f"Desenhar {len(tasks)} nós mesmo assim (pode ficar lento)"):
    st.warning(f"O grafo tem {len(tasks)} nós. Escolha uma feature ou marque a opção acima.")
    st.stop()

src, cp = dot(inst, tasks, speedup, clusters)
msg = f"Caminho crítico do recorte: **{cp}** períodos com o desenvolvedor mais rápido"
if inst.horizon:
    msg += f" (T = {inst.horizon}, {'excede' if cp > inst.horizon else 'cabe em'} T)"
st.markdown(msg + ". Vermelho: caminho crítico. Tracejado: arco entre features. Mais escuro: mais valor.")
st.graphviz_chart(src, use_container_width=True)
