r"""
Turns bench_lookahead.py CSV output into booktabs tables the report can \input

usage: python make_tables_lookahead.py <results.csv> <outdir>
"""

import csv
import sys

NAMES = ("dpll", "counters", "crh", "wbh", "bsh", "bare")
HEAD = ("plain DPLL", "counters", "CRH", "WBH", "BSH", "WBH bare")


def esc(s):
    return s.replace("_", r"\_")


def thousands(v):
    return f"{int(v):,}".replace(",", r"\,")


def emit(path, rows, kind, caption, label):
    lines = [
        r"\begin{table}[H]", r"\centering", r"\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{tabular}{lrl" + "r" * len(NAMES) + "}",
        r"\toprule",
        "instance & vars & result & " + " & ".join(HEAD) + r" \\",
        r"\midrule",
    ]
    for r in rows:
        cells = [esc(r["instance"]), r.get("variables", "--"), r.get("verdict", "--")]
        for n in NAMES:
            if kind == "decisions":
                v = r.get(f"{n}_decisions")
                cells.append(thousands(v) if v not in (None, "") else "--")
            else:
                v = r.get(f"{n}_time")
                cells.append(f"{float(v):.4f}" if v not in (None, "") else "--")
        lines.append(" & ".join(str(c) for c in cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}",
              rf"\caption{{{caption}}}", rf"\label{{{label}}}", r"\end{table}"]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    csv_path, outdir = sys.argv[1], sys.argv[2]
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    emit(f"{outdir}/decisions.tex", rows, "decisions",
         "Number of decisions, that is the size of the search tree. "
         "The counters column is the eager engine under plain branching, a "
         "control rather than a solver variant; its tree is identical to plain "
         "DPLL by construction. WBH bare is WBH with local learning and "
         "autarky reasoning switched off.",
         "tab:decisions")
    emit(f"{outdir}/times.tex", rows, "time",
         "Running time in seconds for the same runs, fastest of three, "
         "search only.",
         "tab:times")
