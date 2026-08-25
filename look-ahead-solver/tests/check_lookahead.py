"""
Every solver configuration must reach the same verdict, and every model must be
a real model

The propagation engine and the branching rule are independent choices, so a
disagreement between any two configurations is a bug in one of them
Look-ahead also reports how much reasoning it did, which is printed so that a
technique quietly ceasing to fire is visible

usage: python check_lookahead.py <dpll> <file> [<file> ...]
"""

import os
import subprocess
import sys

CONFIGS = [
    ("dpll", []),
    ("watched", ["--watched"]),
    ("counters", ["--counters"]),
    ("la/crh", ["--lookahead", "--heuristic=crh"]),
    ("la/wbh", ["--lookahead", "--heuristic=wbh"]),
    ("la/bsh", ["--lookahead", "--heuristic=bsh"]),
    ("la/bare", ["--lookahead", "--no-learning", "--no-autarky"]),
]


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def read_clauses(path):
    nvars, clauses, cur = 0, [], []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s[0] == "c":
                continue
            if s[0] == "p":
                nvars = int(s.split()[2])
                continue
            if s[0] == "%":
                break
            for tok in s.split():
                d = int(tok)
                if d == 0:
                    clauses.append(cur)
                    cur = []
                else:
                    cur.append(d)
    return nvars, clauses


def run(dpll, args, path):
    out = subprocess.run([dpll, *args, path], capture_output=True, text=True,
                         check=True).stdout
    verdict, model, stats = None, None, {}
    for line in out.splitlines():
        s = line.strip()
        if s in ("SAT", "UNSAT"):
            verdict = s
        elif s.startswith("v "):
            model = [int(x) for x in s.split()[1:-1]]
        elif s.startswith("c "):
            k, _, v = s[2:].rpartition(" ")
            stats[k.strip()] = v.strip()
    return verdict, model, stats


def check(dpll, path):
    # .sat input is encoded inside the solver, so its clauses are not in the
    # file; those are verdict-only here and have models validated by
    # check_solver.py instead
    dimacs = not path.endswith(".sat")
    nvars, clauses = read_clauses(path) if dimacs else (0, [])
    base, ok, note = None, True, ""

    for name, args in CONFIGS:
        verdict, model, stats = run(dpll, args, path)
        if base is None:
            base = verdict
        elif verdict != base:
            print(f"FAIL {path} [{name}]: {verdict}, but dpll said {base}")
            ok = False
            continue

        if verdict == "SAT" and dimacs:
            if model is None:
                print(f"FAIL {path} [{name}]: SAT without a model line")
                ok = False
                continue
            val = {abs(l): (l > 0) for l in model}
            if sorted(val) != list(range(1, nvars + 1)):
                print(f"FAIL {path} [{name}]: model does not assign every variable")
                ok = False
                continue
            bad = [c for c in clauses if not any(val[abs(l)] == (l > 0) for l in c)]
            if bad:
                print(f"FAIL {path} [{name}]: model falsifies {bad[0]}")
                ok = False

        if name == "la/wbh":
            note = (f"passes={stats.get('lookaheads', '?')} "
                    f"failed={stats.get('failed literals', '?')} "
                    f"autarky={stats.get('autarkies', '?')} "
                    f"learned={stats.get('learned binary', '?')}")

    if ok:
        print(f"ok   {os.path.basename(path):26s} {base:5s} {note}")
    return ok


if __name__ == "__main__":
    dpll, paths = rel(sys.argv[1]), sys.argv[2:]
    sys.exit(0 if all([check(dpll, p) for p in paths]) else 1)
