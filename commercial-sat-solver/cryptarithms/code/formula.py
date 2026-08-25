"""Boolean combinations of cryptarithm equations

An equation is turned into a single variable s with s true when the equation
holds and false when it does not
The boolean structure over the selector variables uses Tseitin encoding

Connectives: ||, OR, &&, AND, NOT and ! 

An equation carries no spaces, so it is always one token
OR AND and NOT are connectives only when they stand alone as a whole token,
which leaves them usable as ordinary words inside an equation
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Union

from cryptarithm import Equation, parse as parse_equation


@dataclass
class Eq:
    equation: Equation

    def __str__(self) -> str:
        return str(self.equation)


@dataclass
class Not:
    child: "Formula"

    def __str__(self) -> str:
        return f"NOT {self.child}"


@dataclass
class And:
    children: List["Formula"]

    def __str__(self) -> str:
        return "(" + " AND ".join(str(c) for c in self.children) + ")"


@dataclass
class Or:
    children: List["Formula"]

    def __str__(self) -> str:
        return "(" + " OR ".join(str(c) for c in self.children) + ")"


Formula = Union[Eq, Not, And, Or]


def equations(f: Formula) -> List[Equation]:
    if isinstance(f, Eq):
        return [f.equation]
    if isinstance(f, Not):
        return equations(f.child)
    return [e for c in f.children for e in equations(c)]


def letters(f: Formula) -> List[str]:
    seen: List[str] = []
    for eq in equations(f):
        for ch in eq.letters:
            if ch not in seen:
                seen.append(ch)
    return seen


# Parsing

TOKEN = re.compile(r"\(|\)|\|\||&&|!|[A-Za-z0-9+\-=]+")


def tokenize(text: str) -> List[str]:
    out = []
    for t in TOKEN.findall(text):
        upper = t.upper()
        if upper in ("OR", "AND", "NOT"):
            out.append(upper)
        elif t == "||":
            out.append("OR")
        elif t == "&&":
            out.append("AND")
        elif t == "!":
            out.append("NOT")
        else:
            out.append(t)
    return out


def parse(text: str) -> Formula:
    """for reading a formula, simplest case is an equation on its own"""
    tokens = tokenize(text)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def primary() -> Formula:
        t = peek()
        if t is None:
            raise ValueError("unexpected end of formula")
        if t == "(":
            take()
            f = disjunction()
            if take() != ")":
                raise ValueError("expected a closing parenthesis")
            return f
        if t == "NOT":
            take()
            return Not(primary())
        if t in ("OR", "AND", ")"):
            raise ValueError(f"unexpected {t}")
        return Eq(parse_equation(take()))

    def conjunction() -> Formula:
        parts = [primary()]
        while peek() == "AND":
            take()
            parts.append(primary())
        return parts[0] if len(parts) == 1 else And(parts)

    def disjunction() -> Formula:
        parts = [conjunction()]
        while peek() == "OR":
            take()
            parts.append(conjunction())
        return parts[0] if len(parts) == 1 else Or(parts)

    f = disjunction()
    if pos[0] != len(tokens):
        raise ValueError(f"trailing input at {tokens[pos[0]]!r}")
    return f


# Encoding

def encode(f: Formula, base: int = 10, distinct: bool = True,
           leading_zero: bool = False):
    """builds the CNF for a formula over equations

    A formula that is a single equation is asserted directly, without a
    selector
    """
    from cryptarithm import Encoder

    enc = Encoder(letters(f), base, distinct, leading_zero)

    if isinstance(f, Eq):
        enc.assert_equation(f.equation)
        return enc.finish()

    def walk(node: Formula) -> int:
        if isinstance(node, Eq):
            return enc.reify_equation(node.equation)

        if isinstance(node, Not):
            return -walk(node.child)

        kids = [walk(c) for c in node.children]
        g = enc.pool.new()
        if isinstance(node, And):
            for lit in kids:
                enc.clauses.append([-g, lit])
            enc.clauses.append([g] + [-lit for lit in kids])
        else:
            enc.clauses.append([-g] + kids)
            for lit in kids:
                enc.clauses.append([g, -lit])
        return g

    root = walk(f)
    enc.clauses.append([root])
    return enc.finish()
