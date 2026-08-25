"""
Compares the look-ahead solver against plain DPLL, and the three difference
heuristics against each other

Look-ahead trades a large per-node cost for a smaller search tree, so the two
numbers that matter are decisions, which measure the tree, and time, which says
what the tree cost

The counters column is a control rather than a solver anyone would run: eager
counters doing plain branching, so its tree is identical to plain DPLL and the
only thing that differs is the data structure

usage: python bench_lookahead.py <dpll> [--repeat N] [--timeout S] [--csv out.csv] <file> ...
"""

import csv
import os
import subprocess
import sys

CONFIGS = [
    ("dpll", []),
    ("counters", ["--counters"]),
    ("crh", ["--lookahead", "--heuristic=crh"]),
    ("wbh", ["--lookahead", "--heuristic=wbh"]),
    ("bsh", ["--lookahead", "--heuristic=bsh"]),
    ("bare", ["--lookahead", "--heuristic=wbh", "--no-learning", "--no-autarky"]),
]

EXTRA = ("lookaheads", "probes", "failed literals", "autarkies", "learned binary")


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def run(dpll, args, path, timeout):
    try:
        out = subprocess.run([dpll, "-q", *args, path], capture_output=True,
                             text=True, check=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        return None
    rec = {}
    for line in out.splitlines():
        s = line.strip()
        if s in ("SAT", "UNSAT"):
            rec["verdict"] = s
        elif s.startswith("c "):
            k, _, v = s[2:].rpartition(" ")
            rec[k.strip()] = v.strip()
    return rec


def bench(dpll, paths, repeat, timeout):
    rows = []
    for path in paths:
        row = {"instance": os.path.basename(path).replace(".cnf", "")}
        for name, args in CONFIGS:
            best, rec = None, None
            for _ in range(repeat):
                r = run(dpll, args, path, timeout)
                if r is None:
                    best, rec = None, None
                    break
                rec = rec or r
                t = float(r["wall seconds"])
                best = t if best is None else min(best, t)
            if rec is None:
                row[f"{name}_time"] = None
                row.setdefault("verdict", "TIMEOUT")
                continue
            row["verdict"] = rec["verdict"]
            row["variables"] = int(rec["variables"])
            row["clauses"] = int(rec["clauses"])
            row[f"{name}_decisions"] = int(rec["decisions"])
            row[f"{name}_time"] = best
            if name == "wbh":
                for k in EXTRA:
                    if k in rec:
                        row[k.replace(" ", "_")] = int(rec[k])
        rows.append(row)
        print(f"  done {row['instance']}", file=sys.stderr)
    return rows


def table(rows):
    names = [n for n, _ in CONFIGS]
    print(f"{'instance':<11} {'vars':>5} {'result':>6} "
          + " ".join(f"{n + ' dec':>12}" for n in names))
    print("-" * (25 + 13 * len(names)))
    for r in rows:
        cells = []
        for n in names:
            v = r.get(f"{n}_decisions")
            cells.append("timeout" if r.get(f"{n}_time") is None else f"{v:,}")
        print(f"{r['instance']:<11} {r.get('variables', 0):>5} {r.get('verdict', '?'):>6} "
              + " ".join(f"{c:>12}" for c in cells))

    print()
    print(f"{'instance':<11} {'result':>6} " + " ".join(f"{n + ' s':>12}" for n in names))
    print("-" * (19 + 13 * len(names)))
    for r in rows:
        cells = []
        for n in names:
            t = r.get(f"{n}_time")
            cells.append("timeout" if t is None else f"{t:.4f}")
        print(f"{r['instance']:<11} {r.get('verdict', '?'):>6} "
              + " ".join(f"{c:>12}" for c in cells))


if __name__ == "__main__":
    args = sys.argv[1:]
    dpll = rel(args.pop(0))
    repeat, timeout, out_csv, paths = 3, 300.0, None, []
    i = 0
    while i < len(args):
        if args[i] == "--repeat":
            repeat = int(args[i + 1]); i += 2
        elif args[i] == "--timeout":
            timeout = float(args[i + 1]); i += 2
        elif args[i] == "--csv":
            out_csv = args[i + 1]; i += 2
        else:
            paths.append(args[i]); i += 1

    rows = bench(dpll, paths, repeat, timeout)
    table(rows)
    if out_csv:
        keys = sorted({k for r in rows for k in r})
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out_csv}", file=sys.stderr)
