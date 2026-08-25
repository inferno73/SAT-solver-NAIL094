# Check the Tseitin encoding on instances too large to brute force
#
# Independently re-derives the gate numbering in Python and uses it two ways:
#
#   canonical extension  every gate given the value its definition forces, so all
#                        gate clauses must hold for any input assignment, and the
#                        root clause must hold exactly when the formula is true
#   no spurious models   whatever model dpll finds for the CNF must, projected
#                        onto the input variables, satisfy the original formula
#
# usage: python check_large.py <formula2cnf> <dpll> <file.sat> [<file.sat> ...]

import random
import subprocess
import sys

from check_encoding import collect_vars, evaluate, parse, parse_dimacs, tokenize

SAMPLES = 200


# Mirrors tseitin(): input variables numbered by first appearance, gates numbered
# in post-order starting after them, leaves reusing the input variable
def number(f, varids):
    gates = []
    counter = [len(varids)]

    def walk(node):
        if node[0] == "var":
            return varids[node[1]]
        if node[0] == "not":
            return -varids[node[1]]
        a = walk(node[1])
        b = walk(node[2])
        counter[0] += 1
        gates.append((counter[0], node[0], a, b))
        return counter[0]

    root = walk(f)
    return gates, root, counter[0]


def lit_value(lit, val):
    return val[abs(lit)] if lit > 0 else not val[abs(lit)]


def canonical(gates, assign):
    val = dict(assign)
    for g, kind, a, b in gates:
        if kind == "and":
            val[g] = lit_value(a, val) and lit_value(b, val)
        else:
            val[g] = lit_value(a, val) or lit_value(b, val)
    return val


def check(formula2cnf, dpll, path):
    src = open(path).read()
    f = parse(tokenize(src))
    invars = collect_vars(f, [])
    varids = {name: i + 1 for i, name in enumerate(invars)}
    gates, rootlit, nvars = number(f, varids)

    rng = random.Random(12345)
    ok = True

    for mode in ("--equiv", "--impl"):
        out = subprocess.run([formula2cnf, mode, path],
                             capture_output=True, text=True, check=True).stdout
        names, cnf_nvars, clauses = parse_dimacs(out)

        if cnf_nvars != nvars:
            print(f"FAIL {path} {mode}: {cnf_nvars} variables, expected {nvars}")
            return False
        if names != varids:
            print(f"FAIL {path} {mode}: input variable numbering disagrees")
            return False
        if len(clauses[-1]) != 1:
            print(f"FAIL {path} {mode}: last clause is not the root unit clause")
            return False
        if clauses[-1][0] != rootlit:
            print(f"FAIL {path} {mode}: root clause is {clauses[-1]}, expected [{rootlit}]")
            return False

        # all-false, all-true, then random input assignments
        patterns = [{v: False for v in varids.values()}, {v: True for v in varids.values()}]
        patterns += [{v: rng.random() < 0.5 for v in varids.values()} for _ in range(SAMPLES)]

        for assign in patterns:
            val = canonical(gates, assign)
            want = evaluate(f, {n: assign[varids[n]] for n in invars})

            for c in clauses[:-1]:
                if not any(lit_value(l, val) for l in c):
                    print(f"FAIL {path} {mode}: canonical extension falsifies gate clause {c}")
                    return False
            if lit_value(rootlit, val) != want:
                print(f"FAIL {path} {mode}: root gate is {lit_value(rootlit, val)}, "
                      f"formula is {want}")
                return False

        # whatever model the solver finds must project to a model of the formula
        r = subprocess.run([dpll, "--sat", mode, path],
                           capture_output=True, text=True, check=True)
        lines = [l for l in r.stdout.splitlines() if not l.startswith("c")]
        if lines[0].strip() != "SAT":
            print(f"FAIL {path} {mode}: solver reports {lines[0].strip()}")
            return False
        vline = next(l for l in lines if l.startswith("v"))
        model = [int(x) for x in vline.split()[1:-1]]
        mval = {abs(l): (l > 0) for l in model}
        if not evaluate(f, {n: mval[varids[n]] for n in invars}):
            print(f"FAIL {path} {mode}: model projects to a non-model of the formula")
            return False

    print(f"ok   {path:44s} {len(invars):4d} input vars, {len(gates):4d} gates")
    return ok


if __name__ == "__main__":
    formula2cnf, dpll, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    sys.exit(0 if all([check(formula2cnf, dpll, p) for p in paths]) else 1)
