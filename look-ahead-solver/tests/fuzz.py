# Random CNF fuzzing against brute force
#
# Generates small random instances near the phase transition so roughly half are
# satisfiable, and checks the verdict and any reported model
#
# usage: python fuzz.py <dpll> [rounds] [seed]

import itertools
import os
import random
import subprocess
import sys
import tempfile


def random_cnf(rng, nvars, nclauses, width):
    clauses = []
    for _ in range(nclauses):
        vs = rng.sample(range(1, nvars + 1), min(width, nvars))
        clauses.append([v if rng.random() < 0.5 else -v for v in vs])
    return clauses


def brute_force(nvars, clauses):
    for bits in itertools.product([False, True], repeat=nvars):
        val = (None,) + bits
        if all(any(val[abs(l)] == (l > 0) for l in c) for c in clauses):
            return True
    return False


# One scratch file reused across rounds; creating and deleting thousands of them
# trips Windows file locking often enough to fail a run
def run(dpll, path, nvars, clauses, extra=()):
    with open(path, "w") as f:
        f.write(f"p cnf {nvars} {len(clauses)}\n")
        for c in clauses:
            f.write(" ".join(str(l) for l in c) + " 0\n")
    out = subprocess.run([dpll, *extra, path], capture_output=True, text=True,
                         check=True).stdout

    lines = [l for l in out.splitlines() if not l.startswith("c")]
    verdict = lines[0].strip()
    model = None
    for l in lines:
        if l.startswith("v"):
            model = [int(x) for x in l.split()[1:-1]]
    return verdict, model


def main(dpll, rounds, seed, extra=()):
    fd, path = tempfile.mkstemp(suffix=".cnf")
    os.close(fd)
    try:
        return rounds_loop(dpll, path, rounds, seed, extra)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def rounds_loop(dpll, path, rounds, seed, extra):
    rng = random.Random(seed)
    sat_count = 0

    for i in range(rounds):
        nvars = rng.randint(1, 12)
        width = rng.choice([1, 2, 3, 3, 3, 4])
        nclauses = rng.randint(0, int(nvars * 4.5) + 2)
        clauses = random_cnf(rng, nvars, nclauses, width)

        want = brute_force(nvars, clauses)
        verdict, model = run(dpll, path, nvars, clauses, extra)
        sat_count += want

        if verdict != ("SAT" if want else "UNSAT"):
            print(f"MISMATCH seed={seed} round={i}: solver={verdict} truth={want}")
            print(f"p cnf {nvars} {len(clauses)}")
            for c in clauses:
                print(" ".join(str(l) for l in c), 0)
            return 1

        if want:
            if sorted(abs(l) for l in model) != list(range(1, nvars + 1)):
                print(f"MISMATCH seed={seed} round={i}: model does not cover every variable")
                return 1
            val = {abs(l): (l > 0) for l in model}
            for c in clauses:
                if not any(val[abs(l)] == (l > 0) for l in c):
                    print(f"MISMATCH seed={seed} round={i}: model falsifies {c}")
                    return 1

    label = " ".join(extra) if extra else "adjacency"
    print(f"ok   {rounds} random instances, {sat_count} sat / "
          f"{rounds - sat_count} unsat  [{label}]")
    return 0


def _rel(p):
    # Windows python will not spawn a bare relative path like bin/dpll.exe
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


if __name__ == "__main__":
    args = sys.argv[1:]
    extra = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-")]
    dpll = _rel(pos[0])
    rounds = int(pos[1]) if len(pos) > 1 else 500
    seed = int(pos[2]) if len(pos) > 2 else 1
    sys.exit(main(dpll, rounds, seed, extra))
