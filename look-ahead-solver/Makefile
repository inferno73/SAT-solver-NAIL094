# Build with `mingw32-make` on this machine (MSYS2 UCRT64 g++; `make` is absent).
#   mingw32-make            release build
#   mingw32-make debug      -O0 -g with asserts and sanitizer-friendly flags
#   mingw32-make test       encoding check, solver check, and fuzzing
#   mingw32-make test-linux same, but built and run under WSL
#   mingw32-make check-reports  report figures against the CSVs, no build needed
#   mingw32-make clean

CXX := g++
CXXFLAGS := -std=c++20 -Wall -Wextra -O2
LDFLAGS :=

BIN := bin
SRC := src

HEADERS := $(wildcard $(SRC)/*.hpp)
TARGETS := $(BIN)/formula2cnf.exe $(BIN)/dpll.exe

all: $(TARGETS)

$(BIN)/formula2cnf.exe: $(SRC)/formula2cnf.cpp $(HEADERS) | $(BIN)
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

$(BIN)/dpll.exe: $(SRC)/dpll.cpp $(HEADERS) | $(BIN)
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

debug: CXXFLAGS := -std=c++20 -Wall -Wextra -O0 -g -fno-omit-frame-pointer
debug: clean all

EXAMPLES := $(wildcard task1-example-Input-Files/*.sat)

GOOD_SAT := $(filter-out tests/bad-%.sat,$(wildcard tests/*.sat))

test: $(TARGETS)
	python tests/run_all.py $(BIN)/formula2cnf.exe $(BIN)/dpll.exe

# same build and tests under WSL, since grading happens on Linux
test-linux:
	wsl -e bash -lc "g++ $(CXXFLAGS) -o /tmp/formula2cnf src/formula2cnf.cpp && g++ $(CXXFLAGS) -o /tmp/dpll src/dpll.cpp && python3 tests/run_all.py /tmp/formula2cnf /tmp/dpll"

# DPLL experiments, writes results/task2*.csv and refreshes the report tables
bench: $(TARGETS)
	python tests/bench_dpll.py $(BIN)/dpll.exe --repeat 3 --csv results/task2_examples.csv $(EXAMPLES)
	python tests/bench_dpll.py $(BIN)/dpll.exe --repeat 3 --csv results/task2.csv 	  benchmarks/phole/hole6.cnf benchmarks/phole/hole7.cnf benchmarks/phole/hole8.cnf 	  benchmarks/phole/hole9.cnf benchmarks/ais/ais6.cnf benchmarks/ais/ais8.cnf 	  benchmarks/ais/ais10.cnf benchmarks/ais/ais12.cnf 	  benchmarks/rnd3sat/uf50-01.cnf benchmarks/rnd3sat/uf50-010.cnf 	  benchmarks/rnd3sat/uf50-0100.cnf benchmarks/rnd3sat/uf50-0101.cnf

# watched literals comparison, writes results/watched.csv
bench-watched: $(TARGETS)
	python tests/bench_watched.py $(BIN)/dpll.exe --repeat 3 --csv results/watched.csv 	  benchmarks/phole/hole6.cnf benchmarks/phole/hole7.cnf benchmarks/phole/hole8.cnf 	  benchmarks/phole/hole9.cnf benchmarks/ais/ais6.cnf benchmarks/ais/ais8.cnf 	  benchmarks/ais/ais10.cnf benchmarks/ais/ais12.cnf

# look-ahead comparison, writes results/lookahead.csv
bench-lookahead: $(TARGETS)
	python tests/bench_lookahead.py $(BIN)/dpll.exe --repeat 3 --csv results/lookahead.csv 	  benchmarks/phole/hole6.cnf benchmarks/phole/hole7.cnf benchmarks/phole/hole8.cnf 	  benchmarks/ais/ais6.cnf benchmarks/ais/ais8.cnf benchmarks/ais/ais10.cnf 	  benchmarks/ais/ais12.cnf benchmarks/rnd3sat/uf50-01.cnf

# heuristic separation on random 3-SAT, writes results/random.csv
bench-random: $(TARGETS)
	python tests/bench_random.py $(BIN)/dpll.exe 300 --csv results/random.csv

# every figure quoted in the three reports against the CSVs it came from,
# so re-running a bench without updating the prose is caught
check-reports:
	python tests/check_report_dpll.py
	python tests/check_report_watched.py
	python tests/check_report_lookahead.py

$(BIN):
	mkdir $(BIN)

clean:
	-if exist $(BIN) rmdir /s /q $(BIN)

.PHONY: all debug test test-linux bench bench-watched bench-lookahead bench-random \
        check-reports clean
