"""Checks for the backbone algorithms
Used as separate check (not present in measurement counts)
"""

from __future__ import annotations

import glob
import os
from typing import List

from backbone import ALGORITHMS, Cnf, Propagator, backbones, read_dimacs
from verify import (
    cbs_expected_size,
    check,
    check_reported_only,
    is_backbone,
    satisfies,
)

SOLVER = "cadical153"
ALLSAT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "..", "benchmarks_allSAT")


def cnf(n, cs):
    return Cnf(n_vars=n, clauses=[list(c) for c in cs])


def test_small_known() -> None:
    """Formulas whose backbones can be written down by hand"""
    cases = [
        ("unit clause", cnf(2, [[1], [1, 2]]), {1}),
        ("two units", cnf(3, [[1], [-2], [1, 3]]), {1, -2}),
        ("forced by propagation", cnf(2, [[1], [-1, 2]]), {1, 2}),
        ("free variable", cnf(2, [[1, 2], [-1, -2]]), set()),
        ("implied literal", cnf(3, [[1, 2], [-1, 2]]), {2}),
        ("no clauses", cnf(2, []), set()),
        ("all fixed", cnf(2, [[1], [2]]), {1, 2}),
    ]

    for name, formula, want in cases:
        for algo in ALGORITHMS:
            got = set(backbones(formula, algo, SOLVER).backbone)
            assert got == want, f"{name} [{algo}]: got {got}, expected {want}"
        print(f"  {name:<22} {sorted(want) if want else 'none'}")


def test_unsatisfiable() -> None:
    """An unsatisfiable formula entails every literal vacuously"""
    formula = cnf(2, [[1], [-1]])
    for algo in ALGORITHMS:
        r = backbones(formula, algo, SOLVER)
        assert r.unsatisfiable, f"{algo}: did not report unsatisfiable"
        assert len(r.backbone) == 4, f"{algo}: {len(r.backbone)} literals, expected 4"
    print("  unsatisfiable formula reported, all 4 literals returned")


def test_algorithms_agree() -> None:
    """Both algorithms compute the same set on every instance tried"""
    paths = []
    for fam in ["uf20-91", "flat30-60", "CBS_k3_n100_m403_b10", "CBS_k3_n100_m403_b90"]:
        paths += sorted(glob.glob(os.path.join(ALLSAT, fam, "*.cnf")))[:3]

    for p in paths:
        f = read_dimacs(p)
        sets = {a: set(backbones(f, a, SOLVER).backbone) for a in ALGORITHMS}
        first = next(iter(sets.values()))
        for a, s in sets.items():
            assert s == first, (f"{os.path.basename(p)}: {a} gives {len(s)} literals, "
                                f"another gives {len(first)}")
    print(f"  {len(paths)} instances, both algorithms agree")


def test_exhaustive_small() -> None:
    """Every literal checked one by one, only on instances small enough"""
    paths = sorted(glob.glob(os.path.join(ALLSAT, "uf20-91", "*.cnf")))[:3]
    paths += sorted(glob.glob(os.path.join(ALLSAT, "flat30-60", "*.cnf")))[:2]

    for p in paths:
        f = read_dimacs(p)
        for algo in ALGORITHMS:
            r = backbones(f, algo, SOLVER)
            ok, problems = check(f, r.backbone, SOLVER)
            assert ok, f"{os.path.basename(p)} [{algo}]: {problems[:5]}"
        print(f"  {os.path.basename(p):<18} {f.n_vars:3d} vars, "
              f"{len(r.backbone):3d} backbones, all {2*f.n_vars} literals verified")


def test_cbs_ground_truth() -> None:
    """CBS instances state their backbone size in the file name"""
    for b in [10, 30, 50, 70, 90]:
        fam = f"CBS_k3_n100_m403_b{b}"
        paths = sorted(glob.glob(os.path.join(ALLSAT, fam, "*.cnf")))[:5]
        assert paths, f"no instances for {fam}"
        for p in paths:
            want = cbs_expected_size(os.path.basename(p) or fam)
            if want is None:
                want = b
            f = read_dimacs(p)
            for algo in ALGORITHMS:
                r = backbones(f, algo, SOLVER)
                assert r.size == want, (f"{os.path.basename(p)} [{algo}]: "
                                        f"{r.size} backbones, family says {want}")
        print(f"  {fam:<24} {len(paths)} instances, all report {b} backbones")


