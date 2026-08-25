#pragma once

/*
DPLL solver has: trail (partial assignment), statistics, adjacency-list propagation, search loop

Solver<Prop, Decider> with both defaulted is plain DPLL

  Prop     PropAdjacency     this file          adjacency lists
           PropWatched       prop_watched.hpp   2 watched literals
           PropCounter       prop_counter.hpp   eager clause counters

  Decider  PlainDecider      this file          lowest free index
           LookaheadDecider  lookahead.hpp      look-ahead

Both are compile-time types, not runtime options
sat_main.cpp holds one instantiation per combination and selects with
--prop and --lookahead
*/

#include <cstdint>
#include <vector>

#include "cnf.hpp"
#include "lit.hpp"

// Statistics

struct Stats {
    long long decisions = 0;
    long long propagations = 0;      // literals derived by unit propagation
    long long conflicts = 0;
    double cpuSeconds = 0;           // std::clock
    double wallSeconds = 0;          // finer resolution than clock()

    /*
    One increment per clause taken off the list being walked, immediately
    before the clause is examined
    Adjacency and watched count this identically and are comparable
    The eager engine is not: it finishes the whole list after a conflict so
    that its counters stay symmetric for the undo, where the other two return
    at once, so it reports more visits for the same search
    */
    long long clausesChecked = 0;

    // look-ahead only
    long long lookaheads = 0;        // passes of the look-ahead loop, a node
                                     // forcing or committing runs another pass
    long long probes = 0;            // tentative assignments evaluated
    long long failedLiterals = 0;
    long long autarkies = 0;
    long long learnedBinaries = 0;   // binary clauses added by local learning
    long long probePropagations = 0; // speculative, discarded on undo
    long long probeClausesChecked = 0;
};

/*
lval   indexed by literal, lval[l] set means l is true
stack  assignment order, so undo runs in reverse
lim    lim[d] is the stack size when level d+1 opened
qhead  first literal an engine has not consumed

Decision literal of level d+1 is stack[lim[d]]
The stack doubles as the propagation queue
*/

struct Trail {
    int nvars = 0;
    std::vector<uint8_t> lval;
    std::vector<Lit> stack;
    std::vector<int> lim;
    int qhead = 0;

    void init(int n) {
        nvars = n;
        lval.assign(2 * n, 0);
        stack.clear();
        stack.reserve(n);
        lim.clear();
        qhead = 0;
    }

    bool isTrue(Lit l) const { return lval[l] != 0; }
    bool isFalse(Lit l) const { return lval[neg(l)] != 0; }
    bool isUndef(Lit l) const { return !lval[l] && !lval[neg(l)]; }
    bool assigned(Var v) const { return lval[mkLit(v, true)] || lval[mkLit(v, false)]; }

    int decisionLevel() const { return static_cast<int>(lim.size()); }
    int size() const { return static_cast<int>(stack.size()); }

    void newDecisionLevel() { lim.push_back(size()); }

    void enqueue(Lit l) {
        lval[l] = 1;
        stack.push_back(l);
    }

    bool queueEmpty() const { return qhead >= size(); }
    Lit dequeue() { return stack[qhead++]; }
};

enum class Result { Sat, Unsat };

/*
Unit propagation over adjacency lists

occ[l] lists every clause containing l
Assigning l true only shortens clauses holding neg(l), so only those are visited

Engine interface: init, trivialUnsat, propagate, onUnassign
*/

class PropAdjacency {
public:
    void init(const Cnf& f, Trail& t, Stats& s) {
        f_ = &f;
        t_ = &t;
        s_ = &s;

        occ_.assign(2 * f.nvars, {});
        for (size_t ci = 0; ci < f.clauses.size(); ++ci)
            for (Lit l : f.clauses[ci])
                occ_[l].push_back(static_cast<int>(ci));

        // an empty clause is in no occurrence list, nor are contradictory units
        for (const Clause& c : f.clauses) {
            if (c.empty()) { unsat_ = true; continue; }
            if (c.size() != 1) continue;
            if (t.isFalse(c[0])) unsat_ = true;
            else if (t.isUndef(c[0])) t.enqueue(c[0]);
        }
    }

    bool trivialUnsat() const { return unsat_; }

    bool propagate() {
        while (!t_->queueEmpty()) {
            Lit l = t_->dequeue();   // l has just become true
            Lit falsi = neg(l);      // clauses holding falsi have shrunk

            for (int ci : occ_[falsi]) {
                const Clause& c = f_->clauses[ci];
                ++s_->clausesChecked;

                Lit unit = -1;
                int nUndef = 0;
                bool sat = false;
                for (Lit x : c) {
                    if (t_->isTrue(x)) { sat = true; break; }
                    if (t_->isUndef(x)) {
                        unit = x;
                        if (++nUndef > 1) break;
                    }
                }

                if (sat || nUndef > 1) continue;
                if (nUndef == 0) return false;
                t_->enqueue(unit);
                ++s_->propagations;
            }
        }
        return true;
    }

    // lists are static, nothing to undo
    void onUnassign(Lit) {}

private:
    const Cnf* f_ = nullptr;
    Trail* t_ = nullptr;
    Stats* s_ = nullptr;

