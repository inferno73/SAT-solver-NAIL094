#pragma once

// CNF container, DIMACS reader, and input loading for tasks 2-4

#include <algorithm>
#include <fstream>
#include <istream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "formula.hpp"
#include "lit.hpp"
#include "tseitin.hpp"

struct Cnf {
    int nvars = 0;
    std::vector<Clause> clauses;

    // present only when the input was an NNF formula run through Tseitin
    int nInputVars = 0;
    std::vector<std::string> varNames;
};

struct NormalizeStats {
    int tautologiesRemoved = 0;
    int duplicateLitsRemoved = 0;
    int duplicateClausesRemoved = 0;

    bool anything() const {
        return tautologiesRemoved || duplicateLitsRemoved || duplicateClausesRemoved;
    }
};

// Drops repeated literals, tautological clauses and clauses that repeat an
// earlier one. All three are legal in DIMACS input, all three carry no
// information, and a repeated clause would be counted twice by the clause-length
// weights the look-ahead heuristics use in task 4
inline NormalizeStats normalize(Cnf& f) {
    NormalizeStats st;
    std::vector<Clause> kept;
    kept.reserve(f.clauses.size());
    std::set<Clause> seen;

    for (Clause& c : f.clauses) {
        std::sort(c.begin(), c.end());
        size_t before = c.size();
        c.erase(std::unique(c.begin(), c.end()), c.end());
        st.duplicateLitsRemoved += static_cast<int>(before - c.size());

        bool taut = false;
        for (size_t i = 0; i + 1 < c.size(); ++i)
            if (c[i + 1] == neg(c[i])) { taut = true; break; }
        if (taut) { ++st.tautologiesRemoved; continue; }

        // the empty clause must survive even if it appears twice, since it is
        // what makes the formula unsatisfiable
        if (!c.empty() && !seen.insert(c).second) {
            ++st.duplicateClausesRemoved;
            continue;
        }
        kept.push_back(std::move(c));
    }

    f.clauses = std::move(kept);
    return st;
}

inline Cnf readDimacs(std::istream& in) {
    Cnf f;
    bool sawHeader = false;
    int declaredClauses = 0;

    std::string line;
    Clause cur;
    while (std::getline(in, line)) {
        size_t i = line.find_first_not_of(" \t\r");
        if (i == std::string::npos) continue;
        if (line[i] == 'c') continue;

        // SATLIB files end with a '%' line followed by a stray 0; without this
        // the 0 would be read as an extra empty clause and make everything UNSAT
        if (line[i] == '%') break;

        if (line[i] == 'p') {
            std::istringstream ss(line.substr(i + 1));
            std::string fmt;
            if (!(ss >> fmt >> f.nvars >> declaredClauses) || fmt != "cnf")
                throw std::runtime_error("malformed DIMACS header: " + line);
            sawHeader = true;
            continue;
        }

        if (!sawHeader) throw std::runtime_error("clause before the 'p cnf' header");

        std::istringstream ss(line);
        int d;
        while (ss >> d) {
            if (d == 0) { f.clauses.push_back(cur); cur.clear(); continue; }
            if (std::abs(d) > f.nvars)
                throw std::runtime_error("literal " + std::to_string(d) +
                                         " exceeds the declared variable count");
            cur.push_back(litFromDimacs(d));
        }
    }

    if (!sawHeader) throw std::runtime_error("missing 'p cnf' header");
    if (!cur.empty()) throw std::runtime_error("last clause is not 0-terminated");
    return f;
}

inline Cnf fromCnfResult(const CnfResult& r) {
    Cnf f;
    f.nvars = r.nvars;
    f.clauses = r.clauses;
    f.nInputVars = r.nInputVars;
    f.varNames = r.varNames;
    return f;
}

enum class InputFormat { Dimacs, Smtlib };

inline InputFormat formatFromPath(const std::string& path) {
    if (path.size() >= 4 && path.compare(path.size() - 4, 4, ".sat") == 0)
        return InputFormat::Smtlib;
    return InputFormat::Dimacs;
}

inline Cnf loadCnf(std::istream& in, InputFormat fmt, Encoding enc) {
    if (fmt == InputFormat::Dimacs) return readDimacs(in);

    std::ostringstream ss;
    ss << in.rdbuf();
    Ast ast = Parser(ss.str()).parse();
    return fromCnfResult(tseitin(ast, enc));
}
