#pragma once

// literals
// 2*v positive, 2*v+1 negative
// vars are 0-based internally, 1-based in DIMACS

#include <cstdlib>
#include <vector>

using Var = int;
using Lit = int;

inline Lit mkLit(Var v, bool positive) { return 2 * v + (positive ? 0 : 1); }
inline Lit neg(Lit l) { return l ^ 1; }
inline Var var(Lit l) { return l >> 1; }
inline bool sign(Lit l) { return (l & 1) == 0; }  // true = positive

inline int litToDimacs(Lit l) { return sign(l) ? (var(l) + 1) : -(var(l) + 1); }
inline Lit litFromDimacs(int d) { return mkLit(std::abs(d) - 1, d > 0); }

using Clause = std::vector<Lit>;
