"""Cryptarithms solved by a SAT solver, one-hot encoding

A letter is represented by k Boolean variables, one per digit, of which one is
true. Column sums and carries are represented the same way, as one-hot
integers, so the whole encoding uses a single kind of variable

An equation w1 op w2 op ... = s is rearranged so that both sides are sums of
words, the positive terms on one side and the negative terms together with the
result on the other. The two sums are then required to agree digit by digit
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

Clause = List[int]


@dataclass
class Equation:
    """terms carries the signed words of the left side, result is the right side"""

    terms: List[Tuple[int, str]]
    result: str

    @property
    def words(self) -> List[str]:
        return [w for _, w in self.terms] + [self.result]

    @property
    def letters(self) -> List[str]:
        seen: List[str] = []
        for w in self.words:
            for ch in w:
                if ch not in seen:
                    seen.append(ch)
        return seen

    def __str__(self) -> str:
        out = self.terms[0][1]
        for sign, w in self.terms[1:]:
            out += ("+" if sign > 0 else "-") + w
        return out + "=" + self.result


def parse(text: str) -> Equation:
    """Read an equation such as SEND+MORE=MONEY"""
    text = re.sub(r"\s+", "", text).upper()
    if text.count("=") != 1:
        raise ValueError(f"expected one '=' in {text!r}")

    lhs, rhs = text.split("=")
    if not re.fullmatch(r"[A-Z]+", rhs):
        raise ValueError(f"right side {rhs!r} is not a word")

    tokens = re.findall(r"[+-]?[A-Z]+", lhs)
    if not tokens or "".join(tokens) != lhs:
        raise ValueError(f"cannot read the left side of {text!r}")

    terms = []
    for t in tokens:
        if t[0] == "-":
            terms.append((-1, t[1:]))
        elif t[0] == "+":
            terms.append((1, t[1:]))
        else:
            terms.append((1, t))
    return Equation(terms=terms, result=rhs)


# One-hot integers

class Pool:
    """Variable allocator"""

    def __init__(self) -> None:
        self.top = 0

    def new(self) -> int:
        self.top += 1
        return self.top


class Num:
    """An integer held as one-hot variables over lo to hi

    var[v] is true when the integer takes the value v
    """

    def __init__(self, pool: Pool, lo: int, hi: int, clauses: List[Clause],
                 exactly_one: bool = True) -> None:
        self.lo, self.hi = lo, hi
        self.var: Dict[int, int] = {v: pool.new() for v in range(lo, hi + 1)}
        if exactly_one:
            add_exactly_one(list(self.var.values()), pool, clauses)

    @property
    def values(self) -> range:
        return range(self.lo, self.hi + 1)

    def lits(self) -> List[int]:
        return [self.var[v] for v in self.values]


def constant(pool: Pool, value: int, clauses: List[Clause]) -> Num:
    n = Num(pool, value, value, clauses, exactly_one=False)
    clauses.append([n.var[value]])
    return n


def add_exactly_one(lits: Sequence[int], pool: Pool, clauses: List[Clause]) -> None:
    """At least one, plus at most one

    Pairwise is smallest for short lists, a sequential chain with one auxiliary
    variable per position is used once that would be too many clauses
    """
    lits = list(lits)
    clauses.append(list(lits))

    n = len(lits)
    if n < 2:
        return
    if n <= 8:
        for i in range(n):
            for j in range(i + 1, n):
                clauses.append([-lits[i], -lits[j]])
        return

    # sequential: s_i means one of the first i literals is true
    s = [pool.new() for _ in range(n - 1)]
    clauses.append([-lits[0], s[0]])
    clauses.append([-lits[n - 1], -s[n - 2]])
    for i in range(1, n - 1):
        clauses.append([-lits[i], s[i]])
        clauses.append([-s[i - 1], s[i]])
        clauses.append([-lits[i], -s[i - 1]])


def add(a: Num, b: Num, pool: Pool, clauses: List[Clause]) -> Num:
    """One-hot sum of two one-hot integers"""
    c = Num(pool, a.lo + b.lo, a.hi + b.hi, clauses)
    for va in a.values:
        for vb in b.values:
            clauses.append([-a.var[va], -b.var[vb], c.var[va + vb]])
    return c


def split(total: Num, base: int, pool: Pool, clauses: List[Clause]) -> Tuple[Num, Num]:
    """Break a column total into its digit and the carry into the next column

    total = digit + base * carry, and since that has one solution for each
    value of total the relation is two clauses per value
    """
    digit = Num(pool, 0, base - 1, clauses)
    carry = Num(pool, total.lo // base, total.hi // base, clauses)
    for v in total.values:
        clauses.append([-total.var[v], digit.var[v % base]])
        clauses.append([-total.var[v], carry.var[v // base]])
    return digit, carry


# Encoding

@dataclass
class Encoding:
    n_vars: int
    clauses: List[Clause]
    letters: List[str]
    digit_var: Dict[str, Dict[int, int]]
    base: int

    @property
    def n_clauses(self) -> int:
        return len(self.clauses)

    def decode(self, model: Sequence[int]) -> Dict[str, int]:
        true = {l for l in model if l > 0}
        out = {}
        for ch, per_digit in self.digit_var.items():
            for d, v in per_digit.items():
                if v in true:
                    out[ch] = d
                    break
        return out

    def block(self, assignment: Dict[str, int]) -> Clause:
        """Clause forbidding one letter assignment

        Only the letter variables appear, never the auxiliary ones, so a
        solution is excluded once and not once per internal configuration
        """
        return [-self.digit_var[ch][d] for ch, d in assignment.items()]


class Encoder:
    """Shared alphabet and clause set for one or more equations"""

    def __init__(self, letters: Sequence[str], base: int = 10,
                 distinct: bool = True, leading_zero: bool = False) -> None:
        if distinct and len(letters) > base:
            raise ValueError(
                f"{len(letters)} letters cannot be distinct digits in base {base}")

        self.base = base
        self.leading_zero = leading_zero
        self.letters = list(letters)
        self.pool = Pool()
        self.clauses: List[Clause] = []

        self.digit_var = {ch: {d: self.pool.new() for d in range(base)}
                          for ch in self.letters}
        for ch in self.letters:
            add_exactly_one(list(self.digit_var[ch].values()), self.pool, self.clauses)

        if distinct:
            for d in range(base):
                column = [self.digit_var[ch][d] for ch in self.letters]
                for i in range(len(column)):
                    for j in range(i + 1, len(column)):
                        self.clauses.append([-column[i], -column[j]])

    def forbid_leading_zeros(self, words: Sequence[str]) -> None:
        """A word of more than one letter may not start with zero

        This holds for every word that appears, whether or not the equation it
        belongs to is asserted, since it is a property of the notation
        """
        if self.leading_zero:
            return
        for w in words:
            if len(w) > 1:
                self.clauses.append([-self.digit_var[w[0]][0]])

    def width_for(self, eq: Equation) -> int:
        longest = max(len(w) for w in eq.words)
        extra = 1
        while self.base ** extra <= len(eq.terms) + 1:
            extra += 1
        return longest + extra

    def sides(self, eq: Equation) -> Tuple[List[Num], List[Num]]:
        left = [w for sign, w in eq.terms if sign > 0]
        right = [w for sign, w in eq.terms if sign < 0] + [eq.result]
        width = self.width_for(eq)
        return (sum_words(left, self.digit_var, self.base, width, self.pool, self.clauses),
                sum_words(right, self.digit_var, self.base, width, self.pool, self.clauses))

    def assert_equation(self, eq: Equation) -> None:
        """State that the equation holds, with no selector variable"""
        self.forbid_leading_zeros(eq.words)
        digits_l, digits_r = self.sides(eq)
        for i in range(len(digits_l)):
            for v in range(self.base):
                self.clauses.append([-digits_l[i].var[v], digits_r[i].var[v]])
                self.clauses.append([-digits_r[i].var[v], digits_l[i].var[v]])

    def reify_equation(self, eq: Equation) -> int:
        """Return a variable that is true when the equation holds

        The column sums are built unconditionally because they are determined
        by the letters, so only the comparison of the two sides needs a
        biconditional, which is what lets an equation be negated
        """
        self.forbid_leading_zeros(eq.words)
        digits_l, digits_r = self.sides(eq)

        same: List[int] = []
        for i in range(len(digits_l)):
            per_value = []
            for v in range(self.base):
                m = self.pool.new()
                self.clauses.append([-m, digits_l[i].var[v]])
                self.clauses.append([-m, digits_r[i].var[v]])
                self.clauses.append([m, -digits_l[i].var[v], -digits_r[i].var[v]])
                per_value.append(m)

            e = self.pool.new()
            self.clauses.append([-e] + per_value)
            for m in per_value:
                self.clauses.append([e, -m])
            same.append(e)

        s = self.pool.new()
        for e in same:
            self.clauses.append([-s, e])
        self.clauses.append([s] + [-e for e in same])
        return s

    def finish(self) -> "Encoding":
        return Encoding(n_vars=self.pool.top, clauses=self.clauses,
                        letters=self.letters, digit_var=self.digit_var,
                        base=self.base)


def encode(eq: Equation, base: int = 10, distinct: bool = True,
           leading_zero: bool = False) -> Encoding:
    """Build the CNF for one equation asserted directly"""
    enc = Encoder(eq.letters, base, distinct, leading_zero)
    enc.assert_equation(eq)
    return enc.finish()


def sum_words(words: Sequence[str], digit_var, base: int, width: int,
              pool: Pool, clauses: List[Clause]) -> List[Num]:
    """Column by column addition of several words, returning the result digits"""
    zero = constant(pool, 0, clauses)
    carry = zero
    out: List[Num] = []

    for pos in range(width):
        total = carry
        for w in words:
            if pos < len(w):
                ch = w[len(w) - 1 - pos]
                d = Num(pool, 0, base - 1, clauses, exactly_one=False)
                for v in range(base):
                    clauses.append([-d.var[v], digit_var[ch][v]])
                    clauses.append([-digit_var[ch][v], d.var[v]])
                total = add(total, d, pool, clauses)
        digit, carry = split(total, base, pool, clauses)
        out.append(digit)

    for v in carry.values:
        if v != 0:
            clauses.append([-carry.var[v]])
    return out


# Solving

@dataclass
class Solution:
    assignment: Dict[str, int]

    def value(self, word: str, base: int = 10) -> int:
        n = 0
        for ch in word:
            n = n * base + self.assignment[ch]
        return n

    def render(self, eq: Equation, base: int = 10) -> str:
        def val(w):
            n = 0
            for ch in w:
                n = n * base + self.assignment[ch]
            return n
        parts = [str(val(eq.terms[0][1]))]
        for sign, w in eq.terms[1:]:
            parts.append(("+" if sign > 0 else "-") + str(val(w)))
        return "".join(parts) + "=" + str(val(eq.result))


@dataclass
class Result:
    equation: Optional[Equation] = None
    formula: object = None
    solutions: List[Solution] = field(default_factory=list)
    calls: int = 0
    n_vars: int = 0
    n_clauses: int = 0
    encode_time: float = 0.0
    solve_time: float = 0.0
    limit_reached: bool = False

    @property
    def count(self) -> int:
        return len(self.solutions)

    @property
    def unique(self) -> Optional[bool]:
        if self.limit_reached:
            return None
        return self.count == 1


def solve(eq: Equation, base: int = 10, distinct: bool = True,
          leading_zero: bool = False, limit: Optional[int] = 1,
          solver_name: str = "cadical153") -> Result:
    """Find solutions, stopping after limit of them when limit is given

    limit of None enumerates every solution, which is what the counting option
    needs
    """
    from pysat.solvers import Solver

    r = Result(equation=eq)

    t0 = time.perf_counter()
    enc = encode(eq, base, distinct, leading_zero)
    r.encode_time = time.perf_counter() - t0
    r.n_vars, r.n_clauses = enc.n_vars, enc.n_clauses
    return _enumerate(enc, r, limit, solver_name)


def solve_formula(f, base: int = 10, distinct: bool = True,
                  leading_zero: bool = False, limit: Optional[int] = 1,
                  solver_name: str = "cadical153") -> Result:
    """Find solutions of a boolean combination of equations"""
    import formula as formula_module

    r = Result(equation=None, formula=f)

    t0 = time.perf_counter()
    enc = formula_module.encode(f, base, distinct, leading_zero)
    r.encode_time = time.perf_counter() - t0
    r.n_vars, r.n_clauses = enc.n_vars, enc.n_clauses
    return _enumerate(enc, r, limit, solver_name)


def is_unique(f, base: int = 10, distinct: bool = True,
              leading_zero: bool = False,
              solver_name: str = "cadical153") -> Tuple[Optional[bool], Result]:
    """Decide whether the formula has one solution and no more

    Two solutions are enough to answer, so the search stops there instead of
    enumerating everything. None means there is no solution at all
    """
    r = solve_formula(f, base, distinct, leading_zero, limit=2,
                      solver_name=solver_name)
    if r.count == 0:
        return None, r
    return r.count == 1, r


def _enumerate(enc: "Encoding", r: "Result", limit: Optional[int],
               solver_name: str) -> "Result":
    from pysat.solvers import Solver

    s = Solver(name=solver_name, bootstrap_with=enc.clauses)
    try:
        while True:
            t0 = time.perf_counter()
            sat = s.solve()
            r.solve_time += time.perf_counter() - t0
            r.calls += 1
            if not sat:
                break

            assignment = enc.decode(s.get_model())
            r.solutions.append(Solution(assignment=assignment))
            if limit is not None and r.count >= limit:
                r.limit_reached = True
                break
            s.add_clause(enc.block(assignment))
    finally:
        s.delete()

    return r


if __name__ == "__main__":
    import sys

    import formula as formula_module

    if len(sys.argv) < 2:
        print("usage: python cryptarithm.py <formula> [--base k] [--all] "
              "[--repeat] [--leading-zero]")
        print('  a formula is an equation, or equations joined by AND, OR, NOT')
        print('  example: "SEND+MORE=MONEY"')
        print('  example: "A+B=C OR D+E=F"')
        raise SystemExit(2)

    args = sys.argv[1:]
    base = 10
    limit: Optional[int] = 1
    distinct = True
    leading_zero = False
    text = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--base":
            i += 1
            base = int(args[i])
        elif a == "--all":
            limit = None
        elif a == "--repeat":
            distinct = False
        elif a == "--leading-zero":
            leading_zero = True
        else:
            text = a
        i += 1

    try:
        f = formula_module.parse(text)
        res = solve_formula(f, base, distinct, leading_zero, limit)
    except ValueError as e:
        print(f"cannot solve: {e}")
        raise SystemExit(1)

    alphabet = formula_module.letters(f)
    eqs = formula_module.equations(f)

    if res.count == 0:
        print("no solutions")
    else:
        word = "solution" if res.count == 1 else "solutions"
        suffix = " or more" if res.limit_reached else ""
        print(f"{res.count}{suffix} {word} found:")
        for n, sol in enumerate(res.solutions, 1):
            shown = " ".join(f"{ch}={sol.assignment[ch]}" for ch in alphabet)
            print(f"  {n}. {shown}")
            for eq in eqs:
                print(f"       {eq}  ->  {sol.render(eq, base)}")
    print(f"c {res.n_vars} variables, {res.n_clauses} clauses, {res.calls} solver calls")
