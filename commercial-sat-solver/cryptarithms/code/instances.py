"""Helper for reading the puzzle collection

Every line of the collection files carries a puzzle with its solution, example:

    COMET+SATURN=URANUS (61078+298354=359432)

Aligning the words with the numbers recovers the digit of every letter, so the
files give a complete assignment
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "instances")

LINE = re.compile(r"^([A-Za-z+\-=]+)\s+\(([\d+\-=]+)\)\s*$")


@dataclass
class Puzzle:
    text: str
    expected: Dict[str, int] = field(default_factory=dict)
    source: str = ""
    words: List[str] = field(default_factory=list)

    @property
    def letters(self) -> List[str]:
        seen: List[str] = []
        for w in self.words:
            for ch in w:
                if ch not in seen:
                    seen.append(ch)
        return seen

    @property
    def n_terms(self) -> int:
        return len(self.words) - 1


def parse_line(line: str, source: str = "") -> Optional[Puzzle]:
    """read one collection line, return None when it is not a puzzle"""
    m = LINE.match(line.strip())
    if not m:
        return None

    puzzle, numbers = m.group(1).upper(), m.group(2)
    words = re.split(r"[+\-=]", puzzle)
    values = re.split(r"[+\-=]", numbers)
    if len(words) != len(values) or not all(words) or not all(values):
        return None

    expected: Dict[str, int] = {}
    for w, v in zip(words, values):
        if len(w) != len(v):
            return None
        for ch, d in zip(w, v):
            d = int(d)
            if expected.get(ch, d) != d:
                return None
            expected[ch] = d

    return Puzzle(text=puzzle, expected=expected, source=source, words=words)


def load_file(path: str) -> List[Puzzle]:
    name = os.path.splitext(os.path.basename(path))[0]
    out = []
    with open(path, errors="ignore") as f:
        for line in f:
            p = parse_line(line, name)
            if p is not None:
                out.append(p)
    return out


def load_all(directory: str = INSTANCE_DIR) -> List[Puzzle]:
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.out"))):
        out += load_file(path)
    return out


def families(directory: str = INSTANCE_DIR) -> List[str]:
    return sorted(os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(directory, "*.out")))

# given by the task requirements
BENCHMARK = ("SO+MANY+MORE+MEN+SEEM+TO+SAY+THAT+THEY+MAY+SOON+TRY+TO+STAY+AT+"
             "HOME+SO+AS+TO+SEE+OR+HEAR+THE+SAME+ONE+MAN+TRY+TO+MEET+THE+TEAM+"
             "ON+THE+MOON+AS+HE+HAS+AT+THE+OTHER+TEN=TESTS")


if __name__ == "__main__":
    puzzles = load_all()
    print(f"{len(families())} files, {len(puzzles)} puzzles")
    by_terms: Dict[int, int] = {}
    for p in puzzles:
        by_terms[p.n_terms] = by_terms.get(p.n_terms, 0) + 1
    for n in sorted(by_terms):
        print(f"  {n} addends: {by_terms[n]}")
