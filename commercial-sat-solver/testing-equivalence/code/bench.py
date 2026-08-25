"""Timing harness for the equivalence experiments

Runs in process. The work per pair is milliseconds to a few seconds, so a child
process per pair would spend far more time starting an interpreter and pickling
the two formulas than solving. The incremental approach is a loop of small
calls and stops itself at the deadline; the Tseitin approach is one call and
cannot, so a size guard is offered instead.
"""

from __future__ import annotations

import glob
import os
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

from equivalence import Timeout, read_dimacs, relationship
from pairs import Pair, make_pairs

BENCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "benchmarks")
METHODS = ["tseitin", "incremental"]
BUDGET = 60.0
SOLVER = "cadical153"

HARDNESS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hardness.csv")

# Both approaches scale with the number of clauses of psi: the incremental one
# issues a call per clause, the Tseitin one introduces a selector variable per
# clause. Past this size a single pair costs more than the whole rest of the
# sweep, so larger instances are left out and reported separately.
MAX_CLAUSES = 50_000


@dataclass
class Row:
    family: str
    instance: str
    n_vars: int
    n_clauses: int
    mutation: str
    intended: str
    method: str
    solver: str
    verdict: Optional[str] = None
    calls: Optional[int] = None
    aux_vars: Optional[int] = None
    build_time: Optional[float] = None
    load_time: Optional[float] = None
    solve_time: Optional[float] = None
    total_time: Optional[float] = None
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def matched_intent(self) -> Optional[bool]:
        if self.verdict is None:
            return None
        return self.verdict == self.intended


def hard_instances() -> set:
    """Instances that probe.py could not solve within its cap

    The Tseitin approach is a single unbounded call, so an instance the solver
    cannot crack on its own makes the whole pair unmeasurable. Those instances
    are left out of the sweep and reported separately.
    """
    if not os.path.exists(HARDNESS_CSV):
        return set()
    import csv

    with open(HARDNESS_CSV, newline="") as f:
        return {r["instance"] for r in csv.DictReader(f) if r["hard"] == "True"}


def families(include_excluded: bool = False) -> List[str]:
    all_families = sorted(
        d for d in os.listdir(BENCH_DIR)
        if os.path.isdir(os.path.join(BENCH_DIR, d)) and not d.startswith("_")
    )
    if include_excluded:
        return all_families
    return [f for f in all_families if instances(f)]


def instances(family: str, include_hard: bool = False,
              max_clauses: Optional[int] = MAX_CLAUSES) -> List[str]:
    paths = sorted(glob.glob(os.path.join(BENCH_DIR, family, "*.cnf")))
    if include_hard:
        return paths

    hard = hard_instances()
    kept = []
    for p in paths:
        if os.path.basename(p) in hard:
            continue
        if max_clauses is not None and read_dimacs(p).n_clauses > max_clauses:
            continue
        kept.append(p)
    return kept


def run_pair(pair: Pair, family: str, method: str,
             solver: str = SOLVER, budget: float = BUDGET) -> Row:
    row = Row(
        family=family,
        instance=pair.name,
        n_vars=max(pair.phi.n_vars, pair.psi.n_vars),
        n_clauses=pair.phi.n_clauses,
        mutation=pair.mutation,
        intended=pair.intended.value,
        method=method,
        solver=solver,
    )

    started = time.perf_counter()
    try:
        rep = relationship(pair.phi, pair.psi, method, solver, budget)
    except Timeout as e:
        row.timed_out = True
        row.error = str(e)
        row.total_time = time.perf_counter() - started
        return row
    except Exception as e:
        row.error = f"{type(e).__name__}: {e}"
        return row

    row.verdict = rep.verdict.value
    row.calls = rep.calls
    row.aux_vars = rep.aux_vars
    row.build_time = rep.forward.build_time + rep.backward.build_time
    row.load_time = rep.forward.load_time + rep.backward.load_time
    row.solve_time = rep.solve_time
    row.total_time = rep.total_time
    return row


def sweep(selected: Optional[List[str]] = None,
          methods: Optional[List[str]] = None,
          solver: str = SOLVER,
          budget: float = BUDGET,
          max_clauses: Optional[int] = None,
          verbose: bool = True) -> List[Row]:
    """Run every mutation of every instance under both methods"""
    rows: List[Row] = []
    for family in (selected or families()):
        for path in instances(family):
            phi = read_dimacs(path)
            if max_clauses is not None and phi.n_clauses > max_clauses:
                if verbose:
                    print(f"  skip {os.path.basename(path)} "
                          f"({phi.n_clauses} clauses > {max_clauses})")
                continue
            name = os.path.basename(path)
            for pair in make_pairs(name, phi, seed=1):
                for method in (methods or METHODS):
                    r = run_pair(pair, family, method, solver, budget)
                    rows.append(r)
                    if verbose:
                        if r.timed_out:
                            print(f"  {family:<12} {name:<22} {pair.mutation:<16} "
                                  f"{method:<12} timed out at {budget:.0f}s", flush=True)
                        elif r.error:
                            print(f"  {family:<12} {name:<22} {pair.mutation:<16} "
                                  f"{method:<12} {r.error}")
                        else:
                            print(f"  {family:<12} {name:<22} {pair.mutation:<16} "
                                  f"{method:<12} {r.verdict:<16} "
                                  f"{r.calls:>6} calls {r.total_time:7.3f}s", flush=True)
    return rows


def to_records(rows: List[Row]) -> List[dict]:
    out = []
    for r in rows:
        d = asdict(r)
        d["matched_intent"] = r.matched_intent
        out.append(d)
    return out


if __name__ == "__main__":
    rs = sweep(selected=["uf20-91"], budget=30.0)
    print(f"\n{len(rs)} runs")
