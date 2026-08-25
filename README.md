# NAIL094 programming tasks

Task list: https://ktiml.mff.cuni.cz/~kucerap/satsmt/practical/prg_tasks.php

Two sets of tasks. In the first the solver is written from scratch, in the
second an existing SAT solver is used as an oracle and the main work is the
encoding.

## [look-ahead-solver/](look-ahead-solver/) — writing the solver

One C++ program built up over four tasks, each adding to the one before it.

1. Tseitin Encoding and DIMACS Format
2. DPLL Algorithm
3. Watched Literals
4. Look-Ahead Solver

## [commercial-sat-solver/](commercial-sat-solver/) — using a solver

Four independent tasks in Python, through PySAT.

1. N Queens Puzzle
2. Cryptarithms
3. Testing Equivalence
4. Backbones

## [benchmarks_allSAT/](benchmarks_allSAT/)

SATLIB instances shared between the two sets, 27 families and 131 instances,
restricted to the families SATLIB describes as containing only satisfiable
formulas. Kept at the top level because more than one task uses them.

## Reading it

Each set has its own README with the file map, the requirements and how to run.
Every task that asks for a report has it as `report.tex` with the built
`report.pdf` beside it.

All benchmark instances are committed, so no data has to be downloaded and no
path has to be adjusted.
