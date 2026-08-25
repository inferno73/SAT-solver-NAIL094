"""Independent checking of a backbone set

Kept apart from backbone.py on purpose. Everything here creates its own solver
instances and its own counters, so no call made while verifying can ever reach
the measured results. Nothing in this module is used by the algorithms.

The check is worth making even though the algorithms are sound on paper,
because both of them are self reinforcing. The first commits confirmed
backbones into the formula, so a literal wrongly accepted early makes every
later answer agree with the mistake. The second concludes that a whole set of
candidates are backbones from a single unsatisfiable answer, so an error in
the blocking clause produces a confident wrong result. Neither failure shows
up as an inconsistency the program could notice on its own.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from backbone import Cnf


def is_backbone(cnf: Cnf, lit: int, solver_name: str = "cadical153") -> bool:
    """lit is a backbone exactly when phi and not lit has no model"""
    from pysat.solvers import Solver

    with Solver(name=solver_name, bootstrap_with=cnf.clauses) as s:
        return not s.solve(assumptions=[-lit])


def satisfies(cnf: Cnf, model: Sequence[int]) -> bool:
    val = {abs(l): (l > 0) for l in model}
    return all(any(val.get(abs(l), False) == (l > 0) for l in c) for c in cnf.clauses)


def check(cnf: Cnf, reported: Sequence[int],
          solver_name: str = "cadical153") -> Tuple[bool, List[str]]:
    """Test every literal of the formula against the reported set

    Costs 2n solver calls and is only meant for small instances. Returns
    whether the reported set is exactly right, together with the differences.
    """
    problems: List[str] = []
    reported_set = set(reported)

    for v in range(1, cnf.n_vars + 1):
        for lit in (v, -v):
            truth = is_backbone(cnf, lit, solver_name)
            claimed = lit in reported_set
            if truth and not claimed:
                problems.append(f"missed backbone {lit}")
            elif claimed and not truth:
                problems.append(f"wrongly reported {lit}")

    return not problems, problems


def check_reported_only(cnf: Cnf, reported: Sequence[int],
                        solver_name: str = "cadical153") -> Tuple[bool, List[str]]:
    """Cheaper check that only confirms the reported literals really are backbones

    This catches a set that is too large but not one that is too small, so it
    is a partial check. Costs one call per reported literal.
    """
    problems = [f"wrongly reported {l}" for l in reported
                if not is_backbone(cnf, l, solver_name)]
    return not problems, problems


def true_backbone(cnf: Cnf, solver_name: str = "cadical153") -> Tuple[List[int], int]:
    """Compute the backbone from scratch by testing every literal

    One solver is loaded and each of the 2n literals is tested with an
    assumption, which is the same decision procedure as the naive algorithm but
    with none of the shortcuts. Returns the set and the number of calls made,
    where the count is for reporting the cost of checking and is deliberately
    kept apart from the measured results
    """
    from pysat.solvers import Solver

    found: List[int] = []
    calls = 0

    with Solver(name=solver_name, bootstrap_with=cnf.clauses) as s:
        if not s.solve():
            calls += 1
            return [l for v in range(1, cnf.n_vars + 1) for l in (v, -v)], calls
        calls += 1

        for v in range(1, cnf.n_vars + 1):
            for lit in (v, -v):
                calls += 1
                if not s.solve(assumptions=[-lit]):
                    found.append(lit)

    return sorted(found, key=abs), calls


def compare(cnf: Cnf, reported: Sequence[int],
            solver_name: str = "cadical153") -> dict:
    """Full comparison of a reported set against the recomputed backbone"""
    truth, calls = true_backbone(cnf, solver_name)
    t, r = set(truth), set(reported)
    return {
        "true_size": len(t),
        "reported_size": len(r),
        "missing": sorted(t - r, key=abs),
        "extra": sorted(r - t, key=abs),
        "identical": t == r,
        "check_calls": calls,
    }


def cbs_expected_size(filename: str) -> Optional[int]:
    """Backbone size stated in a CBS benchmark name, for example b30 gives 30

    The Controlled Backbone Size family fixes the number of backbone
    variables, which gives ground truth without any solving at all.
    """
    import re

    # the size may end the name, as in CBS_k3_n100_m403_b10, or be followed by
    # the instance number, as in CBS_k3_n100_m403_b10_1.cnf
    m = re.search(r"_b(\d+)(?:_|\.|$)", filename)
    return int(m.group(1)) if m else None
