# Brute-force check that formula2cnf preserves the models of the input formula
#
# For every assignment of the input variables:
#   formula is true  <=>  the CNF has a satisfying extension over the gate variables
#
# This is checked for both encoding modes. Implication-only is usually described
# as merely equisatisfiable, but the input is NNF, so forcing the root gate true
# propagates down to input literals and a false formula admits no extension at
# all; the exact criterion holds and is the stronger thing to test
#
# Files named bad-*.sat must instead be rejected with a nonzero exit code
#
# usage: python check_encoding.py <formula2cnf> <file.sat> [<file.sat> ...]

import itertools
import os
import subprocess
import sys


def tokenize(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "()":
            out.append(c)
            i += 1
        elif c.isalpha():
            j = i
            while j < len(s) and s[j].isalnum():
                j += 1
            out.append(s[i:j])
            i = j
        else:
            raise ValueError(f"bad char {c!r}")
    return out


def parse(toks):
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def formula():
        t = take()
        if t != "(":
            return ("var", t)
        op = take()
        if op == "not":
            v = take()
            assert take() == ")"
            return ("not", v)
        a = formula()
        b = formula()
        assert take() == ")"
        return (op, a, b)

    f = formula()
    assert pos[0] == len(toks)
    return f


def evaluate(f, assign):
    k = f[0]
    if k == "var":
        return assign[f[1]]
    if k == "not":
        return not assign[f[1]]
    if k == "and":
        return evaluate(f[1], assign) and evaluate(f[2], assign)
    return evaluate(f[1], assign) or evaluate(f[2], assign)


def collect_vars(f, acc):
    if f[0] in ("var", "not"):
        if f[1] not in acc:
            acc.append(f[1])
    else:
        collect_vars(f[1], acc)
        collect_vars(f[2], acc)
    return acc


def parse_dimacs(text):
    names, nvars, clauses = {}, 0, []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("c"):
            parts = line.split()
            if len(parts) == 3 and parts[1].isdigit():
                names[parts[2]] = int(parts[1])
        elif line.startswith("p"):
            nvars = int(line.split()[2])
        elif line:
            lits = [int(x) for x in line.split()]
            assert lits[-1] == 0
            clauses.append(lits[:-1])
    return names, nvars, clauses


def cnf_has_extension(nvars, clauses, fixed):
    free = [v for v in range(1, nvars + 1) if v not in fixed]
    for bits in itertools.product([False, True], repeat=len(free)):
        val = dict(fixed)
        val.update(zip(free, bits))
        if all(any(val[abs(l)] == (l > 0) for l in c) for c in clauses):
            return True
    return False


def check_rejected(exe, path):
    r = subprocess.run([exe, path], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"FAIL {path}: accepted, expected a parse error")
        return False
    print(f"ok   {path}  (rejected: {r.stderr.strip()})")
    return True


def check(exe, path):
    if os.path.basename(path).startswith("bad-"):
        return check_rejected(exe, path)

    src = open(path).read()
    f = parse(tokenize(src))
    invars = collect_vars(f, [])

    ok = True
    for mode in ("--equiv", "--impl"):
        out = subprocess.run([exe, mode, path], capture_output=True, text=True, check=True).stdout
        names, nvars, clauses = parse_dimacs(out)
        for name in invars:
            assert name in names, f"{path}: variable {name} missing from the comment block"

        for bits in itertools.product([False, True], repeat=len(invars)):
            assign = dict(zip(invars, bits))
            want = evaluate(f, assign)
            fixed = {names[n]: assign[n] for n in invars}
            got = cnf_has_extension(nvars, clauses, fixed)
            if want != got:
                print(f"FAIL {path} {mode} {assign}: formula={want} cnf={got}")
                ok = False
    print(("ok   " if ok else "FAIL ") + path + f"  ({len(invars)} input vars)")
    return ok


if __name__ == "__main__":
    exe, paths = sys.argv[1], sys.argv[2:]
    sys.exit(0 if all([check(exe, p) for p in paths]) else 1)
