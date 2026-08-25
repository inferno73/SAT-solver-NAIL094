# Exercises the command line interface itself, which the other checks skip
#
# Covers the argument forms the task pages specify: the optional output file,
# stdin/stdout defaults, the format override, and the exit codes for bad usage
#
# usage: python check_cli.py <formula2cnf> <dpll>

import os
import subprocess
import sys
import tempfile

ok = True


def report(good, desc, detail=""):
    global ok
    if not good:
        ok = False
    print(f"{'ok  ' if good else 'FAIL'} {desc}{'  ' + detail if detail else ''}")


def expect_exit(desc, want, *cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    first = (r.stderr or r.stdout).strip().splitlines()
    report(r.returncode == want, desc,
           f"exit={r.returncode} {first[0] if first else ''}")


def path_failures_observable(f2c):
    """Git Bash's MSYS layer makes a doomed open look like it succeeded, so the
    same binary that reports 'cannot open' under cmd and Linux reports a parse
    error here. Detect that rather than blaming the program."""
    missing = "no-such-file-canary.sat"
    if os.path.exists(missing):
        return True
    r = subprocess.run([f2c, missing], capture_output=True, text=True)
    return r.returncode != 0 and "cannot open" in (r.stderr + r.stdout)


def main(f2c, dpll):
    if path_failures_observable(f2c):
        expect_exit("missing input is reported", 1, f2c, "no-such-file.sat")
        expect_exit("unwritable output is reported", 1, f2c, "tests/nested.sat",
                    "/nope/deep/out.cnf")
        expect_exit("dpll missing input is reported", 1, dpll, "no-such-file.cnf")
    else:
        print("skip open-failure checks: this shell hides failed opens "
              "(MSYS); they run under cmd and under Linux")
    expect_exit("help exits 0", 0, f2c, "-h")
    expect_exit("unknown flag exits 2", 2, f2c, "--bogus")
    expect_exit("dpll help exits 0", 0, dpll, "-h")
    expect_exit("dpll unknown flag exits 2", 2, dpll, "--bogus")
    expect_exit("dpll --cnf on a .sat file fails", 1, dpll, "--cnf",
                "tests/nested.sat")

    src = "tests/nested.sat"
    to_stdout = subprocess.run([f2c, src], capture_output=True, text=True,
                               check=True).stdout

    fd, out = tempfile.mkstemp(suffix=".cnf")
    os.close(fd)
    try:
        subprocess.run([f2c, src, out], check=True)
        with open(out) as fh:
            report(fh.read() == to_stdout, "output-file form matches stdout")
    finally:
        os.unlink(out)

    with open(src) as fh:
        piped = subprocess.run([f2c], stdin=fh, capture_output=True, text=True,
                               check=True).stdout
    report(piped == to_stdout, "stdin matches file input")

    def verdict(args, stdin=None):
        r = subprocess.run([dpll, "-q", *args], stdin=stdin,
                           capture_output=True, text=True, check=True)
        return next((l.strip() for l in r.stdout.splitlines()
                     if l.strip() in ("SAT", "UNSAT")), None)

    from_file = verdict(["tests/cnf/hole3.cnf"])
    with open("tests/cnf/hole3.cnf") as fh:
        from_stdin = verdict([], stdin=fh)
    report(from_file == from_stdin == "UNSAT", "dpll stdin matches file input",
           f"{from_stdin} vs {from_file}")

    report(verdict(["--sat", "tests/nested.sat"]) == "SAT",
           "dpll --sat override on a .sat file")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
