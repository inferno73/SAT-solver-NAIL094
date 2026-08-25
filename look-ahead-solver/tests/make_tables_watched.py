r"""
Turns bench_watched.py CSV output into a booktabs table the report can \input

usage: python make_tables_watched.py <results.csv> <out.tex> <caption> <label>
"""

import csv
import sys


def esc(s):
    return s.replace("_", r"\_")


def thousands(n):
    return f"{int(n):,}".replace(",", r"\,")


def main(csv_path, out_path, caption, label):
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lrrrlrrrrr}",
        r"\toprule",
        r"& & & & & \multicolumn{3}{c}{clauses checked} "
        r"& \multicolumn{2}{c}{time (s)} \\",
        r"\cmidrule(lr){6-8}\cmidrule(lr){9-10}",
        r"instance & vars & clauses & $k>2$ & result & adjacency & watched "
        r"& ratio & adjacency & watched \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(" & ".join([
            esc(r["instance"]),
            r["variables"],
            r["clauses"],
            f'{float(r["frac_len_gt2"]):.2f}',
            r["verdict"],
            thousands(r["adjacency_checked"]),
            thousands(r["watched_checked"]),
            f'{float(r["checked_ratio"]):.2f}',
            f'{float(r["adjacency_time"]):.5f}',
            f'{float(r["watched_time"]):.5f}',
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
