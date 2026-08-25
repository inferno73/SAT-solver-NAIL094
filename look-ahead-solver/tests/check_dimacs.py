# Conformance check against the DIMACS rules stated on the task page
#
#   header "p cnf nbvar nbclauses", nbvar is the maximum variable index and
#   nbclauses the exact number of clauses
#   each clause is a sequence of distinct non-null numbers in [-nbvar, nbvar]
#   ending with 0, and must not contain the opposite literals i and -i
#
# Also checks the comment block documents the input variables, the auxiliary
# gate variables and the root, which the task page requires
#
# usage: python check_dimacs.py <formula2cnf> <file.sat> [<file.sat> ...]

import subprocess
import sys


def validate(text, label):
    problems = []
    nbvar = nbclauses = None
    comments = []
    lits = []

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("c"):
            comments.append(s)
        elif s.startswith("p"):
            parts = s.split()
            if len(parts) != 4 or parts[1] != "cnf":
                problems.append(f"malformed header: {s!r}")
            else:
                nbvar, nbclauses = int(parts[2]), int(parts[3])
        else:
            lits.extend(int(t) for t in s.split())

    if nbvar is None:
        return ["missing 'p cnf' header"]

    clauses, cur = [], []
    for v in lits:
        if v == 0:
            clauses.append(cur)
            cur = []
        else:
            cur.append(v)
    if cur:
        problems.append("last clause is not terminated by 0")

    if len(clauses) != nbclauses:
        problems.append(f"header says {nbclauses} clauses, found {len(clauses)}")

    used = {abs(l) for c in clauses for l in c}
    if used and max(used) > nbvar:
        problems.append(f"literal on variable {max(used)} exceeds nbvar={nbvar}")

    for i, c in enumerate(clauses):
        if len(set(c)) != len(c):
            dup = sorted({l for l in c if c.count(l) > 1})
            problems.append(f"clause {i} has repeated literals {dup}: {c}")
        opp = sorted({abs(l) for l in c if -l in c})
        if opp:
            problems.append(f"clause {i} has opposite literals on {opp}: {c}")

    joined = "\n".join(comments)
    for want in ("input variables", "auxiliary", "root"):
        if want not in joined:
            problems.append(f"comment block does not mention {want!r}")

    return problems


def check(exe, path):
    ok = True
    for mode in ("--equiv", "--impl"):
        out = subprocess.run([exe, mode, path], capture_output=True, text=True,
                             check=True).stdout
        problems = validate(out, f"{path} {mode}")
        if problems:
            ok = False
            for p in problems:
                print(f"FAIL {path} {mode}: {p}")
    if ok:
        print(f"ok   {path}")
    return ok


if __name__ == "__main__":
    exe, paths = sys.argv[1], sys.argv[2:]
    sys.exit(0 if all([check(exe, p) for p in paths]) else 1)
