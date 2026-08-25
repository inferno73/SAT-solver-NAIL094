"""Timing helper for the cryptarithm experiments

Encoding (my Python implementation) and solving (commercial solver) are timed apart
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import List, Optional

import formula as F
from cryptarithm import solve_formula
from instances import Puzzle, load_all

SOLVER = "cadical153"


@dataclass
class Row:
    source: str
    puzzle: str
    n_terms: int
    n_letters: int
    longest_word: int
    base: int
    distinct: bool
    mode: str
    solver: str = SOLVER
    n_vars: Optional[int] = None
    n_clauses: Optional[int] = None
    solutions: Optional[int] = None
    calls: Optional[int] = None
    unique: Optional[bool] = None
    matches_published: Optional[bool] = None
    encode_time: Optional[float] = None
    solve_time: Optional[float] = None
    error: Optional[str] = None

    @property
    def total_time(self) -> Optional[float]:
        if self.encode_time is None or self.solve_time is None:
            return None
        return self.encode_time + self.solve_time


def run_puzzle(p: Puzzle, base: int = 10, distinct: bool = True,
               mode: str = "all", solver: str = SOLVER) -> Row:
    """mode is first for one solution, unique for at most two, all for all solutions"""
    limit = {"first": 1, "unique": 2, "all": None}[mode]

    row = Row(source=p.source, puzzle=p.text, n_terms=p.n_terms,
              n_letters=len(p.letters), longest_word=max(len(w) for w in p.words),
              base=base, distinct=distinct, mode=mode, solver=solver)

    try:
        r = solve_formula(F.parse(p.text), base, distinct, limit=limit,
                          solver_name=solver)
    except Exception as e:
        row.error = f"{type(e).__name__}: {e}"
        return row

    row.n_vars, row.n_clauses = r.n_vars, r.n_clauses
    row.solutions = r.count
    row.calls = r.calls
    row.encode_time = r.encode_time
    row.solve_time = r.solve_time

    if mode == "all":
        row.unique = r.count == 1
    elif mode == "unique":
        row.unique = (r.count == 1) if r.count else None

    if p.expected:
        row.matches_published = any(s.assignment == p.expected for s in r.solutions)
    return row


def sweep(puzzles: Optional[List[Puzzle]] = None, base: int = 10,
          distinct: bool = True, mode: str = "all", solver: str = SOLVER,
          verbose: bool = False) -> List[Row]:
    rows = []
    for p in (puzzles if puzzles is not None else load_all()):
        r = run_puzzle(p, base, distinct, mode, solver)
        rows.append(r)
        if verbose:
            print(f"  {r.source:<10} {r.puzzle:<34} {str(r.solutions):>4} sol "
                  f"{r.total_time:7.3f}s", flush=True)
    return rows


def to_records(rows: List[Row]) -> List[dict]:
    out = []
    for r in rows:
        d = asdict(r)
        d["total_time"] = r.total_time
        out.append(d)
    return out


if __name__ == "__main__":
    t0 = time.perf_counter()
    rows = sweep(load_all()[:50], verbose=True)
    print(f"\n{len(rows)} puzzles in {time.perf_counter()-t0:.1f}s")
