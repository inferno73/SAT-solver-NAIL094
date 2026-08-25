"""Checks for the cryptarithm encoder

The brute force reference and the collection solutions are used only here, they
take no part in any measurement
"""

from __future__ import annotations

import random
from itertools import permutations, product
from typing import Dict, List, Optional

import formula as F
from cryptarithm import Equation, is_unique, parse, solve_formula
from instances import BENCHMARK, load_all

SOLVER = "cadical153"


def brute_force(text: str, base: int = 10, distinct: bool = True,
                leading_zero: bool = False) -> List[Dict[str, int]]:
    """every assignment tried one by one, but tested only for few letters"""
    f = F.parse(text)
    letters = F.letters(f)
    eqs = F.equations(f)
    lead = {w[0] for e in eqs for w in e.words if len(w) > 1}

    def value(w, a):
        n = 0
        for ch in w:
            n = n * base + a[ch]
        return n

    def holds(e, a):
        return sum(s * value(w, a) for s, w in e.terms) == value(e.result, a)

    def truth(node, a):
        if isinstance(node, F.Eq):
            return holds(node.equation, a)
        if isinstance(node, F.Not):
            return not truth(node.child, a)
        if isinstance(node, F.And):
            return all(truth(c, a) for c in node.children)
        return any(truth(c, a) for c in node.children)

    source = (permutations(range(base), len(letters)) if distinct
              else product(range(base), repeat=len(letters)))
    out = []
    for combo in source:
        a = dict(zip(letters, combo))
        if not leading_zero and any(a[c] == 0 for c in lead):
            continue
        if truth(f, a):
            out.append(a)
    return out


def count(text, base=10, distinct=True, leading_zero=False) -> int:
    return solve_formula(F.parse(text), base, distinct, leading_zero,
                         limit=None, solver_name=SOLVER).count


def test_parsing() -> None:
    """Equations and formulas are read as written"""
    eq = parse("SEND+MORE=MONEY")
    assert [w for _, w in eq.terms] == ["SEND", "MORE"]
    assert eq.result == "MONEY"
    assert str(eq) == "SEND+MORE=MONEY"

    eq = parse("A-B+C=D")
    assert [s for s, _ in eq.terms] == [1, -1, 1]

    f = F.parse("A+B=C OR NOT D+E=F")
    assert isinstance(f, F.Or)
    assert isinstance(f.children[1], F.Not)

    f = F.parse("A+B=C && (D+E=F || G+H=I)")
    assert isinstance(f, F.And)
    assert isinstance(f.children[1], F.Or)

    # OR is a legal word inside an equation
    eq = parse("SEE+OR+HEAR=THERE")
    assert [w for _, w in eq.terms] == ["SEE", "OR", "HEAR"]
    print("  equations, signs, connectives and OR as a word")


def test_against_brute_force() -> None:
    """Solution counts agree with enumeration, in both uniqueness modes"""
    cases = [
        "AB+BA=CD",
        "AB+BA=CDE",
        "TWO+TWO=FOUR",
        "A+B=CD",
        "AB-BA=CD",
        "NOT AB+BA=CDE AND AB+BA=CD",
        "AB+BA=CD OR AB+BA=CDE",
    ]
    for text in cases:
        for distinct in (True, False):
            want = len(brute_force(text, distinct=distinct))
            got = count(text, distinct=distinct)
            assert got == want, f"{text} distinct={distinct}: got {got}, expected {want}"
        print(f"  {text:<34} matches enumeration in both modes")


def test_other_bases() -> None:
    """testing for parameter k (doesnt necessarily need to be 10)"""
    for base in (5, 8, 10, 16):
        for text in ("AB+BA=CD", "A+B=CD"):
            want = len(brute_force(text, base=base))
            got = count(text, base=base)
            assert got == want, f"{text} base {base}: got {got}, expected {want}"
        print(f"  base {base:2d} agrees with enumeration")


