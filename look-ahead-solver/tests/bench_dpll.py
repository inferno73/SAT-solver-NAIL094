# Runs dpll over a set of instances and records what the task asks to report:
# CPU time, decisions, unit propagation steps
#
# Each instance is run several times and the fastest kept, since wall time on
# the small instances is dominated by noise
#
# usage: python bench_dpll.py <dpll> [--repeat N] [--timeout S] [--csv out.csv] <file> ...

import csv
import os
import subprocess
import sys

KEYS = ("variables", "clauses", "decisions", "unit props", "conflicts",
        "clauses checked")


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def run(dpll, path, timeout):
    try:
        out = subprocess.run([dpll, "-q", path], capture_output=True, text=True,
                             check=True, timeout=timeout).stdout
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
        best_wall = best_cpu = None
        rec = None
        for _ in range(repeat):
            r = run(dpll, path, timeout)
            if r is None:
                rec = None
                break
            rec = rec or r
            w, c = float(r["wall seconds"]), float(r["cpu seconds"])
            best_wall = w if best_wall is None else min(best_wall, w)
            best_cpu = c if best_cpu is None else min(best_cpu, c)

        row = {"instance": os.path.basename(path).replace(".cnf", "")}
        if rec is None:
            row["verdict"] = "TIMEOUT"
        else:
            row["verdict"] = rec["verdict"]
            row["vars"] = int(rec["variables"])
            for k in KEYS:
                row[k.replace(" ", "_")] = int(rec[k])
            row["cpu_seconds"] = best_cpu
            row["wall_seconds"] = best_wall
        rows.append(row)
        print(f"  done {row['instance']}", file=sys.stderr)
    return rows


def table(rows):
    hdr = ("instance", "vars", "clauses", "result", "decisions", "unit props",
           "conflicts", "cpu s", "wall s")
    w = (12, 6, 8, 7, 12, 12, 11, 9, 10)
    print("  ".join(h.rjust(x) for h, x in zip(hdr, w)))
    print("-" * (sum(w) + 2 * len(w)))
    for r in rows:
        def g(k, fmt="{}"):
            v = r.get(k)
            return "-" if v is None else fmt.format(v)
        cells = (r["instance"], g("variables"), g("clauses"), r["verdict"],
                 g("decisions"), g("unit_props"), g("conflicts"),
                 g("cpu_seconds", "{:.4f}"), g("wall_seconds", "{:.5f}"))
        print("  ".join(c.rjust(x) for c, x in zip(cells, w)))


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
            wr = csv.DictWriter(f, fieldnames=keys)
            wr.writeheader()
            wr.writerows(rows)
        print(f"\nwrote {out_csv}", file=sys.stderr)
