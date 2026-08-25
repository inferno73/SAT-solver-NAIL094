"""Timing helper for the n-queens experiments

Each solve runs in a child process so the time budget can be enforced by
killing it, PySAT cannot interrupt CaDiCaL from inside the process
"""

from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from nqueens import decode, encode, verify

SOLVERS = ["cadical153", "glucose4", "minisat22"]
BUDGET = 60.0
ENCODE_BUDGET = 600.0


@dataclass
class Result:
    n: int
    solver: str
    sat: Optional[bool] = None
    encode_time: Optional[float] = None   # Python builds the clause lists
    load_time: Optional[float] = None     # C solver ingests them
    solve_time: Optional[float] = None    # search
    n_vars: Optional[int] = None
    n_clauses: Optional[int] = None
    verified: Optional[bool] = None
    timed_out: bool = False
    error: Optional[str] = None
    restarts: Optional[int] = None
    conflicts: Optional[int] = None
    decisions: Optional[int] = None
    propagations: Optional[int] = None

    @property
    def total_time(self) -> Optional[float]:
        parts = [self.encode_time, self.load_time, self.solve_time]
        if any(p is None for p in parts):
            return None
        return sum(parts)

    @property
    def solver_time(self) -> Optional[float]:
        """Everything the solver does, loading plus search"""
        if self.load_time is None or self.solve_time is None:
            return None
        return self.load_time + self.solve_time


def _worker(n: int, solver_name: str, queue) -> None:
    """Encode and solve in a child process, reporting after each phase

    The encode message lets the parent start a fresh clock for the solve,
    so the budget applies to solving alone
    """
    from pysat.solvers import Solver

    t0 = time.perf_counter()
    enc = encode(n)
    encode_time = time.perf_counter() - t0

    queue.put(
        {
            "phase": "encoded",
            "encode_time": encode_time,
            "n_vars": enc.n_vars,
            "n_clauses": enc.n_clauses,
        }
    )

    t0 = time.perf_counter()
    solver = Solver(name=solver_name, bootstrap_with=enc.clauses)
    load_time = time.perf_counter() - t0

    del enc

    t0 = time.perf_counter()
    sat = solver.solve()
    solve_time = time.perf_counter() - t0

    model = solver.get_model() if sat else None

    try:
        stats = solver.accum_stats()
    except Exception:
        stats = {}

    solver.delete()

    queue.put(
        {
            "phase": "solved",
            "sat": bool(sat),
            "load_time": load_time,
            "solve_time": solve_time,
            "verified": verify(decode(model, n), n) if sat else None,
            "restarts": stats.get("restarts"),
            "conflicts": stats.get("conflicts"),
            "decisions": stats.get("decisions"),
            "propagations": stats.get("propagations"),
        }
    )


def _kill(proc) -> None:
    if proc.is_alive():
        proc.terminate()
    proc.join()


def run_one(
    n: int,
    solver_name: str,
    budget: float = BUDGET,
    encode_budget: float = ENCODE_BUDGET,
) -> Result:
    """Run one instance, killing the child if solving exceeds the budget

    Encoding gets its own generous budget and is not counted against the
    solve budget, a child that dies (out of memory) leaves the queue empty
    """
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=_worker, args=(n, solver_name, queue))
    proc.start()

    try:
        enc_msg = queue.get(timeout=encode_budget)
    except Exception:
        _kill(proc)
        return Result(
            n=n,
            solver=solver_name,
            error=f"encoding failed or timed out (exit {proc.exitcode})",
        )

    try:
        solve_msg = queue.get(timeout=budget)
    except Exception:
        _kill(proc)
        return Result(
            n=n,
            solver=solver_name,
            encode_time=enc_msg["encode_time"],
            n_vars=enc_msg["n_vars"],
            n_clauses=enc_msg["n_clauses"],
            timed_out=True,
        )

    _kill(proc)
    return Result(
        n=n,
        solver=solver_name,
        encode_time=enc_msg["encode_time"],
        n_vars=enc_msg["n_vars"],
        n_clauses=enc_msg["n_clauses"],
        sat=solve_msg["sat"],
        load_time=solve_msg["load_time"],
        solve_time=solve_msg["solve_time"],
        verified=solve_msg["verified"],
        restarts=solve_msg["restarts"],
        conflicts=solve_msg["conflicts"],
        decisions=solve_msg["decisions"],
        propagations=solve_msg["propagations"],
    )


def sweep(
    ns: List[int],
    solvers: List[str] = SOLVERS,
    budget: float = BUDGET,
    verbose: bool = True,
) -> List[Result]:
    """Run every (n, solver) pair, retiring a solver once it times out"""
    results: List[Result] = []
    live = set(solvers)

    for n in ns:
        for name in solvers:
            if name not in live:
                continue

            r = run_one(n, name, budget)
            results.append(r)

            if verbose:
                if r.timed_out:
                    print(f"  n={n:4d} {name:<12} timed out at {budget:.0f}s")
                elif r.error:
                    print(f"  n={n:4d} {name:<12} {r.error}")
                else:
                    print(
                        f"  n={n:4d} {name:<12} encode={r.encode_time:7.3f}s "
                        f"load={r.load_time:7.3f}s solve={r.solve_time:7.3f}s "
                        f"verified={r.verified}"
                    )

            if r.timed_out or r.error:
                live.discard(name)

        if not live:
            break

    return results


def max_n_within(
    results: List[Result],
    budget: float = BUDGET,
    metric: str = "solver",
) -> Dict[str, int]:
    """Largest n each solver handled inside the budget

    metric "solve" is search only, "solver" adds clause loading,
    "total" adds the Python encoding as well
    """
    pick = {
        "solve": lambda r: r.solve_time,
        "solver": lambda r: r.solver_time,
        "total": lambda r: r.total_time,
    }[metric]

    best: Dict[str, int] = {}
    for r in results:
        if r.timed_out or r.error:
            continue
        t = pick(r)
        if t is not None and t <= budget:
            best[r.solver] = max(best.get(r.solver, 0), r.n)
    return best


def non_monotone(results: List[Result]) -> List[dict]:
    """Pairs of consecutive n where a larger board solved faster"""
    found = []
    for name in {r.solver for r in results}:
        runs = sorted(
            (r for r in results if r.solver == name and r.solve_time is not None),
            key=lambda r: r.n,
        )
        for prev, cur in zip(runs, runs[1:]):
            if cur.solve_time < prev.solve_time:
                found.append(
                    {
                        "solver": name,
                        "n_small": prev.n,
                        "t_small": prev.solve_time,
                        "n_large": cur.n,
                        "t_large": cur.solve_time,
                        "speedup": prev.solve_time / cur.solve_time,
                    }
                )
    return sorted(found, key=lambda d: -d["speedup"])


def to_records(results: List[Result]) -> List[dict]:
    """Flat dicts for a DataFrame, with total_time added"""
    out = []
    for r in results:
        d = asdict(r)
        d["solver_time"] = r.solver_time
        d["total_time"] = r.total_time
        out.append(d)
    return out


if __name__ == "__main__":
    for r in sweep(ns=[8, 16, 32, 64]):
        pass
