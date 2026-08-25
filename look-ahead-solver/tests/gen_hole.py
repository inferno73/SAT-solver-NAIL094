# Pigeonhole instances: n+1 pigeons into n holes, always unsatisfiable
#
# Variable (p,h) -> p*n + h + 1, for pigeon p in 0..n and hole h in 0..n-1
# Clauses: each pigeon sits in some hole, no two pigeons share a hole
#
# usage: python gen_hole.py <n> [output]

import sys


def hole(n):
    def v(p, h):
        return p * n + h + 1

    clauses = [[v(p, h) for h in range(n)] for p in range(n + 1)]
    for h in range(n):
        for p in range(n + 1):
            for q in range(p + 1, n + 1):
                clauses.append([-v(p, h), -v(q, h)])
    return n * (n + 1), clauses


def write(out, n, nvars, clauses):
    out.write(f"c pigeonhole: {n + 1} pigeons into {n} holes, unsatisfiable\n")
    out.write(f"p cnf {nvars} {len(clauses)}\n")
    for c in clauses:
        out.write(" ".join(str(l) for l in c) + " 0\n")


if __name__ == "__main__":
    n = int(sys.argv[1])
    nvars, clauses = hole(n)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as f:
            write(f, n, nvars, clauses)
    else:
        write(sys.stdout, n, nvars, clauses)
