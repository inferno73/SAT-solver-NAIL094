#pragma once

/*
Look-ahead branching

Replaces the branching rule of dpll.hpp: at every node each free variable is
tentatively assigned in both polarities and propagated, and what comes back
decides both which variable to branch on and what can be inferred outright

  conflict in one polarity   the opposite literal is failed and is forced
  conflict in both           the node is unsatisfiable
  no clause reduced          the assignment is an autarky and can be committed
  otherwise                  measure the reduction and undo

The three difference heuristics follow Heule and van Maaren, Handbook of
Satisfiability, chapter 5

  CRH(x) = sum over new clauses of size k of gamma_k          Kullmann weights
  WBH(x) = sum over new binary clauses (a or b) of w(-a) + w(-b)
  BSH(x) = sum over new binary clauses (a or b) of w(-a) * w(-b)

where w(l) = sum over k of gamma_k * (occurrences of l in clauses of size k),
computed once from the input formula
gamma_k is 5^(3-k) for WBH and 2^(3-k) for BSH, as given by the task page

The two directions are combined by the MixDiff function of the same chapter,
1024*L*R + L + R, product for a balanced tree and sum only to break ties

Requires PropCounter from eager_counters.hpp, which is what supplies exact
clause lengths
*/

#include <cmath>
#include <utility>
#include <vector>

#include "dpll.hpp"
#include "eager_counters.hpp"
#include "lit.hpp"

enum class Heuristic { CRH, WBH, BSH };

inline const char* heuristicName(Heuristic h) {
    switch (h) {
        case Heuristic::CRH: return "crh";
        case Heuristic::WBH: return "wbh";
        default: return "bsh";
    }
}

struct LookAheadConfig {
    Heuristic heuristic = Heuristic::WBH;
    bool localLearning = true;
    bool autarky = true;
};

class LookAheadDecider {
public:
    LookAheadConfig cfg;

    template <class S>
    Decision decide(S& s) {
        if (!ready_) prepare(s);

        for (;;) {
            if (!collectCandidates(s)) return Decision::solved();

            ++s.stats().lookaheads;
            forced_.clear();
            bool restart = false;

            double bestPhi = -1;
            Lit bestLit = -1;

            for (Var v : cands_) {
                if (s.trail().assigned(v)) continue;   // forced earlier in this pass

                Probe pos = run(s, mkLit(v, true));
                Probe neg_ = run(s, mkLit(v, false));

                if (!pos.ok && !neg_.ok) return Decision::conflict();

                if (!pos.ok || !neg_.ok) {
                    ++s.stats().failedLiterals;
                    forced_.push_back(pos.ok ? mkLit(v, true) : mkLit(v, false));
                    continue;
                }

                /*
                An autarky holds only for the formula as it stands now, and
                unlike a failed literal it does not survive further forcing, so
                it is committed alone and the pass starts over
                */
                if (cfg.autarky && (pos.autarky || neg_.autarky)) {
                    ++s.stats().autarkies;
                    Lit a = pos.autarky ? mkLit(v, true) : mkLit(v, false);
                    if (!s.force(a)) return Decision::conflict();
                    restart = true;
                    break;
                }

                double L = neg_.h;   // Diff for x = 0
                double R = pos.h;    // Diff for x = 1
                double phi = 1024.0 * L * R + L + R;
                if (phi > bestPhi) {
                    bestPhi = phi;
                    // the more reduced branch is the smaller subproblem, take it first
                    bestLit = (R >= L) ? mkLit(v, true) : mkLit(v, false);
                }
            }

            if (restart || !forced_.empty()) {
                for (Lit l : forced_)
                    if (!s.force(l)) return Decision::conflict();
                continue;                       // the node changed, look again
            }
            if (bestLit < 0) return Decision::solved();
            return Decision::branch(bestLit);
        }
    }

private:
    struct Probe {
        bool ok = false;
        bool autarky = false;
        double h = 0;
    };

    /*
    w(l) = sum over k >= 2 of gamma_k * (occurrences of l in clauses of size k),
    read off the input formula once
    */
    template <class S>
    void prepare(S& s) {
        const Cnf& f = s.formula();
        int n = 2 * f.nvars;
        wWBH_.assign(n, 0.0);
        wBSH_.assign(n, 0.0);
        for (const Clause& c : f.clauses) {
            int k = static_cast<int>(c.size());
            if (k < 2) continue;
            double gw = std::pow(5.0, 3 - k);
            double gb = std::pow(2.0, 3 - k);
            for (Lit l : c) {
                wWBH_[l] += gw;
                wBSH_[l] += gb;
            }
        }
        ready_ = true;
    }

    /*
    Kullmann's weights for CRH
    The tabulated values stop at k = 6, above which the chapter gives the
    linear regression they were fitted to, which continues them smoothly:
    it reproduces gamma_2 = 0.978 and gamma_3 = 0.214 against the tabulated
    1 and 0.2
    */
    static double crhGamma(int k) {
        switch (k) {
            case 2: return 1.0;
            case 3: return 0.2;
            case 4: return 0.05;
            case 5: return 0.01;
            case 6: return 0.003;
            default: return 20.4514 * std::pow(0.218673, k);
        }
    }

    template <class S>
    bool collectCandidates(S& s) {
        Var start = s.firstFree();
        if (start < 0) return false;

        cands_.clear();
        for (Var v = start; v < s.trail().nvars; ++v)
            if (!s.trail().assigned(v)) cands_.push_back(v);
        return !cands_.empty();
    }

    /*
    Tentatively assign l, measure the reduction, learn what it implied, undo
    */
    template <class S>
    Probe run(S& s, Lit l) {
        Probe p;
        int base = s.trail().size();
        int mark = s.probeMark();

        s.prop().beginMeasure();
        p.ok = s.probe(l);
        ++s.stats().probes;

        if (p.ok) {
            s.prop().collect(newSizes_, newBinaries_);
            p.h = score();
            p.autarky = s.prop().autarky();

            // the chapter's local learning: l implies y, so record -l or y
            if (cfg.localLearning) {
                implied_.clear();
                for (int i = base + 1; i < s.trail().size(); ++i)
                    implied_.push_back(s.trail().stack[i]);
            }
        }

        s.prop().endMeasure();
        s.undoProbe(mark);

        if (p.ok && cfg.localLearning) {
            for (Lit y : implied_) s.prop().learnBinary(neg(l), y);
        }
        return p;
    }

    double score() const {
        if (cfg.heuristic == Heuristic::CRH) {
            double h = 0;
            for (size_t k = 2; k < newSizes_.size(); ++k)
                if (newSizes_[k]) h += newSizes_[k] * crhGamma(static_cast<int>(k));
            return h;
        }
        const std::vector<double>& w =
            (cfg.heuristic == Heuristic::WBH) ? wWBH_ : wBSH_;
        double h = 0;
        for (const std::pair<Lit, Lit>& b : newBinaries_) {
            double wa = w[neg(b.first)];
            double wb = w[neg(b.second)];
            h += (cfg.heuristic == Heuristic::WBH) ? (wa + wb) : (wa * wb);
        }
        return h;
    }

    std::vector<Var> cands_;
    std::vector<Lit> forced_;
    std::vector<Lit> implied_;
    std::vector<int> newSizes_;
    std::vector<std::pair<Lit, Lit>> newBinaries_;
    std::vector<double> wWBH_, wBSH_;
    bool ready_ = false;
};
