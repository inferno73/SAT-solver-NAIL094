#pragma once

/*
Lazy 2 watched literals

alternative to PropAdjacency in dpll.hpp: only the propagation differs
(so same engine interface, same Solver, same search, )

Every clause of length >= 2 watches two of its literals, and watchList[l] holds
the clauses currently watching l
A clause is inspected only when one of its two watched literals becomes false,
and backtracking moves no watches at all, which is what is measured against
adjacency lists

Unit and empty clauses cannot carry two watches and are handled at init instead
*/

#include <array>
#include <vector>

#include "dpll.hpp"
#include "cnf.hpp"
#include "lit.hpp"

class PropWatched {
public:
    void init(const Cnf& f, Trail& t, Stats& s) {
        f_ = &f;
        t_ = &t;
        s_ = &s;

        watchList_.assign(2 * f.nvars, {});
        watch_.assign(f.clauses.size(), {-1, -1});

        // watches are placed before anything is assigned, so no watched literal
        // starts out false
        for (size_t ci = 0; ci < f.clauses.size(); ++ci) {
            const Clause& c = f.clauses[ci];
            if (c.size() < 2) continue;
            watch_[ci] = {c[0], c[1]};
            watchList_[c[0]].push_back(static_cast<int>(ci));
            watchList_[c[1]].push_back(static_cast<int>(ci));
        }

        for (const Clause& c : f.clauses) {
            if (c.empty()) { unsat_ = true; continue; }
            if (c.size() != 1) continue;
            if (t.isFalse(c[0])) unsat_ = true;      // contradictory unit clauses
            else if (t.isUndef(c[0])) t.enqueue(c[0]);
        }
    }

    bool trivialUnsat() const { return unsat_; }

    bool propagate() {
        while (!t_->queueEmpty()) {
            Lit p = t_->dequeue();
            Lit falsi = neg(p);                  // falsi has just become false
            std::vector<int>& ws = watchList_[falsi];

            size_t i = 0, j = 0;
            while (i < ws.size()) {
                int ci = ws[i++];
                const Clause& c = f_->clauses[ci];
                ++s_->clausesChecked;

                Lit other = (watch_[ci][0] == falsi) ? watch_[ci][1] : watch_[ci][0];
                if (t_->isTrue(other)) { ws[j++] = ci; continue; }

                Lit repl = -1;
                for (Lit x : c) {
                    if (x == falsi || x == other) continue;
                    if (!t_->isFalse(x)) { repl = x; break; }
                }

                if (repl != -1) {
                    // hand the clause over to the replacement's list and drop it
                    // from this one
                    if (watch_[ci][0] == falsi) watch_[ci][0] = repl;
                    else watch_[ci][1] = repl;
                    watchList_[repl].push_back(ci);
                    continue;
                }

                ws[j++] = ci;
                if (t_->isUndef(other)) {
                    t_->enqueue(other);
                    ++s_->propagations;
                } else {
                    while (i < ws.size()) ws[j++] = ws[i++];
                    ws.resize(j);
                    return false;
                }
            }
            ws.resize(j);
        }
        return true;
    }

    void onUnassign(Lit) {}

private:
    const Cnf* f_ = nullptr;
    Trail* t_ = nullptr;
    Stats* s_ = nullptr;

    std::vector<std::vector<int>> watchList_;
    std::vector<std::array<Lit, 2>> watch_;
    bool unsat_ = false;
};
