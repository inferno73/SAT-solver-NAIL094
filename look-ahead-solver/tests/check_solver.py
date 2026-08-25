# Check the DPLL solver against brute force
#
# For each instance:
#   - SAT/UNSAT must match an exhaustive search over all assignments
#   - when SAT, the reported model must satisfy every clause and assign every variable
#
# usage: python check_solver.py <dpll> <formula2cnf> <file> [<file> ...]

import itertools
import subprocess
import sys

MAX_BRUTE_VARS = 16


def parse_dimacs(text):
    nvars, clauses, cur = 0, [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p"):
            nvars = int(line.split()[2])
            continue
        if line.startswith("%"):
            break
        for tok in line.split():
            d = int(tok)
            if d == 0:
                clauses.append(cur)
                cur = []
            else:
                cur.append(d)
    return nvars, clauses


def brute_force(nvars, clauses):
    for bits in itertools.product([False, True], repeat=nvars):
        val = (None,) + bits
        if all(any(val[abs(l)] == (l > 0) for l in c) for c in clauses):
            return True
    return False


def cnf_of(path, formula2cnf):
    if path.endswith(".sat"):
        out = subprocess.run([formula2cnf, path], capture_output=True, text=True, check=True).stdout
    else:
        out = open(path).read()
    return parse_dimacs(out)


def check(dpll, formula2cnf, path):
    nvars, clauses = cnf_of(path, formula2cnf)
    r = subprocess.run([dpll, path], capture_output=True, text=True, check=True)
    lines = [l for l in r.stdout.splitlines() if not l.startswith("c")]

    verdict = lines[0].strip()
    if verdict not in ("SAT", "UNSAT"):
        print(f"FAIL {path}: no SAT/UNSAT verdict")
        return False

    if nvars <= MAX_BRUTE_VARS:
        want = "SAT" if brute_force(nvars, clauses) else "UNSAT"
        if verdict != want:
            print(f"FAIL {path}: solver said {verdict}, brute force says {want}")
            return False
        note = f"agrees with brute force over {nvars} vars"
    else:
        note = f"{nvars} vars, too large to brute force"

    if verdict == "SAT":
        vline = next((l for l in lines if l.startswith("v")), None)
        if vline is None:
            print(f"FAIL {path}: SAT but no model line")
            return False
        lits = [int(x) for x in vline.split()[1:]]
        if lits[-1] != 0:
            print(f"FAIL {path}: model line is not 0-terminated")
            return False
        lits = lits[:-1]

        if sorted(abs(l) for l in lits) != list(range(1, nvars + 1)):
            print(f"FAIL {path}: model does not assign each variable exactly once")
            return False
        if [abs(l) for l in lits] != sorted(abs(l) for l in lits):
            print(f"FAIL {path}: model is not sorted by variable index")
            return False

        val = {abs(l): (l > 0) for l in lits}
        for c in clauses:
            if not any(val[abs(l)] == (l > 0) for l in c):
                print(f"FAIL {path}: model falsifies clause {c}")
                return False
        note += ", model verified"

    print(f"ok   {path:34s} {verdict:5s} ({note})")
    return True


if __name__ == "__main__":
    dpll, formula2cnf, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    sys.exit(0 if all([check(dpll, formula2cnf, p) for p in paths]) else 1)
