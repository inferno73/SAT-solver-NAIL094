"""
Checks that watched literals and adjacency lists are interchangeable

Both must reach the same verdict on every instance, and must walk the same
search tree, which shows as identical decision and conflict counts
Unit propagation is confluent so the implied set is the same either way, but the
propagation count may still differ, because propagation stops at the first
conflict and the two engines reach it after enqueueing different numbers of
units, so that counter is reported rather than required to match

usage: python check_watched.py <dpll> <file> [<file> ...]
"""

import os
import subprocess
import sys

MUST_MATCH = ("decisions", "conflicts")


def rel(p):
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def run(dpll, path, watched):
    args = [dpll, "-q", path] if not watched else [dpll, "-q", "--watched", path]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    verdict, stats = None, {}
    for line in out.splitlines():
        s = line.strip()
        if s in ("SAT", "UNSAT"):
            verdict = s
        elif s.startswith("c "):
            k, _, v = s[2:].rpartition(" ")
            stats[k.strip()] = v.strip()
    return verdict, stats


def check(dpll, path):
    a_verdict, a = run(dpll, path, False)
    w_verdict, w = run(dpll, path, True)

    if a_verdict != w_verdict:
        print(f"FAIL {path}: adjacency={a_verdict} watched={w_verdict}")
        return False

    # a key absent from both outputs would compare None against None and pass
    # while checking nothing, so its presence is required first
    missing = [k for k in MUST_MATCH if k not in a or k not in w]
    if missing:
        print(f"FAIL {path}: the solver reports no {missing}, "
              f"so the search could not be compared")
        return False

    bad = [k for k in MUST_MATCH if a[k] != w[k]]
    if bad:
        print(f"FAIL {path}: same verdict but different search, {bad} differ")
        return False

    ac, wc = int(a["clauses checked"]), int(w["clauses checked"])
    ratio = f"{ac / wc:.2f}x" if wc else "n/a"
    print(f"ok   {os.path.basename(path):26s} {a_verdict:5s} "
          f"clauses checked {ac} vs {wc} ({ratio})")
    return True


if __name__ == "__main__":
    dpll, paths = rel(sys.argv[1]), sys.argv[2:]
    sys.exit(0 if all([check(dpll, p) for p in paths]) else 1)
