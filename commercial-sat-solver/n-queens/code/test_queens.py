"""Brute-force validation of the encoding, no SAT solver needed"""

from __future__ import annotations

from itertools import combinations, permutations, product
from typing import Dict, List

from nqueens import CNF, clause_count, decode, diagonals, encode, render, var, verify

# number of solutions of n-queens for small n
KNOWN = {1: 1, 2: 0, 3: 0, 4: 2, 5: 10, 6: 4, 7: 40}


def satisfied(clauses: CNF, assign: Dict[int, bool]) -> bool:
    return all(any(assign[abs(l)] == (l > 0) for l in cl) for cl in clauses)


def assignment_of(board: List[int], n: int) -> Dict[int, bool]:
    """Board given as pos[r] = column, turned into a full variable assignment"""
    assign = {v: False for v in range(1, n * n + 1)}
    for r, c in enumerate(board):
        assign[var(r, c, n)] = True
    return assign


def test_model_count() -> None:
    """Enumerate every assignment and compare the model count to KNOWN"""
    for n in [1, 2, 3, 4]:
        enc = encode(n)
        count = 0
        for bits in product([False, True], repeat=enc.n_vars):
            assign = {i + 1: bits[i] for i in range(enc.n_vars)}
            if satisfied(enc.clauses, assign):
                count += 1
                model = [i + 1 if bits[i] else -(i + 1) for i in range(enc.n_vars)]
                assert verify(decode(model, n), n), f"n={n} model is not a valid board"
        assert count == KNOWN[n], f"n={n} got {count} models, expected {KNOWN[n]}"
        print(f"  n={n} vars={enc.n_vars} clauses={enc.n_clauses} models={count}")


def test_valid_boards_satisfy() -> None:
    """Every non-attacking placement must satisfy the CNF"""
    for n in [4, 5, 6, 7]:
        enc = encode(n)
        boards = [p for p in permutations(range(n)) if verify(p, n)]
        assert len(boards) == KNOWN[n], f"n={n} found {len(boards)} boards"
        for board in boards:
            assert satisfied(enc.clauses, assignment_of(list(board), n)), \
                f"n={n} valid board {board} rejected by the CNF"
        print(f"  n={n} boards={len(boards)} all satisfy the CNF")


def test_attacking_boards_rejected() -> None:
    """Placements with an attack must not satisfy the CNF"""
    n = 8
    enc = encode(n)
    bad = [
        [0, 1, 2, 3, 4, 5, 6, 7],   # all on one diagonal
        [0, 0, 0, 0, 0, 0, 0, 0],   # all in one column
        [0, 4, 7, 5, 2, 6, 1, 0],   # column 0 used twice
    ]
    for board in bad:
        assert not verify(board, n), f"verify accepted {board}"
        assert not satisfied(enc.clauses, assignment_of(board, n)), \
            f"CNF accepted attacking board {board}"
    print(f"  n={n} {len(bad)} attacking boards rejected")


def test_diagonal_groups() -> None:
    """Diagonal groups must cover exactly the diagonally attacking pairs"""
    for n in [1, 2, 3, 4, 5, 8]:
        groups = list(diagonals(n))
        from_groups = sum(len(g) * (len(g) - 1) // 2 for g in groups)
        cells = [(r, c) for r in range(n) for c in range(n)]
        direct = sum(
            1
            for (r1, c1), (r2, c2) in combinations(cells, 2)
            if abs(r1 - r2) == abs(c1 - c2)
        )
        assert from_groups == direct, f"n={n} {from_groups} pairs vs {direct} expected"
        print(f"  n={n} groups={len(groups)} pairs={from_groups}")


def test_clause_count() -> None:
    """clause_count must agree with the length of the built encoding"""
    for n in [1, 2, 3, 4, 5, 8, 16, 32, 64]:
        built = encode(n).n_clauses
        counted = clause_count(n)
        assert built == counted, f"n={n} built {built} but counted {counted}"
        print(f"  n={n} clauses={built}")


def test_known_solution() -> None:
    """A known 8-queens solution must satisfy the CNF"""
    n = 8
    board = [0, 4, 7, 5, 2, 6, 1, 3]
    assert verify(board, n)
    assert satisfied(encode(n).clauses, assignment_of(board, n))
    print(render(board, n))


if __name__ == "__main__":
    for test in [
        test_model_count,
        test_valid_boards_satisfy,
        test_attacking_boards_rejected,
        test_diagonal_groups,
        test_clause_count,
        test_known_solution,
    ]:
        print(f"{test.__name__}:")
        test()
    print("\nall tests passed")
