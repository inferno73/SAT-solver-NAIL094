# Turns bench_dpll.py CSV output into a booktabs table the report can \input
#
# usage: python make_tables_dpll.py <results.csv> <out.tex> <caption> <label>

import csv
import sys


def esc(s):
    return s.replace("_", r"\_")


def main(csv_path, out_path, caption, label):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrrlrrr}",
        r"\toprule",
        r"instance & vars & clauses & result & decisions & unit props & CPU s \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(" & ".join([
            esc(r["instance"]),
            r["variables"],
            r["clauses"],
            r["verdict"],
            f'{int(r["decisions"]):,}'.replace(",", r"\,"),
            f'{int(r["unit_props"]):,}'.replace(",", r"\,"),
            f'{float(r["cpu_seconds"]):.3f}',
        ]) + r" \\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\end{table}",
    ]
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main(*sys.argv[1:5])
