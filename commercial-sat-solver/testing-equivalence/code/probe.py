"""Find which benchmark instances a plain SAT call can actually solve

The Tseitin approach is a single unbounded call, so its cost is governed by how
hard the instance itself is. Each instance is solved in a child process with a
hard cap, since a running call cannot be stopped from inside the process.

Writes hardness.csv next to this file.

usage: python probe.py [cap_seconds]
"""

from __future__ import annotations

import csv
import multiprocessing as mp
import os
import sys
import time

from bench import BENCH_DIR, families, instances
from equivalence import read_dimacs

CAP = 10.0


def _solve(path: str, queue) -> None:
    from pysat.solvers import Solver

    f = read_dimacs(path)
    t0 = time.perf_counter()
    with Solver(name="cadical153", bootstrap_with=f.clauses) as s:
        sat = s.solve()
    queue.put({"sat": bool(sat), "seconds": time.perf_counter() - t0})


def probe(path: str, cap: float = CAP) -> dict:
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=_solve, args=(path, queue))
    proc.start()
    proc.join(cap)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return {"sat": None, "seconds": None, "hard": True}
    try:
        out = queue.get(timeout=5)
    except Exception:
        return {"sat": None, "seconds": None, "hard": True}
    out["hard"] = False
    return out


def main(cap: float) -> None:
    rows = []
    for fam in families(include_excluded=True):
        for path in instances(fam):
            f = read_dimacs(path)
            r = probe(path, cap)
            row = {
                "family": fam,
                "instance": os.path.basename(path),
                "n_vars": f.n_vars,
                "n_clauses": f.n_clauses,
                "sat": r["sat"],
                "seconds": None if r["seconds"] is None else round(r["seconds"], 3),
                "hard": r["hard"],
            }
            rows.append(row)
            mark = "HARD" if r["hard"] else f"{r['seconds']:.3f}s {r['sat']}"
            print(f"  {fam:<14} {row['instance']:<24} "
                  f"{f.n_clauses:>7} clauses  {mark}", flush=True)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hardness.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    hard = sorted({r["family"] for r in rows if r["hard"]})
    print(f"\n{len(rows)} instances, {sum(r['hard'] for r in rows)} not solved within {cap:.0f}s")
    print("families containing an unsolved instance:", ", ".join(hard) if hard else "none")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else CAP)
