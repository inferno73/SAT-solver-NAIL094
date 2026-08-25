/* formula2cnf: Tseitin encoding of an NNF formula into DIMACS CNF

 usage: formula2cnf [--equiv|--impl] [input [output]]
   --equiv   full equivalence per gate  g <-> (a op b)   [default]
   --impl    left-to-right only         g -> (a op b)
   input/output default to stdin/stdout
*/
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "formula.hpp"
#include "tseitin.hpp"

namespace {

std::string readAll(std::istream& in) {
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

void usage() {
    std::cerr << "usage: formula2cnf [--equiv|--impl] [input [output]]\n";
}

}  // namespace

int main(int argc, char** argv) {
    Encoding enc = Encoding::Equivalence;
    std::string inPath, outPath;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--equiv") enc = Encoding::Equivalence;
        else if (a == "--impl") enc = Encoding::Implication;
        else if (a == "-h" || a == "--help") { usage(); return 0; }
        else if (!a.empty() && a[0] == '-') { usage(); return 2; }
        else if (inPath.empty()) inPath = a;
        else if (outPath.empty()) outPath = a;
        else { usage(); return 2; }
    }

    std::string src;
    if (inPath.empty()) {
        src = readAll(std::cin);
    } else {
        std::ifstream f(inPath);
        if (!f) { std::cerr << "cannot open " << inPath << "\n"; return 1; }
        src = readAll(f);
    }

    CnfResult result;
    try {
        Ast ast = Parser(src).parse();
        result = tseitin(ast, enc);
    } catch (const std::exception& e) {
        std::cerr << "parse error: " << e.what() << "\n";
        return 1;
    }

    if (outPath.empty()) {
        writeDimacs(std::cout, result);
    } else {
        std::ofstream f(outPath);
        if (!f) { std::cerr << "cannot open " << outPath << "\n"; return 1; }
        writeDimacs(f, result);
    }
    return 0;
}
