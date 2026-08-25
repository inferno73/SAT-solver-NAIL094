# Solver from scratch

Course: NAIL094 Decision Procedures and Verification, Petr Kučera, KTIML MFF UK

Each task builds on the one before it, so this is one program as whole, rather than four separate ones. The later tasks add a propagation engine or a branching rule and leave the rest alone.

## Tasks

1. **[Tseitin Encoding and DIMACS Format](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_tseitin.php)**
   - code: `src/formula.hpp`, `src/tseitin.hpp`, `src/formula2cnf.cpp`
   - report: x.

2. **[DPLL Algorithm](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_dpll.php)**
   - code: `src/dpll.hpp`, `src/dpll.cpp`
   - report: [reports/dpll/report.pdf](reports/dpll/report.pdf)

3. **[Watched Literals](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_watched.php)**
   - code: `src/watched_literals.hpp`
   - report: [reports/watched/report.pdf](reports/watched/report.pdf)

4. **[Look-Ahead Solver](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_look_ahead.php)**
   - code: `src/look_ahead.hpp`, `src/eager_counters.hpp`
   - report: [reports/lookahead/report.pdf](reports/lookahead/report.pdf)

`src/cnf.hpp` is the DIMACS reader and `src/lit.hpp` the literal encoding, both shared. 
`src/dpll.hpp` holds the trail, the statistics, the adjacency-list propagation and the search loop.

The three propagation engines share one four-method interface and are chosen by a template parameter, so the search loop, the trail and the decision heuristic are the same code in every configuration. Only propagation differs, which is what makes the comparison in the watched literals report a comparison of data structures and nothing else.

## Benchmarks

Available within the repository (so separate download isn't necessary). 

1. [benchmarks/](benchmarks/) — the three families used by all three reports, taken
   from [SATLIB](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html), the collection of
   Hoos and Stützle:
   [All Interval Series](https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/AIS/descr.html),
   [pigeonhole](https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/DIMACS/PHOLE/descr.html)
   from the DIMACS set, contributed by John Hooker, and
   [Uniform Random-3-SAT](https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/RND3SAT/descr.html).
   The files are unmodified, and each keeps the source header it came with.
2. [task1-example-Input-Files/](task1-example-Input-Files/) — the five example
   formulas given with the
   [Tseitin task](https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/task_tseitin.php)
3. [tests/cnf/](tests/cnf/) — the small cases for the test suite, written by hand or
   produced by `tests/gen_hole.py`.

## Requirements

A C++20 compiler. The solver uses only the standard library, so there is no
dependency to install, and it is built and tested on Linux with g++ 13. The scripts under `tests/` need Python 3 and use only its standard library.

## Building and running

```
make                     # Linux and WSL
mingw32-make             # MSYS2 UCRT64 on Windows, where `make` is absent
```

```
formula2cnf [--equiv|--impl] [input [output]]
dpll [--cnf|--sat] [--equiv|--impl] [--watched|--counters]
     [--lookahead [--heuristic=crh|wbh|bsh]] [-q] [input]
```

`formula2cnf` reads standard input and writes standard output when no file is
given. 
`dpll` picks the format from the extension, `.cnf` for DIMACS and `.sat` for
the simplified SMT-LIB syntax, passing the second through the Tseitin encoder so
the search only ever sees CNF. Without a flag it branches in index order over
adjacency lists, which is the plain DPLL of the second task. Every run prints the
verdict, a model if satisfiable, and the statistics the tasks ask for: CPU time,
decisions, unit propagation steps and clauses checked.

```
dpll benchmarks/ais/ais6.cnf                                # plain DPLL
dpll --watched benchmarks/ais/ais6.cnf                      # watched literals
dpll --lookahead --heuristic=wbh benchmarks/ais/ais6.cnf
```

## Tests and measurements

```
make test              # correctness, every configuration
make test-linux        # the same, built and run under WSL
make bench             # writes results/task2*.csv
make bench-watched     # writes results/watched.csv
make bench-lookahead   # writes results/lookahead.csv
make bench-random      # writes results/random.csv
make check-reports     # every figure in the reports against those CSVs
```

`tests/run_all.py` drives the correctness side: the Tseitin encoding against
exhaustive enumeration, the solver against brute force on both input formats, the
engines and heuristics against each other, then fuzzing every configuration against
exhaustive search on random instances near the phase transition.

The measurement side is the same shape for each report. A `bench_*.py` script runs
the solver several times per instance and keeps the fastest, writing a CSV under
`results/`. A `make_tables_*.py` script turns that CSV into a table under
`reports/<task>/tables/`, which the report reads with `\input`, so no measurement is
typed into a report by hand. `check-reports` closes the loop by recomputing every
number quoted in the prose from the CSVs, which catches a benchmark re-run while the
text still quotes the old figures. It needs no build and no solver.

Each report is `report.tex` with its built `report.pdf` beside it. The preamble is shared with the other task set and is placed in
[../commercial-sat-solver/shared/](../commercial-sat-solver/shared/).
