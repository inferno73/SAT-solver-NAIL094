"""
Cross-checks every number quoted in the watched literals report against results/watched.csv

The report is built on ratios rather than raw counts, so each claimed range is
recomputed from the two engine columns instead of being read off the table

usage: python check_report_watched.py [results_dir]
"""

import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def claim(name, ok, detail=""):
    print(f"  {name:<44} {'OK' if ok else 'MISMATCH':<9} {detail}")
    if not ok:
        fails.append(f"{name}: {detail}")


def main(results):
    with open(os.path.join(results, "watched.csv")) as fh:
        rows = list(csv.DictReader(fh))

    f = lambda r, k: float(r[k])
    hole = [r for r in rows if r["instance"].startswith("hole")]
    ais = [r for r in rows if r["instance"].startswith("ais")]

    red = lambda g: [1 - f(r, "watched_checked") / f(r, "adjacency_checked") for r in g]
    slow = lambda g: [f(r, "watched_time") / f(r, "adjacency_time") for r in g]
    ratio = lambda g: [f(r, "checked_ratio") for r in g]

    print("== pigeonhole ==")
    r = red(hole)
    claim("checks only 2% fewer clauses", all(0.015 <= x <= 0.025 for x in r),
          f"{min(r) * 100:.1f}-{max(r) * 100:.1f}%")
    claim("ratio 1.02 on all four", all(round(x, 2) == 1.02 for x in ratio(hole)),
          str([round(x, 3) for x in ratio(hole)]))
    s = slow(hole)
    claim("takes 1.27 to 1.45 times as long",
          abs(min(s) - 1.27) < 0.01 and abs(max(s) - 1.45) < 0.01,
          f"{min(s):.3f}-{max(s):.3f}")
    b = [1 - f(r, "frac_len_gt2") for r in hole]
    claim("95 to 98% binary", round(min(b), 2) >= 0.95 and round(max(b), 2) <= 0.98,
          f"{min(b) * 100:.1f}-{max(b) * 100:.1f}%")

    print("== all interval series ==")
    r = red(ais)
    claim("checks 34 to 44% fewer clauses",
          round(min(r) * 100) >= 34 and round(max(r) * 100) <= 44,
          f"{min(r) * 100:.1f}-{max(r) * 100:.1f}%")
    q = ratio(ais)
    claim("ratio 1.51 on ais6 to 1.77 on ais12",
          abs(q[0] - 1.51) < 0.005 and abs(q[-1] - 1.77) < 0.005,
          f"{q[0]:.3f} -> {q[-1]:.3f}")
    claim("the ratio rises with instance size",
          all(q[i] < q[i + 1] for i in range(len(q) - 1)), str([round(x, 3) for x in q]))
    sv = [1 - x for x in slow(ais)]
    claim("saves 11 to 29% of the running time",
          round(min(sv) * 100) >= 11 and round(max(sv) * 100) <= 29,
          f"{min(sv) * 100:.1f}-{max(sv) * 100:.1f}%")
    g2 = [f(r, "frac_len_gt2") for r in ais]
    claim("26 to 28% of clauses longer than two",
          round(min(g2), 2) >= 0.26 and round(max(g2), 2) <= 0.28,
          f"{min(g2) * 100:.1f}-{max(g2) * 100:.1f}%")

    print("== both families ==")
    claim("identical decisions and conflicts",
          all(r["adjacency_decisions"] == r["watched_decisions"]
              and r["adjacency_conflicts"] == r["watched_conflicts"] for r in rows),
          f"{len(rows)} instances")
    claim("same_tree set on every row", all(r["same_tree"] == "True" for r in rows))

    print()
    print("FAILURES:", fails if fails else "none")
    return 1 if fails else 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
    sys.exit(main(out))
