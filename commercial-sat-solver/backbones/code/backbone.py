
"""Main backbone script
Uses 2 variants:

  propagate   one call per candidate, confirmed backbones are sent back
              into the formula so propagation can derive more of them
  complement  one call per pruning round, asking for a model that falsifies at
              least one remaining candidate; an unsatisfiable answer proves
              every remaining candidate is a backbone at once

Only calls to the solver's solve method are counted
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

Clause = List[int]


@dataclass
class Cnf:
    n_vars: int = 0
    clauses: List[Clause] = field(default_factory=list)

    @property
    def n_clauses(self) -> int:
        return len(self.clauses)


@dataclass
class Result:
    """Output of one backbone search

    calls: counts solver invocations (goal to minimize) 
    free: counts backbones obtained by unit propagation 
    (cost no calls)
    """

    backbone: List[int] = field(default_factory=list)
    calls: int = 0
    free: int = 0
    rounds: int = 0
    unsatisfiable: bool = False
    load_time: float = 0.0
    solve_time: float = 0.0

    @property
    def size(self) -> int:
        return len(self.backbone)

# DIMACS

def read_dimacs(path: str) -> Cnf:
    """Read a DIMACS CNF file

    SATLIB random 3-SAT files end with a "%" line followed by a "0",
    which would otherwise be read as an empty clause
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
                cnf.n_vars = int(line.split()[2])
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


# Unit propagation, no solver involved

class Propagator:
    """Unit propagation over a fixed clause set

    Every literal it derives from a set of backbones is itself a backbone,
    since the backbones are entailed by the formula and propagation only
    derives consequences
    """

    def __init__(self, cnf: Cnf) -> None:
        self.clauses = [list(c) for c in cnf.clauses]
        self.occurs: Dict[int, List[int]] = {}
        for i, c in enumerate(self.clauses):
            for lit in c:
                self.occurs.setdefault(lit, []).append(i)
        self.value: Dict[int, bool] = {}

    def _is_true(self, lit: int) -> bool:
        v = self.value.get(abs(lit))
        return v is not None and v == (lit > 0)

    def _is_false(self, lit: int) -> bool:
        v = self.value.get(abs(lit))
        return v is not None and v != (lit > 0)

    def assign(self, lits: Sequence[int]) -> Tuple[bool, List[int]]:
        """Assign the literals and propagate, returning what was derived

        The bool is False when propagation hits a conflict
        (since these cannot happen when the input literals are backbones of a satisfiable
        formula)
        """
        queue = list(lits)
        derived: List[int] = []

        while queue:
            lit = queue.pop()
            if self._is_true(lit):
                continue
            if self._is_false(lit):
                return False, derived
            self.value[abs(lit)] = lit > 0
            derived.append(lit)

            for idx in self.occurs.get(-lit, ()):
                clause = self.clauses[idx]
                unassigned = None
                satisfied = False
                count = 0
                for other in clause:
                    if self._is_true(other):
                        satisfied = True
                        break
                    if not self._is_false(other):
                        count += 1
                        unassigned = other
                        if count > 1:
                            break
                if satisfied or count > 1:
                    continue
                if count == 0:
                    return False, derived
                queue.append(unassigned)

        return True, derived

    def units(self) -> List[int]:
        return [c[0] for c in self.clauses if len(c) == 1]


# Helpers

def _candidates_from_model(model: Sequence[int], n_vars: int) -> Set[int]:
    """Only the polarity a model satisfies can still be a backbone

    If a model sets x true then it witnesses that not x has a model, x (and not x) are not a backbone
    One model therefore rules out half of the literals
    """
    return {l for l in model if abs(l) <= n_vars}


def _order(cands: Set[int], cnf: Cnf, how: str) -> List[int]:
    if how == "frequency":
        freq: Dict[int, int] = {}
        for c in cnf.clauses:
            for lit in c:
                freq[abs(lit)] = freq.get(abs(lit), 0) + 1
        return sorted(cands, key=lambda l: (-freq.get(abs(l), 0), abs(l)))
    return sorted(cands, key=abs)


def _all_literals(n_vars: int) -> List[int]:
    return [s * v for v in range(1, n_vars + 1) for s in (1, -1)]


# Algorithm 1: one call per candidate

