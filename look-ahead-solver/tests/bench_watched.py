"""
Compares the two propagation engines on clauses checked and running time

Also records the clause width profile, since that is what decides whether
watched literals can save anything: a watch can only move to a literal the
clause actually has, so a binary clause offers nowhere to move it

usage: python bench_watched.py <dpll> [--repeat N] [--timeout S] [--csv out.csv] <file> ...
"""

import csv
import os
import statistics
import subprocess
import sys


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def widths(path):
    lengths, cur = [], 0
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s[0] in "cp":
                continue
            if s[0] == "%":
                break
            for tok in s.split():
                if int(tok) == 0:
                    lengths.append(cur)
                    cur = 0
                else:
                    cur += 1
    if not lengths:
        return 0, 0
    return statistics.mean(lengths), sum(1 for l in lengths if l > 2) / len(lengths)


def run(dpll, path, watched, timeout):
    args = [dpll, "-q", path] if not watched else [dpll, "-q", "--watched", path]
    try:
        out = subprocess.run(args, capture_output=True, text=True, check=True,
                             timeout=timeout).stdout
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
        mean_len, long_frac = widths(path)
        row = {"instance": os.path.basename(path).replace(".cnf", ""),
               "mean_len": round(mean_len, 2), "frac_len_gt2": round(long_frac, 3)}

        for name, watched in (("adjacency", False), ("watched", True)):
            best, rec = None, None
            for _ in range(repeat):
                r = run(dpll, path, watched, timeout)
                if r is None:
                    best, rec = None, None
                    break
                rec = rec or r
                t = float(r["wall seconds"])
                best = t if best is None else min(best, t)
            if rec is None:
                row[f"{name}_time"] = None
                row["verdict"] = "TIMEOUT"
                continue
            row["verdict"] = rec["verdict"]
            row["variables"] = int(rec["variables"])
            row["clauses"] = int(rec["clauses"])
            row[f"{name}_decisions"] = int(rec["decisions"])
            row[f"{name}_conflicts"] = int(rec["conflicts"])
            row[f"{name}_checked"] = int(rec["clauses checked"])
            row[f"{name}_time"] = best

        a, w = row.get("adjacency_checked"), row.get("watched_checked")
        row["checked_ratio"] = round(a / w, 3) if a and w else None
        at, wt = row.get("adjacency_time"), row.get("watched_time")
        row["time_ratio"] = round(at / wt, 3) if at and wt else None
        row["same_tree"] = (row.get("adjacency_decisions") == row.get("watched_decisions")
                            and row.get("adjacency_conflicts") == row.get("watched_conflicts"))
        rows.append(row)
        print(f"  done {row['instance']}", file=sys.stderr)
    return rows


def table(rows):
    hdr = ("instance", "vars", "clauses", "len", ">2", "result",
           "adj checked", "wat checked", "ratio", "adj s", "wat s", "speedup")
    w = (11, 5, 8, 5, 5, 6, 12, 12, 6, 9, 9, 8)
    print("  ".join(h.rjust(x) for h, x in zip(hdr, w)))
    print("-" * (sum(w) + 2 * len(w)))
    for r in rows:
        def g(k, fmt="{}"):
            v = r.get(k)
            return "-" if v is None else fmt.format(v)
        cells = (r["instance"], g("variables"), g("clauses"),
                 g("mean_len", "{:.2f}"), g("frac_len_gt2", "{:.2f}"), r["verdict"],
                 g("adjacency_checked"), g("watched_checked"),
                 g("checked_ratio", "{:.2f}"), g("adjacency_time", "{:.5f}"),
                 g("watched_time", "{:.5f}"), g("time_ratio", "{:.2f}"))
        print("  ".join(c.rjust(x) for c, x in zip(cells, w)))
    bad = [r["instance"] for r in rows if not r.get("same_tree")]
    print("\nsearch trees identical for every instance" if not bad
          else f"\nWARNING search differs on: {bad}")


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
