"""
Cross-checks every number quoted in the DPLL report against the CSVs it came from

Guards against a report that has drifted from the measurements, which is easy
once a bench is re-run and the prose is not

usage: python check_report_dpll.py [results_dir]
"""

import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def claim(name, ok, detail=""):
    print(f"  {name:<50} {'OK' if ok else 'MISMATCH':<9} {detail}")
    if not ok:
        fails.append(f"{name}: {detail}")


def load(results, name):
    with open(os.path.join(results, name)) as f:
        return {r["instance"]: r for r in csv.DictReader(f)}


def main(results):
    R = load(results, "task2.csv")
    E = load(results, "task2_examples.csv")

    d = lambda i: float(R[i]["decisions"])
    hole = ["hole6", "hole7", "hole8", "hole9"]
    uf = sorted(k for k in R if k.startswith("uf50"))

    print("== pigeonhole growth ==")
    gf = [d(hole[i + 1]) / d(hole[i]) for i in range(3)]
    claim("growth factors 10.1, 11.5, 13.0",
          [round(x, 1) for x in gf] == [10.1, 11.5, 13.0],
          str([round(x, 2) for x in gf]))
    claim("the growth factor itself increases", all(gf[i] < gf[i + 1] for i in range(2)))
    claim("factor rises by about 1.4 per step",
          all(1.2 <= gf[i + 1] - gf[i] <= 1.6 for i in range(2)),
          str([round(gf[i + 1] - gf[i], 2) for i in range(2)]))
    claim("cpu 0.001 s to 1.635 s",
          float(R["hole6"]["cpu_seconds"]) == 0.001
          and float(R["hole9"]["cpu_seconds"]) == 1.635)
    claim("48 additional variables",
          float(R["hole9"]["variables"]) - float(R["hole6"]["variables"]) == 48)

    print("== across families ==")
    claim("ais12 265 vars against hole9 90",
          float(R["ais12"]["variables"]) == 265 and float(R["hole9"]["variables"]) == 90)
    claim("ais12 0.355 s against hole9 1.635 s",
          float(R["ais12"]["cpu_seconds"]) == 0.355
          and float(R["hole9"]["cpu_seconds"]) == 1.635)
    claim("four uf50 instances", len(uf) == 4, str(uf))
    spread = max(d(k) for k in uf) / min(d(k) for k in uf)
    claim("uf50 differ by a factor of 23 in decisions", round(spread) == 23, f"{spread:.2f}")
    claim("uf50 all 50 vars and 218 clauses at ratio 4.36",
          all(float(R[k]["clauses"]) == 218 and float(R[k]["variables"]) == 50 for k in uf),
          f"218/50 = {218 / 50:.2f}")

    print("== unit propagations per decision ==")
    per = lambda i: float(R[i]["unit_props"]) / d(i)
    ph = [per(h) for h in hole]
    # the report hedges with "stays near", so a little slack past the stated ends is allowed
    claim("pigeonhole near 4.5 to 5.5", 4.4 <= min(ph) and max(ph) <= 5.6,
          f"{min(ph):.2f}-{max(ph):.2f}")
    uu = [per(k) for k in uf]
    claim("uf50 near 5 to 7.5", 5.0 <= min(uu) and max(uu) <= 7.5,
          f"{min(uu):.2f}-{max(uu):.2f}")
    claim("ais climbs 9.0 on ais6 to 17.6 on ais12",
          abs(per("ais6") - 9.0) < 0.05 and abs(per("ais12") - 17.6) < 0.05,
          f"{per('ais6'):.2f} -> {per('ais12'):.2f}")
    aa = [per(k) for k in ("ais6", "ais8", "ais10", "ais12")]
    claim("ais increases with size", all(aa[i] < aa[i + 1] for i in range(3)),
          str([round(x, 1) for x in aa]))

    print("== example formulas ==")
    claim("all five satisfiable", all(r["verdict"] == "SAT" for r in E.values()),
          f"{len(E)} rows")
    withconf = sorted(k for k, r in E.items() if int(r["conflicts"]) > 0)
    claim("only nested_8 has conflicts, 31 of them",
          withconf == ["nested_8.sat"] and int(E["nested_8.sat"]["conflicts"]) == 31,
          str(withconf))

    print("== ais6 duplicate clauses ==")
    claim("ais6 reports 441 clauses", float(R["ais6"]["clauses"]) == 441)
    src = os.path.join(ROOT, "benchmarks", "ais", "ais6.cnf")
    if os.path.exists(src):
        seen, total = set(), 0
        with open(src) as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "pc%":
                    continue
                lits = tuple(sorted(int(x) for x in line.split()[:-1]))
                if lits:
                    total += 1
                    seen.add(lits)
        claim("the original file has 581 clauses, 140 repeated",
              total == 581 and total - len(seen) == 140,
              f"{total} clauses, {total - len(seen)} repeated, {len(seen)} distinct")

    print()
    print("FAILURES:", fails if fails else "none")
    return 1 if fails else 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
    sys.exit(main(out))