def backbones_propagate(cnf: Cnf, solver_name: str = "cadical153",
                        order: str = "index") -> Result:
    from pysat.solvers import Solver

    r = Result()
    t0 = time.perf_counter()
    solver = Solver(name=solver_name, bootstrap_with=cnf.clauses)
    r.load_time = time.perf_counter() - t0

    try:
        t0 = time.perf_counter()
        sat = solver.solve()
        r.solve_time += time.perf_counter() - t0
        r.calls += 1

        if not sat:
            r.unsatisfiable = True
            r.backbone = _all_literals(cnf.n_vars)
            return r

        cands = _candidates_from_model(solver.get_model(), cnf.n_vars)

        prop = Propagator(cnf)
        ok, derived = prop.assign(prop.units())
        found: Set[int] = set(derived)
        r.free += len(derived)
        cands -= found
        cands -= {-l for l in found}

        for lit in _order(cands, cnf, order):
            if lit in found or -lit in found:
                continue
            # a model seen since the order was fixed may have dropped this one
            if lit not in cands:
                continue

            t0 = time.perf_counter()
            sat = solver.solve(assumptions=[-lit])
            r.solve_time += time.perf_counter() - t0
            r.calls += 1
            r.rounds += 1

            if sat:
                # the model rules out every candidate it falsifies
                model = _candidates_from_model(solver.get_model(), cnf.n_vars)
                cands &= model
                continue

            # phi and not lit is unsatisfiable, so lit is a backbone
            found.add(lit)
            solver.add_clause([lit])
            ok, derived = prop.assign([lit])
            for d in derived:
                if d != lit:
                    found.add(d)
                    r.free += 1

        r.backbone = sorted(found, key=abs)
        return r
    finally:
        solver.delete()


# Algorithm 2: one call per pruning round

def backbones_complement(cnf: Cnf, solver_name: str = "cadical153",
                         order: str = "index") -> Result:
    from pysat.solvers import Solver

    r = Result()
    t0 = time.perf_counter()
    solver = Solver(name=solver_name, bootstrap_with=cnf.clauses)
    r.load_time = time.perf_counter() - t0

    try:
        t0 = time.perf_counter()
        sat = solver.solve()
        r.solve_time += time.perf_counter() - t0
        r.calls += 1

        if not sat:
            r.unsatisfiable = True
            r.backbone = _all_literals(cnf.n_vars)
            return r

        cands = _candidates_from_model(solver.get_model(), cnf.n_vars)

        prop = Propagator(cnf)
        ok, derived = prop.assign(prop.units())
        found: Set[int] = set(derived)
        r.free += len(derived)
        cands -= found
        cands -= {-l for l in found}

        selector = cnf.n_vars
        while cands:
            # (not s) or (at least one candidate is false), activated by
            # assuming s, and dropped afterwards by asserting not s
            selector += 1
            solver.add_clause([-selector] + [-l for l in cands])

            t0 = time.perf_counter()
            sat = solver.solve(assumptions=[selector])
            r.solve_time += time.perf_counter() - t0
            r.calls += 1
            r.rounds += 1

            if not sat:
                # no model falsifies any candidate, so all of them are backbones
                solver.add_clause([-selector])
                found |= cands
                cands = set()
                break

            model = _candidates_from_model(solver.get_model(), cnf.n_vars)
            solver.add_clause([-selector])
            cands &= model

        r.backbone = sorted(found, key=abs)
        return r
    finally:
        solver.delete()


ALGORITHMS = {
    "propagate": backbones_propagate,
    "complement": backbones_complement,
}


def backbones(cnf: Cnf, algorithm: str = "complement",
              solver_name: str = "cadical153", order: str = "index") -> Result:
    return ALGORITHMS[algorithm](cnf, solver_name, order)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python backbone.py <file.cnf> [propagate|complement] [solver]")
        raise SystemExit(2)

    algo = sys.argv[2] if len(sys.argv) > 2 else "complement"
    solver = sys.argv[3] if len(sys.argv) > 3 else "cadical153"

    f = read_dimacs(sys.argv[1])
    res = backbones(f, algo, solver)

    if res.unsatisfiable:
        print("c formula is unsatisfiable, every literal is vacuously a backbone")
    print(" ".join(str(l) for l in res.backbone))
    print(f"c {res.size} backbones, {res.calls} solver calls, "
          f"{res.free} obtained by propagation")
