#pragma once

/*
Eager clause-length counters

Alternative to PropAdjacency in dpll.hpp and
PropWatched in watched_literals.hpp
Per clause it keeps two numbers that are always correct for the current
assignment: how many of its literals are true, and how many are not false
The second is the clause's current length, which is what the look-ahead
difference heuristics read and what watched literals deliberately refuse to
track

look_ahead.hpp needs two things here that plain propagation does not provide

  measurement   it assigns a literal for a trial run and has to know what that
                did to the formula: which clauses got shorter, what length each
                ended at, and for any clause left with exactly two literals,
                which two those are
  learned       local learning derives new binary clauses as the search runs
                they are kept here, propagate like ordinary clauses, and are
                forgotten again on backtracking
*/

#include <cmath>
#include <utility>
#include <vector>

#include "dpll.hpp"
#include "cnf.hpp"
#include "lit.hpp"

class PropCounter {
public:
    void init(const Cnf& f, Trail& t, Stats& s) {
        f_ = &f;
        t_ = &t;
        s_ = &s;

        occ_.assign(2 * f.nvars, {});
        for (size_t ci = 0; ci < f.clauses.size(); ++ci)
            for (Lit l : f.clauses[ci])
                occ_[l].push_back(static_cast<int>(ci));

        size_.resize(f.clauses.size());
        satCount_.assign(f.clauses.size(), 0);
        stamp_.assign(f.clauses.size(), 0);
        for (size_t ci = 0; ci < f.clauses.size(); ++ci) {
            size_[ci] = static_cast<int>(f.clauses[ci].size());
            if (size_[ci] > maxLen_) maxLen_ = size_[ci];
        }

        learnedOcc_.assign(2 * f.nvars, {});

        for (const Clause& c : f.clauses) {
            if (c.empty()) { unsat_ = true; continue; }
            if (c.size() != 1) continue;
            if (t.isFalse(c[0])) unsat_ = true;
            else if (t.isUndef(c[0])) t.enqueue(c[0]);
        }
    }

    bool trivialUnsat() const { return unsat_; }

    bool propagate() {
        bool ok = true;
        while (!t_->queueEmpty()) {
            Lit p = t_->dequeue();
            if (!apply(p)) ok = false;
            applied_ = t_->qhead;
            if (!ok) break;
        }
        return ok;
    }

    /*
    Counters are applied as literals are dequeued, so a literal enqueued but
    never processed must not be undone
    Pops run from the top of the trail downwards, so comparing against the
    applied prefix is enough
    Learned binaries added below the new trail size are dropped here too
    */
    void onUnassign(Lit l) {
        int idx = t_->size();
        if (idx < applied_) {
            unapply(l);
            applied_ = idx;
        }
        while (!learned_.empty() && learned_.back().mark > idx) dropLearned();
    }

    // measurement, driven by look_ahead.hpp

    void beginMeasure() {
        measuring_ = true;
        ++mark_;
        touched_.clear();
    }

    void endMeasure() { measuring_ = false; }

    /*
    A clause counts as newly created at size k when it lost at least one literal
    and is not satisfied
    newSizes counts them per size, newBinaries lists the two surviving literals
    of each clause that came out binary
    */
    void collect(std::vector<int>& newSizes,
                 std::vector<std::pair<Lit, Lit>>& newBinaries) const {
        newSizes.assign(maxLen_ + 1, 0);
        newBinaries.clear();
        for (int ci : touched_) {
            if (satCount_[ci] != 0) continue;
            int k = size_[ci];
            if (k < 0 || k > maxLen_) continue;
            ++newSizes[k];
            if (k == 2) {
                Lit a = -1, b = -1;
                for (Lit x : f_->clauses[ci]) {
                    if (t_->isFalse(x)) continue;
                    if (a < 0) a = x;
                    else { b = x; break; }
                }
                if (a >= 0 && b >= 0) newBinaries.emplace_back(a, b);
            }
        }
    }

    // no clause lost a literal without being satisfied, so the probe is an autarky
    bool autarky() const {
        for (int ci : touched_)
            if (satCount_[ci] == 0) return false;
        return true;
    }

    // local learning

    int learnedMark() const { return static_cast<int>(learned_.size()); }

    void learnBinary(Lit a, Lit b) {
        int idx = static_cast<int>(learned_.size());
        learned_.push_back({a, b, t_->size()});
        learnedOcc_[a].push_back(idx);
        learnedOcc_[b].push_back(idx);
        ++s_->learnedBinaries;
    }

    int maxClauseLen() const { return maxLen_; }

private:
    struct Binary {
        Lit a, b;
        int mark;   // trail size when it was added, valid only above this
    };

    bool apply(Lit p) {
        bool ok = true;
        Lit falsi = neg(p);

        for (int ci : occ_[falsi]) {
            ++s_->clausesChecked;
            int k = --size_[ci];

            if (measuring_ && stamp_[ci] != mark_) {
                stamp_[ci] = mark_;
                touched_.push_back(ci);
            }
            if (satCount_[ci] != 0) continue;

            if (k == 0) {
                ok = false;                 // finish the update before reporting
            } else if (k == 1) {
                Lit u = soleFree(ci);
                if (u >= 0 && t_->isUndef(u)) {
                    t_->enqueue(u);
                    ++s_->propagations;
                }
            }
        }

        for (int ci : occ_[p]) ++satCount_[ci];

        // learned binaries holding falsi imply their other literal
        for (int idx : learnedOcc_[falsi]) {
            if (idx >= static_cast<int>(learned_.size())) continue;
            const Binary& c = learned_[idx];
            ++s_->clausesChecked;
            Lit other = (c.a == falsi) ? c.b : c.a;
            if (t_->isTrue(other)) continue;
            if (t_->isFalse(other)) ok = false;
            else {
                t_->enqueue(other);
                ++s_->propagations;
            }
        }
        return ok;
    }

    void unapply(Lit p) {
        for (int ci : occ_[p]) --satCount_[ci];
        for (int ci : occ_[neg(p)]) ++size_[ci];
    }

    /*
    Learned clauses are dropped strictly newest first, so the index being
    removed is the largest in play and therefore sits at the back of both of
    its occurrence lists
    */
    void dropLearned() {
        int idx = static_cast<int>(learned_.size()) - 1;
        const Binary c = learned_[idx];
        for (Lit l : {c.a, c.b}) {
            std::vector<int>& v = learnedOcc_[l];
            if (!v.empty() && v.back() == idx) v.pop_back();
        }
        learned_.pop_back();
    }

    Lit soleFree(int ci) const {
        for (Lit x : f_->clauses[ci])
            if (!t_->isFalse(x)) return x;
        return -1;
    }

    const Cnf* f_ = nullptr;
    Trail* t_ = nullptr;
    Stats* s_ = nullptr;

    std::vector<std::vector<int>> occ_;
    std::vector<int> size_;       // literals not yet false: the current length
    std::vector<int> satCount_;   // literals currently true
    int applied_ = 0;
    bool unsat_ = false;
    int maxLen_ = 0;

    bool measuring_ = false;
    std::vector<int> touched_;
    std::vector<unsigned> stamp_;
    unsigned mark_ = 0;

    std::vector<Binary> learned_;
    std::vector<std::vector<int>> learnedOcc_;
};
