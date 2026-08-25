"""Testing equivalence of two CNF formulas

phi implies psi iff phi and not psi is unsatisfiable. Running that test in both
directions gives one of four verdicts. Two ways of running it are implemented:

  tseitin      one call on phi and not psi, encoded with a selector per clause
  incremental  one call per clause of psi, the negated clause given as assumptions
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

Clause = List[int]


class Timeout(Exception):
    """Raised when a run exceeds the budget it was given"""


class Verdict(str, Enum):
    EQUIVALENT = "phi <=> psi"
    IMPLIES = "phi => psi"
    IMPLIED_BY = "phi <= psi"
    NONE = "no relationship"


@dataclass
class Cnf:
    n_vars: int = 0
    clauses: List[Clause] = field(default_factory=list)

    @property
    def n_clauses(self) -> int:
        return len(self.clauses)


@dataclass
class Answer:
    """One directional test, phi => psi

    The three times cover the whole run with no gap between them: build is the
    Python work of assembling the clause list, load is the solver ingesting it,
    solve is the search itself summed over all calls.
    """

    holds: bool
    calls: int
    counterexample: Optional[List[int]] = None
    aux_vars: int = 0
    n_clauses_sent: int = 0
    build_time: float = 0.0
    load_time: float = 0.0
    solve_time: float = 0.0

    @property
    def total_time(self) -> float:
        return self.build_time + self.load_time + self.solve_time


@dataclass
class Report:
    verdict: Verdict
    forward: Answer
    backward: Answer

    @property
    def calls(self) -> int:
        return self.forward.calls + self.backward.calls

    @property
    def total_time(self) -> float:
        return self.forward.total_time + self.backward.total_time

    @property
    def solve_time(self) -> float:
        return self.forward.solve_time + self.backward.solve_time

    @property
    def aux_vars(self) -> int:
        return self.forward.aux_vars + self.backward.aux_vars


# DIMACS

def read_dimacs(path: str) -> Cnf:
    """Read a DIMACS CNF file, tolerating clauses split over several lines

    SATLIB random 3-SAT files end with a "%" line followed by a stray "0".
    Reading that 0 would append an empty clause and make the formula
    unsatisfiable, so parsing stops at the marker.
    """
    cnf = Cnf()
    current: Clause = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] == "c":
                continue
            if line[0] == "%":
                break
            if line[0] == "p":
                parts = line.split()
                cnf.n_vars = int(parts[2])
                continue
            for token in line.split():
                value = int(token)
                if value == 0:
                    cnf.clauses.append(current)
                    current = []
                else:
                    current.append(value)
                    cnf.n_vars = max(cnf.n_vars, abs(value))

    if current:
        cnf.clauses.append(current)
    return cnf


def is_tautology(clause: Sequence[int]) -> bool:
    seen = set(clause)
    return any(-l in seen for l in clause)


# Approach 1: Tseitin encoding, a single call

def implies_tseitin(phi: Cnf, psi: Cnf, solver_name: str) -> Answer:
    """Test phi => psi by one call on phi and not psi

    not psi is a disjunction of negated clauses. A selector s_i per clause of
    psi carries "this disjunct holds", giving s_i -> not C_i together with a
    clause forcing at least one selector. Only the left to right implication is
    needed, since the encoding has to preserve satisfiability and nothing more.
    """
    from pysat.solvers import Solver

    t0 = time.perf_counter()
    top = max(phi.n_vars, psi.n_vars)
    shared = top
    clauses = [list(c) for c in phi.clauses]
    selectors = []

    for clause in psi.clauses:
        top += 1
        s = top
        selectors.append(s)
        for lit in clause:
            clauses.append([-s, -lit])

    # an empty psi means not psi is false, so phi => psi holds vacuously
    if not selectors:
        return Answer(holds=True, calls=0, aux_vars=0, n_clauses_sent=0,
                      build_time=time.perf_counter() - t0)

    clauses.append(selectors)
    build_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    s = Solver(name=solver_name, bootstrap_with=clauses)
    load_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    sat = s.solve()
    solve_time = time.perf_counter() - t0

    model = s.get_model() if sat else None
    s.delete()

    return Answer(
        holds=not sat,
        calls=1,
        counterexample=_project(model, shared) if model else None,
        aux_vars=len(selectors),
        n_clauses_sent=len(clauses),
        build_time=build_time,
        load_time=load_time,
        solve_time=solve_time,
    )


# Approach 2: incremental, one call per clause of psi

def implies_incremental(phi: Cnf, psi: Cnf, solver_name: str,
                        deadline: Optional[float] = None) -> Answer:
    """Test phi => psi by one call per clause of psi

    phi is loaded once. For a clause C the query is phi and not C, and not C is
    a conjunction of unit literals, so it goes in as assumptions and no new
    variables are needed. The first satisfiable query is a counterexample and
    ends the test.

    deadline is an absolute perf_counter value. Being a loop of small calls,
    this approach can give up between them, which the single call of the
    Tseitin approach cannot do.
    """
    from pysat.solvers import Solver

    top = max(phi.n_vars, psi.n_vars)
    calls = 0
    solve_time = 0.0

    t0 = time.perf_counter()
    s = Solver(name=solver_name, bootstrap_with=phi.clauses)
    load_time = time.perf_counter() - t0

    try:
        for clause in psi.clauses:
            if deadline is not None and time.perf_counter() > deadline:
                raise Timeout(f"gave up after {calls} of {psi.n_clauses} clauses")
            calls += 1
            t0 = time.perf_counter()
            sat = s.solve(assumptions=[-l for l in clause])
            solve_time += time.perf_counter() - t0
            if sat:
                # the first satisfiable query is a counterexample, stop here
                return Answer(
                    holds=False,
                    calls=calls,
                    counterexample=_project(s.get_model(), top),
                    aux_vars=0,
                    n_clauses_sent=phi.n_clauses,
                    load_time=load_time,
                    solve_time=solve_time,
                )

        return Answer(holds=True, calls=calls, aux_vars=0,
                      n_clauses_sent=phi.n_clauses,
                      load_time=load_time, solve_time=solve_time)
    finally:
        s.delete()


def _project(model: Optional[Sequence[int]], n_vars: int) -> Optional[List[int]]:
    """Drop auxiliary variables, keep the shared variable range"""
    if model is None:
        return None
    return [l for l in model if abs(l) <= n_vars]


# Verdict

METHODS = {
    "tseitin": implies_tseitin,
    "incremental": implies_incremental,
}


def relationship(phi: Cnf, psi: Cnf, method: str = "incremental",
                 solver_name: str = "cadical153",
                 budget: Optional[float] = None) -> Report:
    """Decide which of the four relationships holds between phi and psi"""
    implies = METHODS[method]
    deadline = None if budget is None else time.perf_counter() + budget

    if method == "incremental":
        forward = implies(phi, psi, solver_name, deadline)
        backward = implies(psi, phi, solver_name, deadline)
    else:
        forward = implies(phi, psi, solver_name)
        backward = implies(psi, phi, solver_name)

    if forward.holds and backward.holds:
        verdict = Verdict.EQUIVALENT
    elif forward.holds:
        verdict = Verdict.IMPLIES
    elif backward.holds:
        verdict = Verdict.IMPLIED_BY
    else:
        verdict = Verdict.NONE

    return Report(verdict=verdict, forward=forward, backward=backward)


# Reference check, used by the tests

def brute_force_relationship(phi: Cnf, psi: Cnf) -> Verdict:
    """Enumerate all assignments, only usable for very small formulas"""
    from itertools import product

    n = max(phi.n_vars, psi.n_vars)
    fwd = True
    bwd = True

    for bits in product([False, True], repeat=n):
        val = {i + 1: bits[i] for i in range(n)}
        a = _holds(phi, val)
        b = _holds(psi, val)
        if a and not b:
            fwd = False
        if b and not a:
            bwd = False
        if not fwd and not bwd:
            break

    if fwd and bwd:
        return Verdict.EQUIVALENT
    if fwd:
        return Verdict.IMPLIES
    if bwd:
        return Verdict.IMPLIED_BY
    return Verdict.NONE


def _holds(cnf: Cnf, val: Dict[int, bool]) -> bool:
    return all(any(val[abs(l)] == (l > 0) for l in c) for c in cnf.clauses)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("usage: python equivalence.py <phi.cnf> <psi.cnf> "
              "[tseitin|incremental] [solver]")
        raise SystemExit(2)

    method = sys.argv[3] if len(sys.argv) > 3 else "incremental"
    solver = sys.argv[4] if len(sys.argv) > 4 else "cadical153"

    phi = read_dimacs(sys.argv[1])
    psi = read_dimacs(sys.argv[2])
    rep = relationship(phi, psi, method, solver)

    print(rep.verdict.value)
    print(f"c method {method}, solver {solver}, {rep.calls} solver calls")