    std::vector<std::vector<int>> occ_;
    bool unsat_ = false;
};

// Branching

// what a decider returns
struct Decision {
    enum Kind { Branch, Solved, Conflict };
    Kind kind = Branch;
    Lit lit = -1;

    static Decision branch(Lit l) { return {Branch, l}; }
    static Decision solved() { return {Solved, -1}; }
    static Decision conflict() { return {Conflict, -1}; }
};

// lowest unassigned variable, positive first
struct PlainDecider {
    template <class S>
    Decision decide(S& s) {
        Var v = s.firstFree();
        if (v < 0) return Decision::solved();
        return Decision::branch(mkLit(v, true));
    }
};

// The search

template <class Prop = PropAdjacency, class Decider = PlainDecider>
class Solver {
public:
    Solver(const Cnf& f, Stats& stats) : f_(f), stats_(stats) {
        trail_.init(f.nvars);
        prop_.init(f, trail_, stats);
    }

    Decider& decider() { return decider_; }

    /*
    flipped_[d] marks whether level d+1 has tried both polarities
    That bit per level replaces the recursion
    */
    Result solve() {
        if (prop_.trivialUnsat()) return Result::Unsat;
        bool conflict = !prop_.propagate();   // unit clauses at level 0

        for (;;) {
            if (conflict) {
                ++stats_.conflicts;

                // deepest level whose decision has not been flipped yet
                int lvl = trail_.decisionLevel();
                while (lvl > 0 && flipped_[lvl - 1]) --lvl;
                if (lvl == 0) return Result::Unsat;

                Lit d = trail_.stack[trail_.lim[lvl - 1]];   // that level's decision
                backtrack(lvl - 1);
                decide(neg(d), true);
                conflict = !prop_.propagate();
                continue;
            }

            Decision d = decider_.decide(*this);
            if (d.kind == Decision::Solved) return Result::Sat;
            if (d.kind == Decision::Conflict) { conflict = true; continue; }

            decide(d.lit, false);
            conflict = !prop_.propagate();
        }
    }

    // model literals, sorted by variable index as DIMACS output requires
    std::vector<Lit> model() const {
        std::vector<Lit> m;
        m.reserve(trail_.nvars);
        for (Var v = 0; v < trail_.nvars; ++v)
            m.push_back(trail_.isTrue(mkLit(v, true)) ? mkLit(v, true) : mkLit(v, false));
        return m;
    }

    Trail& trail() { return trail_; }
    Prop& prop() { return prop_; }
    Stats& stats() { return stats_; }
    const Cnf& formula() const { return f_; }

    /*
    Lowest unassigned variable, -1 if none
    hint_ is a lower bound: moved forward here, pulled back by backtrack
    */
    Var firstFree() {
        for (Var v = hint_; v < trail_.nvars; ++v) {
            if (!trail_.assigned(v)) { hint_ = v; return v; }
        }
        hint_ = trail_.nvars;
        return -1;
    }

    /*
    Used only by the look-ahead decider: assign a literal tentatively,
    propagate, then throw the result away
    Plain DPLL never calls these
    */

    int probeMark() const { return trail_.decisionLevel(); }

    bool probe(Lit l) {
        if (!trail_.isUndef(l)) return !trail_.isFalse(l);

        // probe work is speculative, kept out of the committed counts
        long long p0 = stats_.propagations;
        long long c0 = stats_.clausesChecked;

        trail_.newDecisionLevel();
        flipped_.push_back(true);   // probes are undone, never flipped
        trail_.enqueue(l);
        bool ok = prop_.propagate();

        stats_.probePropagations += stats_.propagations - p0;
        stats_.probeClausesChecked += stats_.clausesChecked - c0;
        stats_.propagations = p0;
        stats_.clausesChecked = c0;
        return ok;
    }

    void undoProbe(int mark) { backtrack(mark); }

    // assign l as implied at the current level, false means node unsatisfiable
    bool force(Lit l) {
        if (trail_.isTrue(l)) return true;
        if (trail_.isFalse(l)) return false;
        trail_.enqueue(l);
        return prop_.propagate();
    }

private:
    // both branches of a variable count as decisions
    void decide(Lit l, bool isFlip) {
        trail_.newDecisionLevel();
        flipped_.push_back(isFlip);
        trail_.enqueue(l);
        ++stats_.decisions;
    }

    // undo every assignment above level, in reverse
    void backtrack(int level) {
        int target = trail_.lim[level];
        while (trail_.size() > target) {
            Lit l = trail_.stack.back();
            trail_.stack.pop_back();
            trail_.lval[l] = 0;
            if (var(l) < hint_) hint_ = var(l);
            prop_.onUnassign(l);
        }
        trail_.lim.resize(level);
        flipped_.resize(level);
        // levels open only with the queue drained, so this always rewinds
        trail_.qhead = target;
    }

    const Cnf& f_;
    Stats& stats_;
    Trail trail_;
    Prop prop_;
    Decider decider_;
    std::vector<char> flipped_;
    Var hint_ = 0;
};

// plain DPLL
using Dpll = Solver<PropAdjacency, PlainDecider>;
