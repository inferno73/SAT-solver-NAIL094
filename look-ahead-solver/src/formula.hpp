#pragma once


/*
NNF formula: AST, tokenizer and recursive-descent parser

grammar:
  <formula> ::= '(' 'and' <formula> <formula> ')'
               | '(' 'or'  <formula> <formula> ')'
               | '(' 'not' <variable> ')'
               | <variable>
*/
#include <cctype>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "lit.hpp"

// AST

enum class NodeKind { Var, Not, And, Or };

struct Node {
    NodeKind kind;
    Var v = -1;          // Var/not: the referenced input variable
    int left = -1;       // And/or: indices into Ast::nodes
    int right = -1;
};

struct Ast {
    std::vector<Node> nodes;
    int root = -1;

    // input variable names in order of first appearance, index == Var
    std::vector<std::string> varNames;
    std::map<std::string, Var> varIds;

    Var internVar(const std::string& name) {
        auto it = varIds.find(name);
        if (it != varIds.end()) return it->second;
        Var v = static_cast<Var>(varNames.size());
        varNames.push_back(name);
        varIds.emplace(name, v);
        return v;
    }

    int addNode(Node n) {
        nodes.push_back(n);
        return static_cast<int>(nodes.size()) - 1;
    }
};

[[noreturn]] inline void fail(const std::string& msg, int pos) {
    throw std::runtime_error(msg + " at offset " + std::to_string(pos));
}

// Tokenizer

enum class TokKind { LParen, RParen, Ident, End };

struct Token {
    TokKind kind;
    std::string text;   // for Ident
    int pos;            // byte offset, for error messages
};

class Lexer {
public:
    explicit Lexer(std::string src) : src_(std::move(src)) {}

    Token next() {
        while (i_ < src_.size() && std::isspace(static_cast<unsigned char>(src_[i_]))) ++i_;

        int pos = static_cast<int>(i_);
        if (i_ >= src_.size()) return {TokKind::End, "", pos};

        char c = src_[i_];
        if (c == '(') { ++i_; return {TokKind::LParen, "(", pos}; }
        if (c == ')') { ++i_; return {TokKind::RParen, ")", pos}; }

        if (std::isalpha(static_cast<unsigned char>(c))) {
            size_t start = i_;
            while (i_ < src_.size() && std::isalnum(static_cast<unsigned char>(src_[i_]))) ++i_;
            return {TokKind::Ident, src_.substr(start, i_ - start), pos};
        }

        fail(std::string("unexpected character '") + c + "'", pos);
    }

private:
    std::string src_;
    size_t i_ = 0;
};

// Parser, recursive descent, throws std::runtime_error on malformed or non-NNF input

class Parser {
public:
    explicit Parser(std::string src) : lex_(std::move(src)) {}

    Ast parse() {
        advance();
        ast_.root = parseFormula();
        if (cur_.kind != TokKind::End) fail("trailing input after the formula", cur_.pos);
        return std::move(ast_);
    }

private:
    void advance() { cur_ = lex_.next(); }

    // consumes an identifier used as a variable
    Var expectVarName() {
        if (cur_.kind != TokKind::Ident) fail("expected a variable name", cur_.pos);
        Var v = ast_.internVar(cur_.text);
        advance();
        return v;
    }

    void expectRParen() {
        if (cur_.kind != TokKind::RParen) fail("expected ')'", cur_.pos);
        advance();
    }

    int parseFormula() {
        if (cur_.kind == TokKind::Ident) {
            Node n{NodeKind::Var};
            n.v = expectVarName();
            return ast_.addNode(n);
        }
        if (cur_.kind != TokKind::LParen) fail("expected a formula", cur_.pos);

        advance();
        if (cur_.kind != TokKind::Ident) fail("expected 'and', 'or' or 'not'", cur_.pos);
        std::string op = cur_.text;
        int opPos = cur_.pos;
        advance();

        if (op == "not") {
            if (cur_.kind != TokKind::Ident)
                fail("'not' may only be applied to a variable (input is not in NNF)", cur_.pos);
            Node n{NodeKind::Not};
            n.v = expectVarName();
            expectRParen();
            return ast_.addNode(n);
        }
        if (op == "and" || op == "or") {
            Node n{op == "and" ? NodeKind::And : NodeKind::Or};
            n.left = parseFormula();
            n.right = parseFormula();
            if (cur_.kind != TokKind::RParen)
                fail("'" + op + "' takes exactly two arguments", cur_.pos);
            advance();
            return ast_.addNode(n);
        }
        fail("unknown connective '" + op + "'", opPos);
    }

    Lexer lex_;
    Token cur_{TokKind::End, "", 0};
    Ast ast_;
};
