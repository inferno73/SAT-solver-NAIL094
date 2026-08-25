#pragma once

// Tseitin encoding of an NNF AST into CNF, plus the DIMACS writer

#include <algorithm>
#include <ostream>
#include <set>
#include <string>
#include <vector>

#include "formula.hpp"
#include "lit.hpp"

enum class Encoding { Equivalence, Implication };

struct CnfResult {
    int nvars = 0;             // total, input + auxiliary
    std::vector<Clause> clauses;
    Var rootVar = -1;
    Lit rootLit = -1;
    int nInputVars = 0;        // vars [0, nInputVars) are input vars
    std::vector<std::string> varNames;
    Encoding enc = Encoding::Equivalence;
};

// node -> literal: Var leaf gives the positive literal, Not leaf the negative,
// And/Or gate a fresh auxiliary variable
inline CnfResult tseitin(const Ast& ast, Encoding enc) {
    CnfResult r;
    r.enc = enc;
    r.nInputVars = static_cast<int>(ast.varNames.size());
    r.varNames = ast.varNames;

    Var nextVar = r.nInputVars;
    std::vector<Lit> lit(ast.nodes.size(), -1);

    // DIMACS requires clause literals to be distinct and forbids a clause holding
    // both i and -i, so repeated literals are collapsed and tautologies dropped;
    // identical clauses are dropped too, which a gate over two equal children
    // would otherwise produce
    std::set<Clause> seen;
    auto add = [&](Clause c) {
        Clause out;
        for (Lit l : c)
            if (std::find(out.begin(), out.end(), l) == out.end()) out.push_back(l);
        for (Lit l : out)
            if (std::find(out.begin(), out.end(), neg(l)) != out.end()) return;

        Clause key = out;
        std::sort(key.begin(), key.end());
        if (!seen.insert(key).second) return;
        r.clauses.push_back(std::move(out));
    };

    // the parser appends children before their parent, so index order is post-order
    for (size_t i = 0; i < ast.nodes.size(); ++i) {
        const Node& n = ast.nodes[i];
        if (n.kind == NodeKind::Var) { lit[i] = mkLit(n.v, true); continue; }
        if (n.kind == NodeKind::Not) { lit[i] = mkLit(n.v, false); continue; }

        Lit g = mkLit(nextVar++, true);
        Lit a = lit[n.left];
        Lit b = lit[n.right];
        lit[i] = g;

        if (n.kind == NodeKind::And) {
            add({neg(g), a});
            add({neg(g), b});
            if (enc == Encoding::Equivalence) add({g, neg(a), neg(b)});
        } else {
            add({neg(g), a, b});
            if (enc == Encoding::Equivalence) {
                add({g, neg(a)});
                add({g, neg(b)});
            }
        }
    }

    r.rootLit = lit[ast.root];
    r.rootVar = var(r.rootLit);
    r.nvars = nextVar;
    add({r.rootLit});
    return r;
}

// DIMACS output

inline void writeDimacs(std::ostream& out, const CnfResult& r) {
    out << "c Tseitin encoding produced by formula2cnf\n";
    out << "c encoding: "
        << (r.enc == Encoding::Equivalence ? "full equivalences" : "left-to-right implications")
        << "\n";

    out << "c input variables (" << r.nInputVars << "):\n";
    for (int v = 0; v < r.nInputVars; ++v)
        out << "c   " << (v + 1) << " " << r.varNames[v] << "\n";

    int nAux = r.nvars - r.nInputVars;
    out << "c auxiliary gate variables (" << nAux << "): ";
    if (nAux > 0) out << (r.nInputVars + 1) << ".." << r.nvars << "\n";
    else out << "none\n";

    out << "c root: variable " << (r.rootVar + 1)
        << ", asserted as literal " << litToDimacs(r.rootLit) << "\n";

    out << "p cnf " << r.nvars << " " << r.clauses.size() << "\n";
    for (const Clause& c : r.clauses) {
        for (Lit l : c) out << litToDimacs(l) << " ";
        out << "0\n";
    }
}