def test_cbs_set_is_exact() -> None:
    """The reported literals are the true backbone, not just the right count

    CBS fixes the number of backbone literals at b. If the program reports b
    literals and each of them is confirmed a backbone, then the reported set
    is a b element subset of a b element set, so the two coincide
    """
    for b in [10, 30, 50, 70, 90]:
        fam = f"CBS_k3_n100_m403_b{b}"
        paths = sorted(glob.glob(os.path.join(ALLSAT, fam, "*.cnf")))[:3]
        for p in paths:
            f = read_dimacs(p)
            for algo in ALGORITHMS:
                r = backbones(f, algo, SOLVER)
                assert r.size == b, f"{os.path.basename(p)} [{algo}]: {r.size} of {b}"
                ok, problems = check_reported_only(f, r.backbone, SOLVER)
                assert ok, f"{os.path.basename(p)} [{algo}]: {problems[:3]}"
        print(f"  {fam:<24} {len(paths)} instances, all {b} literals confirmed genuine")


def test_algorithms_agree_as_sets() -> None:
    """Agreement is on the literals, not merely on how many there are"""
    paths = []
    for fam in ["uf50-218", "uf100-430", "blocksworld", "ais", "logistics"]:
        paths += sorted(glob.glob(os.path.join(ALLSAT, fam, "*.cnf")))[:2]

    for p in paths:
        f = read_dimacs(p)
        a = set(backbones(f, "propagate", SOLVER).backbone)
        b = set(backbones(f, "complement", SOLVER).backbone)
        assert a == b, (f"{os.path.basename(p)}: sets differ, "
                        f"{len(a - b)} only in propagate, {len(b - a)} only in complement")
    print(f"  {len(paths)} instances, identical literal sets")


def test_propagation_is_sound() -> None:
    """Literals derived by unit propagation from the units really are backbones

    None of the benchmark files carries a unit clause, so propagating from the
    units alone derives nothing there and would check nothing. The formulas
    below carry units on purpose, and the benchmark case is covered by
    propagating from a committed literal instead
    """
    # x1, then x2 by the second clause, then x3 by the third
    built = [
        (cnf(3, [[1], [-1, 2], [-2, 3], [1, 2, 3]]), {1, 2, 3}),
        (cnf(4, [[1], [-1, -2], [2, 3], [-3, 4]]), {1, -2, 3, 4}),
    ]
    for f, want in built:
        prop = Propagator(f)
        ok, derived = prop.assign(prop.units())
        assert ok, "propagation hit a conflict"
        assert set(derived) == want, f"derived {sorted(derived)}, expected {sorted(want)}"
        for lit in derived:
            assert is_backbone(f, lit, SOLVER), f"propagated {lit} is not a backbone"
        print(f"  built formula      {len(derived)} propagated literals, "
              f"all confirmed backbones")

    paths = sorted(glob.glob(os.path.join(ALLSAT, "blocksworld", "*.cnf")))[:2]
    for p in paths:
        f = read_dimacs(p)
        assert not Propagator(f).units(), \
            f"{os.path.basename(p)}: expected no unit clauses"
        # propagate from a literal known to be a backbone, which is what the
        # algorithm does after it commits one
        prop = Propagator(f)
        seed = _a_backbone_of(f)
        ok, derived = prop.assign([seed])
        assert ok, f"{os.path.basename(p)}: propagation hit a conflict"
        assert derived, f"{os.path.basename(p)}: committing {seed} derived nothing"
        for lit in derived:
            assert is_backbone(f, lit, SOLVER), \
                f"{os.path.basename(p)}: propagated {lit} is not a backbone"
        print(f"  {os.path.basename(p):<18} {len(derived)} propagated literals, "
              f"all confirmed backbones")


def _a_backbone_of(f: Cnf) -> int:
    """First backbone literal of the formula, used to seed a propagation"""
    for v in range(1, f.n_vars + 1):
        for lit in (v, -v):
            if is_backbone(f, lit, SOLVER):
                return lit
    raise AssertionError("formula has no backbone to propagate from")


def test_calls_are_counted() -> None:
    """The reported call count must be positive and bounded by the naive 2n"""
    p = sorted(glob.glob(os.path.join(ALLSAT, "uf50-218", "*.cnf")))[0]
    f = read_dimacs(p)
    for algo in ALGORITHMS:
        r = backbones(f, algo, SOLVER)
        assert r.calls >= 1, f"{algo}: no calls counted"
        assert r.calls <= 2 * f.n_vars, \
            f"{algo}: {r.calls} calls exceeds the naive {2 * f.n_vars}"
        print(f"  {algo:<12} {r.calls:4d} calls against a naive {2 * f.n_vars}")


if __name__ == "__main__":
    for test in [
        test_small_known,
        test_unsatisfiable,
        test_propagation_is_sound,
        test_algorithms_agree,
        test_algorithms_agree_as_sets,
        test_exhaustive_small,
        test_cbs_ground_truth,
        test_cbs_set_is_exact,
        test_calls_are_counted,
    ]:
        print(f"{test.__name__}:")
        test()
    print("\nall tests passed")
