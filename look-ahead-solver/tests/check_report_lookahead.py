"""
Cross-checks every number quoted in the look-ahead report

Covers results/lookahead.csv for the two tables and the paragraphs that
decompose the pigeonhole slowdown, and results/random.csv for the 300 instance
heuristic comparison, whose confidence intervals are recomputed rather than
taken on trust

usage: python check_report_lookahead.py [results_dir]
"""

import csv
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def claim(name, ok, detail=""):
    print(f"  {name:<52} {'OK' if ok else 'MISMATCH':<9} {detail}")
    if not ok:
        fails.append(f"{name}: {detail}")


def paired_ci(a, b):
    """95% interval for the mean paired difference, normal approximation"""
    diff = [x - y for x, y in zip(a, b)]
    m = statistics.mean(diff)
    se = statistics.stdev(diff) / math.sqrt(len(diff))
    return m - 1.96 * se, m + 1.96 * se


def main(results):
    with open(os.path.join(results, "lookahead.csv")) as fh:
        rows = {r["instance"]: r for r in csv.DictReader(fh)}
    g = lambda inst, col: float(rows[inst][col])
    hole = ["hole6", "hole7", "hole8"]

    print("== decisions ==")
    red = [g(h, "dpll_decisions") / g(h, "crh_decisions") for h in hole]
    claim("pigeonhole reduction factor 14 to 28",
          round(min(red)) == 14 and round(max(red)) == 28,
          f"{min(red):.2f}-{max(red):.2f}")
    claim("ais12 falls from 192,780 to 6 under WBH",
          g("ais12", "dpll_decisions") == 192780 and g("ais12", "wbh_decisions") == 6)
    claim("the three agree on pigeonhole at 478 / 3358 / 26878",
          all(g(h, "crh_decisions") == g(h, "wbh_decisions") == g(h, "bsh_decisions")
              for h in hole)
          and [g(h, "crh_decisions") for h in hole] == [478, 3358, 26878])
    claim("ais12 WBH and BSH 6 against CRH 29",
          g("ais12", "wbh_decisions") == 6 and g("ais12", "bsh_decisions") == 6
          and g("ais12", "crh_decisions") == 29)
    claim("the counters column repeats plain DPLL on every row",
          all(r["counters_decisions"] == r["dpll_decisions"] for r in rows.values()),
          f"{len(rows)} rows")
    claim("hole8 bare 121,182 against 26,878, more than four times",
          g("hole8", "bare_decisions") == 121182
          and g("hole8", "bare_decisions") / g("hole8", "wbh_decisions") > 4,
          f"{g('hole8', 'bare_decisions') / g('hole8', 'wbh_decisions'):.2f}x")

    print("== the hole8 decomposition ==")
    plain, cnt, crh = (g("hole8", "dpll_time"), g("hole8", "counters_time"),
                       g("hole8", "crh_time"))
    claim("hole8 CRH 0.4931 against plain 0.1192",
          abs(crh - 0.4931) < 5e-5 and abs(plain - 0.1192) < 5e-5)
    claim("the engine alone is a factor of 1.35", abs(cnt / plain - 1.35) < 0.005,
          f"{cnt / plain:.4f}")
    claim("look-ahead on the engine is a factor of 3.06", abs(crh / cnt - 3.06) < 0.005,
          f"{crh / cnt:.4f}")
    claim("together they give 4.14", abs(crh / plain - 4.14) < 0.005, f"{crh / plain:.4f}")
    claim("look-ahead adds 0.374 s", abs((crh - plain) - 0.374) < 0.0005,
          f"{crh - plain:.4f}")
    claim("of which the counters are 0.042 s", abs((cnt - plain) - 0.042) < 0.0005,
          f"{cnt - plain:.4f}")
    claim("and the probing 0.332 s", abs((crh - cnt) - 0.332) < 0.0005, f"{crh - cnt:.4f}")
    claim("bookkeeping is 11% of the excess",
          round((cnt - plain) / (crh - plain) * 100) == 11,
          f"{(cnt - plain) / (crh - plain) * 100:.1f}%")
    claim("probing is the remaining 89%",
          round((crh - cnt) / (crh - plain) * 100) == 89,
          f"{(crh - cnt) / (crh - plain) * 100:.1f}%")

    print("== all interval series times ==")
    p12, c12, w12 = (g("ais12", "dpll_time"), g("ais12", "counters_time"),
                     g("ais12", "wbh_time"))
    claim("ais12 0.3563 to 0.0204 under WBH",
          abs(p12 - 0.3563) < 5e-5 and abs(w12 - 0.0204) < 5e-5)
    claim("ais12 CRH 0.1835", abs(g("ais12", "crh_time") - 0.1835) < 5e-5)
    claim("the engine is a factor of 1.04 on ais12", abs(c12 / p12 - 1.04) < 0.005,
          f"{c12 / p12:.4f}")
    # the sentence says on top of the engine, so the engine is the baseline here
    claim("look-ahead gains a factor of 18 on top of it", round(c12 / w12) == 18,
          f"against engine {c12 / w12:.2f}, against plain {p12 / w12:.2f}")
    claim("hole8 bare 1.0118 against 0.5440",
          abs(g("hole8", "bare_time") - 1.0118) < 5e-5
          and abs(g("hole8", "wbh_time") - 0.5440) < 5e-5)
    claim("ais12 is faster bare, 0.0115 against 0.0204",
          abs(g("ais12", "bare_time") - 0.0115) < 5e-5 and abs(w12 - 0.0204) < 5e-5)

    cols = ["dpll_time", "counters_time", "crh_time", "wbh_time", "bsh_time", "bare_time"]
    under = sorted(i for i in rows if all(g(i, c) < 0.002 for c in cols))
    claim("two instances run under two milliseconds throughout",
          under == ["ais6", "uf50-01"], str(under))

    print("== the 300 instance random sweep ==")
    with open(os.path.join(results, "random.csv")) as fh:
        rnd = list(csv.DictReader(fh))
    col = lambda k, grp=None: [float(r[f"{k}_decisions"]) for r in (grp or rnd)]
    means = {k: statistics.mean(col(k)) for k in ("dpll", "crh", "wbh", "bsh")}

    claim("300 instances", len(rnd) == 300, str(len(rnd)))
    claim("plain DPLL mean 418.2", abs(means["dpll"] - 418.2) < 0.05, f"{means['dpll']:.2f}")
    for k, want in (("crh", 4.11), ("wbh", 4.07), ("bsh", 4.30)):
        claim(f"{k.upper()} mean {want}", abs(means[k] - want) < 0.005, f"{means[k]:.4f}")

    straddle = True
    for x, y in (("crh", "wbh"), ("crh", "bsh"), ("wbh", "bsh")):
        lo, hi = paired_ci(col(x), col(y))
        ok = lo <= 0 <= hi
        straddle &= ok
        print(f"    {x} - {y:<4} [{lo:+.3f}, {hi:+.3f}]  "
              f"{'straddles zero' if ok else 'EXCLUDES zero'}")
    claim("every pairwise interval straddles zero", straddle)

    m100 = {k: statistics.mean(col(k, rnd[:100])) for k in ("crh", "wbh", "bsh")}
    claim("BSH led over the first hundred", min(m100, key=m100.get) == "bsh",
          ", ".join(f"{k}={v:.3f}" for k, v in m100.items()))
    m300 = {k: means[k] for k in ("crh", "wbh", "bsh")}
    claim("BSH trails over three hundred", max(m300, key=m300.get) == "bsh",
          ", ".join(f"{k}={v:.3f}" for k, v in m300.items()))

    print()
    print("FAILURES:", fails if fails else "none")
    return 1 if fails else 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
    sys.exit(main(out))
