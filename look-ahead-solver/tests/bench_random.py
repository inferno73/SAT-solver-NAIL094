"""
Separates the three difference heuristics on uniform random 3-SAT

The structured families are too few and too symmetric to tell the heuristics
apart: pigeonhole ties all three exactly. Random instances at the phase
transition do separate them, but one instance says nothing, so this aggregates
over a sample and reports the mean

Times are not measured here: a uf50 solve is about a millisecond, which process
startup dominates. Decisions are exact and deterministic, so they are the
statistic that carries

usage: python bench_random.py <dpll> <count> [--csv out.csv]
"""

import csv
import glob
import os
import subprocess
import sys

CONFIGS = [
    ("dpll", []),
    ("crh", ["--lookahead", "--heuristic=crh"]),
    ("wbh", ["--lookahead", "--heuristic=wbh"]),
    ("bsh", ["--lookahead", "--heuristic=bsh"]),
]


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def decisions(dpll, args, path):
    out = subprocess.run([dpll, "-q", *args, path], capture_output=True,
                         text=True, check=True).stdout
    verdict, dec = None, None
    for line in out.splitlines():
        s = line.strip()
        if s in ("SAT", "UNSAT"):
            verdict = s
        elif s.startswith("c decisions"):
            dec = int(s.split()[-1])
    return verdict, dec


def main(dpll, count, out_csv):
    paths = sorted(glob.glob("benchmarks/rnd3sat/*.cnf"))[:count]
    totals = {n: 0 for n, _ in CONFIGS}
    wins = {n: 0 for n, _ in CONFIGS}
    rows = []

    for path in paths:
        row = {"instance": os.path.basename(path).replace(".cnf", "")}
        got = {}
        base = None
        for name, args in CONFIGS:
            verdict, dec = decisions(dpll, args, path)
            if base is None:
                base = verdict
            elif verdict != base:
                print(f"FAIL {path}: {name} says {verdict}, dpll said {base}")
                return 1
            got[name] = dec
            totals[name] += dec
            row[f"{name}_decisions"] = dec
        row["verdict"] = base
        rows.append(row)

        best = min(got[n] for n, _ in CONFIGS if n != "dpll")
        for n, _ in CONFIGS:
            if n != "dpll" and got[n] == best:
                wins[n] += 1

    n = len(paths)
    print(f"{n} uniform random 3-SAT instances, 50 variables, 218 clauses\n")
    print(f"{'config':10s} {'total':>10s} {'mean':>9s} {'best or tied':>13s}")
    print("-" * 45)
    for name, _ in CONFIGS:
        w = "--" if name == "dpll" else f"{wins[name]} of {n}"
        print(f"{name:10s} {totals[name]:10,d} {totals[name] / n:9.1f} {w:>13s}")

    if out_csv:
        with open(out_csv, "w", newline="") as f:
            keys = ["instance", "verdict"] + [f"{n}_decisions" for n, _ in CONFIGS]
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    dpll, count = rel(args[0]), int(args[1])
    out_csv = args[args.index("--csv") + 1] if "--csv" in args else None
    sys.exit(main(dpll, count, out_csv))
