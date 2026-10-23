"""SALBP instance and the ``.alb`` file format (Scholl / Otto et al. data sets).

Example::

    <number of tasks>
    20

    <cycle time>
    1000

    <order strength>
    0,268

    <task times>
    1 142
    ...

    <precedence relations>
    1,6
    ...

    <end>
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .graph import PrecedenceGraph


@dataclass
class Instance:
    n: int
    cycle_time: int
    task_times: list[int]  # task_times[k] is the time of task k + 1
    arcs: list[tuple[int, int]]  # 1-indexed direct precedence relations
    name: str = ""
    meta: dict = field(default_factory=dict)

    def graph(self) -> PrecedenceGraph:
        return PrecedenceGraph.from_arcs(self.n, [(i - 1, j - 1) for i, j in self.arcs])

    @property
    def order_strength(self) -> float:
        return self.graph().order_strength

    # ------------------------------------------------------------------ I/O
    def to_alb(self) -> str:
        os_txt = f"{self.order_strength:.3f}".replace(".", ",")
        lines = [
            "<number of tasks>", str(self.n), "",
            "<cycle time>", str(self.cycle_time), "",
            "<order strength>", os_txt, "",
            "<task times>",
            *(f"{k + 1} {t}" for k, t in enumerate(self.task_times)), "",
            "<precedence relations>",
            *(f"{i},{j}" for i, j in sorted(self.arcs)), "",
            "<end>",
        ]
        return "\n".join(lines) + "\n"

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.to_alb())

    @classmethod
    def from_alb(cls, text: str, name: str = "") -> "Instance":
        sections: dict[str, list[str]] = {}
        current = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("<") and line.endswith(">"):
                current = line[1:-1].strip().lower()
                sections[current] = []
            elif current is not None:
                sections[current].append(line)
        n = int(sections["number of tasks"][0])
        c = int(sections["cycle time"][0]) if sections.get("cycle time") else 0
        times = [0] * n
        for line in sections.get("task times", []):
            k, t = line.split()
            times[int(k) - 1] = int(t)
        arcs = []
        for line in sections.get("precedence relations", []):
            i, j = line.replace(" ", "").split(",")
            arcs.append((int(i), int(j)))
        meta = {}
        if sections.get("order strength"):
            meta["order_strength_file"] = float(sections["order strength"][0].replace(",", "."))
        return cls(n, c, times, arcs, name=name, meta=meta)

    @classmethod
    def read(cls, path: str | Path) -> "Instance":
        path = Path(path)
        return cls.from_alb(path.read_text(), name=path.stem)
