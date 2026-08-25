# Tasks solved with an existing SAT solver

Course: NAIL094 Decision Procedures and Verification, Petr Kučera, KTIML MFF UK

Four tasks that use a SAT solver as an oracle through
[PySAT](https://pysathq.github.io), so the work in each is the encoding rather than
the search.

## Tasks

1. **[N Queens Puzzle](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_n_queens.php)**
   — [n-queens/](n-queens/), [report.pdf](n-queens/report/report.pdf)
   - encoding: `nqueens.py`
   - tests: `test_queens.py`
   - measurements: `bench.py`, `results.csv`, `stats.csv`

2. **[Cryptarithms](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_alphametics.php)**
   — [cryptarithms/](cryptarithms/), [report.pdf](cryptarithms/report/report.pdf)
   - encoding: `cryptarithm.py`, `formula.py`, `instances.py`
   - tests: `test_cryptarithm.py`
   - measurements: `bench.py`, `results.csv`

3. **[Testing Equivalence](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_equivalence.php)**
   — [testing-equivalence/](testing-equivalence/), [report.pdf](testing-equivalence/report/report.pdf)
   - encoding: `equivalence.py`, `pairs.py`
   - tests: `test_equivalence.py`
   - measurements: `bench.py`, `results.csv`, `hardness.csv`

4. **[Backbones](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_backbone.php)**
   — [backbones/](backbones/), [report.pdf](backbones/report/report.pdf)
   - algorithms: `backbone.py`
   - tests: `test_backbone.py`, `verify.py`
   - measurements: `bench.py`, `results.csv`, `verification.csv`

Every file named above is in that task's `code/` directory, next to an
`experiments.ipynb` committed with its outputs saved. Algorithms are placed in the
modules and never in the notebook, so a measurement does not depend on which cells
were run.

In the backbones task `verify.py` is separate from `test_backbone.py` on purpose. It
recomputes every backbone from scratch with its own solver instances, so it is far
more expensive than the algorithms it checks and is kept out of every reported
measurement.

## Benchmarks

Committed with the code, so nothing has to be downloaded and no path has to be
adjusted. 

1. [../benchmarks_allSAT/](../benchmarks_allSAT/) — used by backbones. 27 families
   and 131 instances from
   [SATLIB](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html), the collection of Hoos
   and Stützle, restricted to the families it describes as containing only
   satisfiable formulas. Among them are the CBS families, Random-3-SAT generated
   with a controlled backbone size by Singer, Gent and Smaill, *Backbone Fragility
   and the Local Search Cost Peak*, JAIR 2000. Their names state the size of the
   backbone, which is what makes them ground truth for that task.
2. [testing-equivalence/benchmarks/](testing-equivalence/benchmarks/) — used by
   testing equivalence, a wider selection of
   [SATLIB](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html) families, satisfiable
   and unsatisfiable alike.
3. [cryptarithms/instances/](cryptarithms/instances/) — used by cryptarithms, 1997
   puzzles from the collection of Naoyuki Tamura,
   [Cryptarithm Puzzles](https://tamura70.gitlab.io/web-puzzle/cryptarithm/). Each
   puzzle is printed with its solution, which is what lets the answers be checked
   against a published result rather than only against the encoding.

N Queens needs no instances, since the board is generated from `n`.

## Requirements

Python 3.11 or newer and [requirements.txt](requirements.txt), pinned to the
versions the reported measurements were taken with. The pin on `python-sat`
matters most, because the package ships the solvers themselves rather than
calling an installed one: version 1.9.dev7 is what provides CaDiCaL 1.5.3,
Glucose 4 and MiniSat 2.2. Those are the solvers every timing in the reports was
measured on, so a different version of `python-sat` would give different numbers.

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Linux: .venv/bin/python
```

## Running

From a task's `code/` directory:

```
python test_cryptarithm.py                        # the correctness checks
python bench.py                                   # rewrite results.csv
python cryptarithm.py "SEND+MORE=MONEY" --all     # solve one instance
```

`nqueens.py`, `equivalence.py` and `backbone.py` take a command line the same way.

Each report is `report.tex` with its built `report.pdf` beside it, so there is
nothing to compile. To rebuild one, run `pdflatex report.tex` twice from its
`report/` directory, the second pass being what resolves the table references. The
shared preamble is in [shared/](shared/).
