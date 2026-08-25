"""Timing and call counting for the backbone experiments

Measuered metrics:
    the number of SAT calls (minimise these)
    times of execution
"""

from __future__ import annotations

import glob
import hashlib
import os
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

from backbone import ALGORITHMS, read_dimacs, backbones
from verify import cbs_expected_size

BENCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..", "benchmarks_allSAT")
SOLVER = "cadical153"


@dataclass
class Row:
    family: str
    instance: str
    n_vars: int
    n_clauses: int
    algorithm: str
    solver: str
    order: str
    backbone_size: Optional[int] = None
    backbone_hash: Optional[str] = None
    expected_size: Optional[int] = None
    calls: Optional[int] = None
    free: Optional[int] = None
    rounds: Optional[int] = None
    load_time: Optional[float] = None
    solve_time: Optional[float] = None
    error: Optional[str] = None

    @property
    def naive_calls(self) -> int:
        return 2 * self.n_vars

    @property
    def saving(self) -> Optional[float]:
        if self.calls is None:
            return None
        return 1.0 - self.calls / self.naive_calls

    @property
    def matches_expected(self) -> Optional[bool]:
        if self.expected_size is None or self.backbone_size is None:
            return None
        return self.backbone_size == self.expected_size


def families() -> List[str]:
    return sorted(d for d in os.listdir(BENCH_DIR)
                  if os.path.isdir(os.path.join(BENCH_DIR, d)) and not d.startswith("_"))


def instances(family: str) -> List[str]:
    return sorted(glob.glob(os.path.join(BENCH_DIR, family, "*.cnf")))


def run_one(path: str, family: str, algorithm: str,
            solver: str = SOLVER, order: str = "index") -> Row:
    cnf = read_dimacs(path)
    name = os.path.basename(path)
    row = Row(family=family, instance=name, n_vars=cnf.n_vars,
              n_clauses=cnf.n_clauses, algorithm=algorithm, solver=solver,
              order=order, expected_size=cbs_expected_size(family))

    try:
        r = backbones(cnf, algorithm, solver, order)
    except Exception as e:
        row.error = f"{type(e).__name__}: {e}"
        return row

    row.backbone_size = r.size
    # fingerprint of the literals themselves, so agreement between the two
    # algorithms can be checked as set equality and not only as equal counts
    row.backbone_hash = hashlib.sha1(
        ",".join(str(l) for l in sorted(r.backbone)).encode()
    ).hexdigest()[:16]
    row.calls = r.calls
    row.free = r.free
    row.rounds = r.rounds
    row.load_time = r.load_time
    row.solve_time = r.solve_time
    return row


def sweep(selected: Optional[List[str]] = None,
          algorithms: Optional[List[str]] = None,
          solver: str = SOLVER,
          order: str = "index",
          verbose: bool = True) -> List[Row]:
    rows: List[Row] = []
    for family in (selected or families()):
        for path in instances(family):
            for algorithm in (algorithms or list(ALGORITHMS)):
                r = run_one(path, family, algorithm, solver, order)
                rows.append(r)
                if verbose:
                    if r.error:
                        print(f"  {family:<24} {r.instance:<26} {algorithm:<11} "
                              f"{r.error}", flush=True)
                    else:
                        print(f"  {family:<24} {r.instance:<26} {algorithm:<11} "
                              f"{r.backbone_size:>4} bb  {r.calls:>5} calls "
                              f"(naive {r.naive_calls})  {r.solve_time:6.3f}s",
                              flush=True)
    return rows


def to_records(rows: List[Row]) -> List[dict]:
    out = []
    for r in rows:
        d = asdict(r)
        d["naive_calls"] = r.naive_calls
        d["saving"] = r.saving
        d["matches_expected"] = r.matches_expected
        out.append(d)
    return out


if __name__ == "__main__":
    t0 = time.perf_counter()
    rs = sweep(selected=["uf20-91", "CBS_k3_n100_m403_b50"])
    print(f"\n{len(rs)} runs in {time.perf_counter()-t0:.1f}s")
