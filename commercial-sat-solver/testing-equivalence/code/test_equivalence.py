"""Checks for the two implication tests

Run: python test_equivalence.py
"""

from __future__ import annotations

import glob
import os
import random

from equivalence import (
    Cnf,
    Verdict,
    brute_force_relationship,
    implies_incremental,
    implies_tseitin,
    read_dimacs,
    relationship,
)
from pairs import make_pairs

SOLVER = "cadical153"


def cnf(n_vars, clauses):
    return Cnf(n_vars=n_vars, clauses=[list(c) for c in clauses])


def satisfies(formula: Cnf, model) -> bool:
    val = {abs(l): (l > 0) for l in model}
    for c in formula.clauses:
        if not c:
            return False
        if not any(val.get(abs(l), False) == (l > 0) for l in c):
            return False
    return True


def test_known_small() -> None:
    """Hand-made cases with a verdict that can be checked by enumeration"""
    cases = [
        ("identical", cnf(2, [[1, 2]]), cnf(2, [[1, 2]]), Verdict.EQUIVALENT),
        ("weaker", cnf(2, [[1], [2]]), cnf(2, [[1]]), Verdict.IMPLIES),
        ("stronger", cnf(2, [[1]]), cnf(2, [[1], [2]]), Verdict.IMPLIED_BY),
        ("unrelated", cnf(2, [[1]]), cnf(2, [[2]]), Verdict.NONE),
        ("phi unsat", cnf(2, [[1], [-1]]), cnf(2, [[2]]), Verdict.IMPLIES),
        ("both unsat", cnf(2, [[1], [-1]]), cnf(2, [[2], [-2]]), Verdict.EQUIVALENT),
        ("psi empty", cnf(2, [[1]]), cnf(2, []), Verdict.IMPLIES),
        ("phi empty", cnf(2, []), cnf(2, [[1]]), Verdict.IMPLIED_BY),
        ("both empty", cnf(2, []), cnf(2, []), Verdict.EQUIVALENT),
        ("tautology in psi", cnf(2, [[1]]), cnf(2, [[1, -1], [1]]), Verdict.EQUIVALENT),
        ("resolvent added", cnf(3, [[1, 2], [-1, 3]]),
         cnf(3, [[1, 2], [-1, 3], [2, 3]]), Verdict.EQUIVALENT),
    ]

    for name, phi, psi, want in cases:
        ref = brute_force_relationship(phi, psi)
        assert ref == want, f"{name}: brute force says {ref}, case claims {want}"
        for method in ("tseitin", "incremental"):
            got = relationship(phi, psi, method, SOLVER).verdict
            assert got == want, f"{name} [{method}]: got {got}, expected {want}"
        print(f"  {name:<18} {want.value}")


def test_methods_agree_on_benchmarks() -> None:
    """The two approaches must return the same verdict on every derived pair"""
    root = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    files = sorted(glob.glob(os.path.join(root, "*", "*.cnf")))
    assert files, "no benchmark files found"

    rng = random.Random(7)
    sample = rng.sample(files, min(12, len(files)))

    checked = 0
    for path in sample:
        phi = read_dimacs(path)
        for pair in make_pairs(os.path.basename(path), phi, seed=1):
            a = relationship(pair.phi, pair.psi, "tseitin", SOLVER)
            b = relationship(pair.phi, pair.psi, "incremental", SOLVER)
            assert a.verdict == b.verdict, (
                f"{pair.name} [{pair.mutation}]: tseitin says {a.verdict}, "
                f"incremental says {b.verdict}"
            )
            checked += 1
    print(f"  {checked} pairs, both approaches agree")


def test_counterexamples_are_real() -> None:
    """A failed direction must come with a model of phi that falsifies psi"""
    root = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    files = sorted(glob.glob(os.path.join(root, "uf20-91", "*.cnf")))[:4]

    checked = 0
    for path in files:
        phi = read_dimacs(path)
        for pair in make_pairs(os.path.basename(path), phi, seed=2):
            for fn in (implies_tseitin, implies_incremental):
                ans = fn(pair.phi, pair.psi, SOLVER)
                if ans.holds:
                    continue
                assert ans.counterexample is not None, "no counterexample given"
                assert satisfies(pair.phi, ans.counterexample), \
                    f"{pair.name}: counterexample does not satisfy phi"
                assert not satisfies(pair.psi, ans.counterexample), \
                    f"{pair.name}: counterexample also satisfies psi"
                checked += 1
    print(f"  {checked} counterexamples verified against both formulas")


def test_tseitin_introduces_selectors() -> None:
    """One auxiliary variable per clause of psi, and none in the incremental run"""
    phi = cnf(3, [[1, 2], [-1, 3]])
    psi = cnf(3, [[1], [2, 3]])

    t = implies_tseitin(phi, psi, SOLVER)
    i = implies_incremental(phi, psi, SOLVER)

    assert t.aux_vars == psi.n_clauses, f"{t.aux_vars} selectors for {psi.n_clauses} clauses"
    assert i.aux_vars == 0
    assert i.calls == psi.n_clauses or not i.holds
    print(f"  tseitin adds {t.aux_vars} selectors, incremental adds {i.aux_vars}")


def test_reader() -> None:
    """The reader must agree with the p line on a real benchmark file"""
    root = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    for family, n_vars, n_clauses in [("uf20-91", 20, 91), ("uf50-218", 50, 218)]:
        path = sorted(glob.glob(os.path.join(root, family, "*.cnf")))[0]
        f = read_dimacs(path)
        assert f.n_vars == n_vars, f"{path}: {f.n_vars} vars, expected {n_vars}"
        assert f.n_clauses == n_clauses, f"{path}: {f.n_clauses} clauses, expected {n_clauses}"
        print(f"  {os.path.basename(path):<16} {f.n_vars} vars, {f.n_clauses} clauses")


if __name__ == "__main__":
    for test in [
        test_reader,
        test_known_small,
        test_tseitin_introduces_selectors,
        test_counterexamples_are_real,
        test_methods_agree_on_benchmarks,
    ]:
        print(f"{test.__name__}:")
        test()
    print("\nall tests passed")
