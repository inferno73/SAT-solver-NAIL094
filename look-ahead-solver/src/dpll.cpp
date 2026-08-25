/*
dpll -- DPLL solver

  dpll [input]

input is a file, or stdin when omitted
Format follows the extension, .cnf for DIMACS and .sat for the simplified
SMT-LIB format, and can be forced instead with --cnf or --sat

  --cnf | --sat      force the input format
  --equiv | --impl   Tseitin mode for .sat input, default --equiv
  --watched          propagate with watched literals instead of adjacency lists
  --counters         propagate with eager clause-length counters, plain branching
                     the counters exist for look-ahead, which needs the lengths
                     they keep; run this way they answer what that bookkeeping
                     costs when nothing reads it
  --lookahead        look-ahead branching, implies the eager counter engine
  --heuristic=NAME   crh, wbh or bsh, default wbh, only with --lookahead
  -q                 statistics only, no model
*/

#include <chrono>
#include <ctime>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "dpll.hpp"
#include "cnf.hpp"
#include "eager_counters.hpp"
#include "look_ahead.hpp"
#include "watched_literals.hpp"

namespace {

void usage() {
    std::cerr << "usage: dpll [--cnf|--sat] [--equiv|--impl] [--watched|--counters]\n"
                 "            [--lookahead [--heuristic=crh|wbh|bsh]] [-q] [input]\n";
}

/*
The search is the same in every configuration, only the propagation engine and
the branching rule differ, which is what makes the comparisons measure those and
nothing else
*/
template <class Prop>
Result solveWith(const Cnf& f, Stats& stats, std::vector<Lit>& model) {
    Solver<Prop> solver(f, stats);
    Result res = solver.solve();
    if (res == Result::Sat) model = solver.model();
    return res;
}

Result solveLookAhead(const Cnf& f, Stats& stats, std::vector<Lit>& model,
                      const LookAheadConfig& cfg) {
    Solver<PropCounter, LookAheadDecider> solver(f, stats);
    solver.decider().cfg = cfg;
    Result res = solver.solve();
    if (res == Result::Sat) model = solver.model();
    return res;
}

/*
DIMACS input gets every literal in increasing variable order, which the task
requires
SMT-LIB input additionally gets the projection onto the named input variables,
the gate variables Tseitin introduced being of no interest outside the solver
*/
void printModel(std::ostream& out, const Cnf& f, const std::vector<Lit>& model) {
    if (f.nInputVars > 0) {
        for (int v = 0; v < f.nInputVars; ++v)
            out << "c " << f.varNames[v] << " = "
                << (sign(model[v]) ? "true" : "false") << "\n";
    }
    out << "v";
    for (Lit l : model) out << " " << litToDimacs(l);
    out << " 0\n";
}

void printStats(std::ostream& out, const Cnf& f, const Stats& s,
                const char* engine, bool la, const LookAheadConfig& cfg) {
    out << "c propagation     " << engine << "\n";
    out << "c branching       " << (la ? "look-ahead" : "index order") << "\n";
    if (la) {
        out << "c heuristic       " << heuristicName(cfg.heuristic) << "\n";
        out << "c lookaheads      " << s.lookaheads << "\n";
        out << "c probes          " << s.probes << "\n";
        out << "c failed literals " << s.failedLiterals << "\n";
        out << "c autarkies       " << s.autarkies << "\n";
        out << "c learned binary  " << s.learnedBinaries << "\n";
        out << "c probe props     " << s.probePropagations << "\n";
        out << "c probe checked   " << s.probeClausesChecked << "\n";
    }
    out << "c variables       " << f.nvars << "\n";
    out << "c clauses         " << f.clauses.size() << "\n";
    out << "c cpu seconds     " << s.cpuSeconds << "\n";
    out << "c decisions       " << s.decisions << "\n";
    out << "c unit props      " << s.propagations << "\n";
    out << "c conflicts       " << s.conflicts << "\n";
    out << "c clauses checked " << s.clausesChecked << "\n";
    out << "c wall seconds    " << s.wallSeconds << "\n";
}

}  // namespace

int main(int argc, char** argv) {
    std::string inPath;
    Encoding enc = Encoding::Equivalence;
    bool quiet = false;
    bool watched = false;
    bool counters = false;
    bool lookahead = false;
    LookAheadConfig laCfg;
    bool forceFmt = false;
    InputFormat fmt = InputFormat::Dimacs;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--cnf") { fmt = InputFormat::Dimacs; forceFmt = true; }
        else if (a == "--sat") { fmt = InputFormat::Smtlib; forceFmt = true; }
        else if (a == "--equiv") enc = Encoding::Equivalence;
        else if (a == "--impl") enc = Encoding::Implication;
        else if (a == "--watched") watched = true;
        else if (a == "--counters") counters = true;
        else if (a == "--lookahead") lookahead = true;
        else if (a == "--heuristic=crh") laCfg.heuristic = Heuristic::CRH;
        else if (a == "--heuristic=wbh") laCfg.heuristic = Heuristic::WBH;
        else if (a == "--heuristic=bsh") laCfg.heuristic = Heuristic::BSH;
        else if (a == "--no-learning") laCfg.localLearning = false;
        else if (a == "--no-autarky") laCfg.autarky = false;
        else if (a == "-q") quiet = true;
        else if (a == "-h" || a == "--help") { usage(); return 0; }
        else if (!a.empty() && a[0] == '-') { usage(); return 2; }
        else if (inPath.empty()) inPath = a;
        else { usage(); return 2; }
    }

    if (!forceFmt && !inPath.empty()) fmt = formatFromPath(inPath);

    Cnf f;
    try {
        if (inPath.empty()) {
            f = loadCnf(std::cin, fmt, enc);
        } else {
            std::ifstream in(inPath);
            if (!in) { std::cerr << "cannot open " << inPath << "\n"; return 1; }
            f = loadCnf(in, fmt, enc);
        }
    } catch (const std::exception& e) {
        std::cerr << "input error: " << e.what() << "\n";
        return 1;
    }

    NormalizeStats ns = normalize(f);
    if (ns.anything())
        std::cout << "c removed " << ns.tautologiesRemoved << " tautological clauses, "
                  << ns.duplicateClausesRemoved << " repeated clauses and "
                  << ns.duplicateLitsRemoved << " repeated literals\n";

    Stats stats;
    std::clock_t c0 = std::clock();
    auto t0 = std::chrono::steady_clock::now();

    std::vector<Lit> model;
    const char* engine = (lookahead || counters) ? "eager counters"
                       : watched                  ? "watched literals"
                                                  : "adjacency lists";
    Result res = lookahead ? solveLookAhead(f, stats, model, laCfg)
               : counters  ? solveWith<PropCounter>(f, stats, model)
               : watched   ? solveWith<PropWatched>(f, stats, model)
                           : solveWith<PropAdjacency>(f, stats, model);

    stats.cpuSeconds = static_cast<double>(std::clock() - c0) / CLOCKS_PER_SEC;
    stats.wallSeconds = std::chrono::duration<double>(
                            std::chrono::steady_clock::now() - t0).count();

    if (res == Result::Sat) {
        std::cout << "SAT\n";
        if (!quiet) printModel(std::cout, f, model);
    } else {
        std::cout << "UNSAT\n";
    }
    printStats(std::cout, f, stats, engine, lookahead, laCfg);
    return 0;
}
