"""Build pairs of formulas that exercise all four relationships

Two unrelated benchmark files are almost always unrelated, which makes a dull
experiment, so psi is derived from phi by a small mutation. Each mutation has an
intended verdict, but only the measurement decides: dropping a clause that the
rest of the formula already implies leaves the two formulas equivalent, for
instance. The experiments record the intended and the measured verdict side by
side.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from equivalence import Clause, Cnf, Verdict, is_tautology


@dataclass
class Pair:
    name: str
    mutation: str
    intended: Verdict
    phi: Cnf
    psi: Cnf
    note: str = ""


def _copy(cnf: Cnf) -> Cnf:
    return Cnf(n_vars=cnf.n_vars, clauses=[list(c) for c in cnf.clauses])


# Mutations

def identical(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    return _copy(phi)


def shuffled(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    """Same clauses, different order, literals permuted inside each clause"""
    psi = _copy(phi)
    for c in psi.clauses:
        rng.shuffle(c)
    rng.shuffle(psi.clauses)
    return psi


def with_resolvent(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    """Add a resolvent of two clauses of phi

    A resolvent is implied by phi, so the model set does not change and the two
    formulas stay equivalent even though psi is syntactically larger.
    """
    index = list(range(phi.n_clauses))
    rng.shuffle(index)

    for i in index[:200]:
        for j in index[:200]:
            if i == j:
                continue
            a, b = phi.clauses[i], phi.clauses[j]
            pivots = [l for l in a if -l in b]
            if len(pivots) != 1:
                continue
            p = pivots[0]
            resolvent = sorted({l for l in a if l != p} | {l for l in b if l != -p})
            if not resolvent or is_tautology(resolvent):
                continue
            if resolvent in phi.clauses:
                continue
            psi = _copy(phi)
            psi.clauses.append(resolvent)
            return psi
    return None


def dropped_clause(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    """Remove one clause, which weakens the formula"""
    if phi.n_clauses < 2:
        return None
    psi = _copy(phi)
    psi.clauses.pop(rng.randrange(len(psi.clauses)))
    return psi


def added_clause(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    """Add a random clause, which strengthens the formula"""
    if phi.n_vars < 3:
        return None
    psi = _copy(phi)
    for _ in range(50):
        vars_ = rng.sample(range(1, phi.n_vars + 1), 3)
        clause = sorted(v if rng.random() < 0.5 else -v for v in vars_)
        if clause not in psi.clauses and not is_tautology(clause):
            psi.clauses.append(clause)
            return psi
    return None


def flipped_literal(phi: Cnf, rng: random.Random) -> Optional[Cnf]:
    """Negate one literal of one clause, which usually breaks both directions"""
    if phi.n_clauses == 0:
        return None
    psi = _copy(phi)
    for _ in range(50):
        ci = rng.randrange(len(psi.clauses))
        if not psi.clauses[ci]:
            continue
        li = rng.randrange(len(psi.clauses[ci]))
        clause = list(psi.clauses[ci])
        clause[li] = -clause[li]
        if is_tautology(clause):
            continue
        psi.clauses[ci] = clause
        return psi
    return None


MUTATIONS = [
    ("identical", identical, Verdict.EQUIVALENT,
     "psi is a copy of phi"),
    ("shuffled", shuffled, Verdict.EQUIVALENT,
     "clause and literal order permuted"),
    ("resolvent added", with_resolvent, Verdict.EQUIVALENT,
     "an implied clause added, psi is larger but says the same"),
    ("clause dropped", dropped_clause, Verdict.IMPLIES,
     "psi has one clause fewer, so it is weaker"),
    ("clause added", added_clause, Verdict.IMPLIED_BY,
     "psi has one random clause more, so it is stronger"),
    ("literal flipped", flipped_literal, Verdict.NONE,
     "one literal negated, usually unrelated"),
]


def make_pairs(name: str, phi: Cnf, seed: int = 0) -> List[Pair]:
    """All mutations of one benchmark instance"""
    rng = random.Random(seed)
    out = []
    for label, fn, intended, note in MUTATIONS:
        psi = fn(phi, rng)
        if psi is None:
            continue
        out.append(Pair(name=name, mutation=label, intended=intended,
                        phi=phi, psi=psi, note=note))
    return out
