"""Precedence graph with an incrementally maintained transitive closure.

Nodes are 0-indexed internally. Reachability is stored as Python ints used as
bitsets, which keeps order-strength updates cheap even for n = 1000.

The graph is always kept *transitively reduced*: whenever a new arc makes an
existing arc redundant, the redundant arc is dropped, so ``arcs()`` only ever
returns direct (non-redundant) precedence relations.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def iter_bits(x: int) -> Iterator[int]:
    """Yield the indices of the set bits of ``x`` in increasing order."""
    while x:
        low = x & -x
        yield low.bit_length() - 1
        x ^= low


def nth_set_bit(x: int, k: int) -> int:
    """Index of the k-th (0-based) set bit of ``x``, by binary search on popcounts."""
    lo, hi = 0, x.bit_length()
    while lo < hi:
        mid = (lo + hi) // 2
        if (x & ((1 << (mid + 1)) - 1)).bit_count() > k:
            hi = mid
        else:
            lo = mid + 1
    return lo


class CycleError(ValueError):
    pass


class PrecedenceGraph:
    def __init__(self, n: int):
        self.n = n
        self.succ: list[set[int]] = [set() for _ in range(n)]
        self.pred: list[set[int]] = [set() for _ in range(n)]
        self.reach = [0] * n  # strict transitive successors of each node
        self.reached_by = [0] * n  # strict transitive predecessors of each node
        self.closure_size = 0  # number of comparable (ordered) pairs

    # ------------------------------------------------------------------ basics
    @classmethod
    def from_arcs(cls, n: int, arcs: Iterable[tuple[int, int]]) -> "PrecedenceGraph":
        g = cls(n)
        for i, j in arcs:
            if not g.reaches(i, j):
                g.add_arc(i, j)
        return g

    @property
    def max_pairs(self) -> int:
        return self.n * (self.n - 1) // 2

    @property
    def order_strength(self) -> float:
        return self.closure_size / self.max_pairs if self.n > 1 else 0.0

    @property
    def n_arcs(self) -> int:
        return sum(len(s) for s in self.succ)

    def arcs(self) -> list[tuple[int, int]]:
        return sorted((i, j) for i in range(self.n) for j in self.succ[i])

    def has_arc(self, i: int, j: int) -> bool:
        return j in self.succ[i]

    def reaches(self, i: int, j: int) -> bool:
        return (self.reach[i] >> j) & 1 == 1

    def comparable(self, i: int, j: int) -> bool:
        return self.reaches(i, j) or self.reaches(j, i)

    def in_degree(self, v: int) -> int:
        return len(self.pred[v])

    def out_degree(self, v: int) -> int:
        return len(self.succ[v])

    # ------------------------------------------------------- arc evaluation
    def _sets(self, i: int, j: int) -> tuple[int, int]:
        return self.reached_by[i] | (1 << i), self.reach[j] | (1 << j)

    def gain(self, i: int, j: int) -> int:
        """Number of new ordered pairs the arc (i, j) would add to the closure."""
        if i == j:
            raise CycleError("self loop")
        if self.reaches(i, j):
            return 0
        if self.reaches(j, i):
            raise CycleError(f"arc {i}->{j} closes a cycle")
        a_set, b_set = self._sets(i, j)
        reach = self.reach
        return sum((b_set & ~reach[a]).bit_count() for a in iter_bits(a_set))

    def made_redundant(self, i: int, j: int) -> list[tuple[int, int]]:
        """Existing direct arcs that become redundant once (i, j) is added."""
        a_set, b_set = self._sets(i, j)
        out = []
        for a in iter_bits(a_set):
            for b in self.succ[a]:
                if (b_set >> b) & 1:
                    out.append((a, b))
        return out

    # ---------------------------------------------------------- modification
    def add_arc(self, i: int, j: int) -> list[tuple[int, int]]:
        """Add arc (i, j); returns the arcs removed because they became redundant."""
        if self.reaches(i, j):
            raise ValueError(f"arc {i}->{j} is redundant")
        g = self.gain(i, j)  # also checks for cycles
        redundant = self.made_redundant(i, j)
        a_set, b_set = self._sets(i, j)
        for a in iter_bits(a_set):
            self.reach[a] |= b_set
        for b in iter_bits(b_set):
            self.reached_by[b] |= a_set
        self.closure_size += g
        for a, b in redundant:
            self.succ[a].discard(b)
            self.pred[b].discard(a)
        self.succ[i].add(j)
        self.pred[j].add(i)
        return redundant

    def remove_arc(self, i: int, j: int) -> None:
        self.succ[i].discard(j)
        self.pred[j].discard(i)
        self.recompute_closure()

    def topological_order(self) -> list[int]:
        indeg = [len(p) for p in self.pred]
        stack = [v for v in range(self.n) if indeg[v] == 0]
        order = []
        while stack:
            v = stack.pop()
            order.append(v)
            for w in self.succ[v]:
                indeg[w] -= 1
                if indeg[w] == 0:
                    stack.append(w)
        if len(order) != self.n:
            raise CycleError("graph contains a cycle")
        return order

    def recompute_closure(self) -> None:
        order = self.topological_order()
        self.reach = [0] * self.n
        self.reached_by = [0] * self.n
        for v in reversed(order):
            r = 0
            for w in self.succ[v]:
                r |= self.reach[w] | (1 << w)
            self.reach[v] = r
        for v in order:
            r = 0
            for u in self.pred[v]:
                r |= self.reached_by[u] | (1 << u)
            self.reached_by[v] = r
        self.closure_size = sum(r.bit_count() for r in self.reach)

    def longest_path_nodes(self) -> int:
        """Number of nodes on a longest path (= number of levels)."""
        if self.n == 0:
            return 0
        depth = [1] * self.n
        for v in self.topological_order():
            for w in self.succ[v]:
                depth[w] = max(depth[w], depth[v] + 1)
        return max(depth)
