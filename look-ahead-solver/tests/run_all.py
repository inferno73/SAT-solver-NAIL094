# Runs every check against a given pair of binaries
#
# Both `make test` and `make test-linux` go through this, so the Windows and
# Linux runs cannot drift apart. Written in Python rather than shell because
# Windows make has no sh
#
# usage: python tests/run_all.py <formula2cnf> <dpll>

import glob
import os
import subprocess
import sys


def rel(p):
    # Windows python will not spawn a bare relative path like bin/dpll.exe
    return p if os.path.isabs(p) or p.startswith("./") else "./" + p


def main(f2c, dpll):
    f2c, dpll = rel(f2c), rel(dpll)
    all_sat = sorted(glob.glob("tests/*.sat"))
    good_sat = [p for p in all_sat if not os.path.basename(p).startswith("bad-")]
    examples = sorted(glob.glob("task1-example-Input-Files/*.sat"))
    cnf = sorted(glob.glob("tests/cnf/*.cnf"))
    py = sys.executable

    steps = [
        ["tests/check_cli.py", f2c, dpll],
        ["tests/check_encoding.py", f2c, *all_sat],
        ["tests/check_dimacs.py", f2c, *good_sat, *examples],
        ["tests/check_large.py", f2c, dpll, *examples],
        ["tests/check_solver.py", dpll, f2c, *cnf, *good_sat],
        ["tests/check_watched.py", dpll, *cnf, *good_sat],
        ["tests/check_lookahead.py", dpll, *cnf, *good_sat],
        ["tests/fuzz.py", dpll, "400", "1"],
        ["tests/fuzz.py", dpll, "400", "2", "--watched"],
        ["tests/fuzz.py", dpll, "400", "6", "--counters"],
        ["tests/fuzz.py", dpll, "250", "3", "--lookahead", "--heuristic=crh"],
        ["tests/fuzz.py", dpll, "250", "4", "--lookahead", "--heuristic=wbh"],
        ["tests/fuzz.py", dpll, "250", "5", "--lookahead", "--heuristic=bsh"],
    ]

    for step in steps:
        print(f"\n===== {os.path.basename(step[0])} =====", flush=True)
        r = subprocess.run([py, *step])
        if r.returncode != 0:
            print(f"\n{step[0]} FAILED", file=sys.stderr)
            return r.returncode
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
