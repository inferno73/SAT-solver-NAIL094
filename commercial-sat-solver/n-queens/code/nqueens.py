"""N-Queens SAT encoding

x[r][c] is true iff a queen stands on row r, column c (both 0-based)
DIMACS variables are 1-based: var(r, c) = r * n + c + 1

Constraints: at most one (AMO) per row, at least one (ALO) per column,
at most one per diagonal (both directions)

AMO is pairwise
"""

from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Iterator, List, Sequence

Clause = List[int]
CNF = List[Clause]


@dataclass
class Encoding:
    n: int              # board size
    clauses: CNF        # list of clauses to go itno CNF
    n_vars: int         # number of variables; n*n

    @property
    def n_clauses(self) -> int:
        return len(self.clauses)


def var(r: int, c: int, n: int) -> int:
    return r * n + c + 1


# Cardinality

def at_least_one(lits: Sequence[int]) -> CNF:
    return [list(lits)]


def at_most_one(lits: Sequence[int]) -> CNF:
    # combinations used to yield all unordered pairs; j<k
    return [[-a, -b] for a, b in combinations(lits, 2)]


# Literal groups

def rows(n: int) -> Iterator[List[int]]:
    for r in range(n):
        yield [var(r, c, n) for c in range(n)]


def columns(n: int) -> Iterator[List[int]]:
    for c in range(n):
        yield [var(r, c, n) for r in range(n)]


def diagonals(n: int) -> Iterator[List[int]]:
    # "\" direction: cells with equal r - c
    for d in range(-(n - 1), n):
        group = [var(r, r - d, n) for r in range(max(0, d), min(n, n + d))]
        if len(group) > 1:
            yield group

    # "/" direction: cells with equal r + c
    for s in range(2 * n - 1):
        group = [var(r, s - r, n) for r in range(max(0, s - n + 1), min(n, s + 1))]
        if len(group) > 1:
            yield group


# Encoding

def encode(n: int) -> Encoding:
    clauses: CNF = []

    for group in rows(n):
        clauses.extend(at_most_one(group))
    for group in columns(n):
        clauses.extend(at_least_one(group))
    for group in diagonals(n):
        clauses.extend(at_most_one(group))

    return Encoding(n=n, clauses=clauses, n_vars=n * n)


def clause_count(n: int) -> int:
    """Number of clauses encode(n) would produce, without building them"""
    pairs = lambda g: len(g) * (len(g) - 1) // 2
    return (
        sum(pairs(g) for g in rows(n))
        + sum(1 for _ in columns(n))
        + sum(pairs(g) for g in diagonals(n))
    )


# Decoding

def decode(model: Sequence[int], n: int) -> List[int]:
    """Return pos[r] = column of the queen in row r, or -1 if the row is empty"""
    true_vars = {lit for lit in model if lit > 0}
    pos = [-1] * n
    for r in range(n):
        for c in range(n):
            if var(r, c, n) in true_vars:
                pos[r] = c
                break
    return pos


def verify(positions: Sequence[int], n: int) -> bool:
    if len(positions) != n or any(not 0 <= c < n for c in positions):
        return False
    if len(set(positions)) != n:
        return False
    return all(
        abs(r1 - r2) != abs(positions[r1] - positions[r2])
        for r1, r2 in combinations(range(n), 2)
    )


def to_dimacs(enc: Encoding) -> str:
    lines = [f"p cnf {enc.n_vars} {enc.n_clauses}"]
    lines.extend(" ".join(map(str, clause)) + " 0" for clause in enc.clauses)
    return "\n".join(lines) + "\n"


def render(positions: Sequence[int], n: int) -> str:
    return "\n".join(
        " ".join("Q" if c == positions[r] else "." for c in range(n))
        for r in range(n)
    )