def test_leading_zero_rule() -> None:
    """A word of several letters cant start with zero, a single letter can"""
    assert count("A+A=B") == len(brute_force("A+A=B"))

    # A+BC=BC forces A to be zero, which is allowed for a one letter word
    sols = solve_formula(F.parse("A+BC=BC"), limit=None).solutions
    assert sols, "A+BC=BC should be solvable with A equal to zero"
    assert all(s.assignment["A"] == 0 for s in sols)
    assert len(sols) == len(brute_force("A+BC=BC"))
    print(f"  A+BC=BC gives {len(sols)} solutions, all with A zero")

    # the same is not allowed once the word has more than one letter
    without = count("AB+BA=CD")
    with_zero = count("AB+BA=CD", leading_zero=True)
    assert with_zero >= without
    print(f"  AB+BA=CD gives {without} normally and {with_zero} "
          f"when leading zeros are permitted")


def test_collection_solutions() -> None:
    """The digits found match the ones printed in the collection"""
    puzzles = load_all()
    rng = random.Random(11)
    sample = rng.sample(puzzles, 120)

    for p in sample:
        r = solve_formula(F.parse(p.text), limit=None, solver_name=SOLVER)
        assert r.count >= 1, f"{p.text}: no solution found"
        found = [s.assignment for s in r.solutions]
        assert p.expected in found, (
            f"{p.text}: collection says {p.expected}, "
            f"solver found {found[:2]}")
    print(f"  {len(sample)} puzzles, the published assignment is among those found")


def test_uniqueness_matches_collection() -> None:
    """The collection lists puzzles that have a unique solution"""
    puzzles = load_all()
    rng = random.Random(5)
    sample = rng.sample(puzzles, 80)

    disagree = 0
    for p in sample:
        unique, _ = is_unique(F.parse(p.text), solver_name=SOLVER)
        if unique is not True:
            disagree += 1
    assert disagree == 0, f"{disagree} of {len(sample)} were not unique"
    print(f"  {len(sample)} puzzles, all confirmed to have one solution only")


def test_compound_formula_semantics() -> None:
    """A conjunction is the intersection and a disjunction the union"""
    a, b = "TWO+TWO=FOUR", "AB+BA=CDE"
    sols_a = {tuple(sorted(s.assignment.items()))
              for s in solve_formula(F.parse(a), limit=None).solutions}
    assert len(sols_a) == count(a)

    # over a shared alphabet the union and intersection can be checked directly
    x, y = "AB+BA=CD", "AB+BA=CDE"
    both = count(f"{x} AND {y}")
    either = count(f"{x} OR {y}")
    only_x, only_y = count(x), count(y)
    assert both == len(brute_force(f"{x} AND {y}"))
    assert either == len(brute_force(f"{x} OR {y}"))
    assert either <= only_x + only_y
    print(f"  AND gives {both}, OR gives {either}, from {only_x} and {only_y}")


def test_benchmark() -> None:
    """The instance given by the task"""
    eq = parse(BENCHMARK)
    assert len(eq.terms) == 41
    assert len(eq.letters) == 10

    r = solve_formula(F.parse(BENCHMARK), limit=1, solver_name=SOLVER)
    assert r.count == 1
    a = r.solutions[0].assignment

    def value(w):
        n = 0
        for ch in w:
            n = n * 10 + a[ch]
        return n

    lhs = sum(sign * value(w) for sign, w in eq.terms)
    assert lhs == value(eq.result), f"{lhs} against {value(eq.result)}"
    assert len(set(a.values())) == len(a), "letters are not distinct"
    lead = {w[0] for w in eq.words if len(w) > 1}
    assert all(a[c] != 0 for c in lead), "a word starts with zero"
    print(f"  41 addends, 10 letters, sum {lhs} equals TESTS, {r.solve_time:.2f}s")


if __name__ == "__main__":
    for test in [
        test_parsing,
        test_against_brute_force,
        test_other_bases,
        test_leading_zero_rule,
        test_compound_formula_semantics,
        test_collection_solutions,
        test_uniqueness_matches_collection,
        test_benchmark,
    ]:
        print(f"{test.__name__}:")
        test()
    print("\nall tests passed")
