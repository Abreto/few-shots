#!/usr/bin/env python3
"""Verifier for p003: lower bounds for the Ramsey number R(4,6).

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON strings only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: a simple graph on n vertices, given by its adjacency matrix, with no clique of size 4 and no
independent set of size 6. Score = n; such a graph proves R(4,6) >= n + 1.

Method: vertices are bit positions in Python integers. Both checks use one depth-first clique
search, pruned by candidate count: for a 4-clique in the graph, then for a 6-clique in the
complement (an independent 6-set). Both searches are exhaustive
and stop at the first witness. The work stays small for every input: the K4 search visits each
vertex, edge and triangle at most once; in the second search (run only on K4-free graphs) a top-level
branch at vertex u fails only if u lies in no independent 6-set, and then the non-neighbours of u
induce a K4-free graph with no independent 5-set, so there are at most R(4,5) - 1 = 24 of them
and the branch has at most 1 + 24 + C(24,2) + C(24,3) + C(24,4) nodes. Inside the first
successful branch the same argument bounds each failing sub-branch by R(4,4) - 1 = 17 candidates.

Canonical form: for a valid graph, the lexicographically smallest relabelled adjacency matrix over
all leaves of an individualisation-refinement search tree (colour refinement, first non-singleton
cell, every vertex of that cell tried). The tree and the work it takes depend on the graph
structure alone, so isomorphic graphs get the same form. If the full search would need more than
CANON_BUDGET work units (highly symmetric graphs), the matrix is hashed in its given labelling
instead, marked as such; this decision is also the same for isomorphic graphs.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

CERT_NAME = "certificate.json"
MAX_DEPTH = 8                 # maximum JSON nesting depth
MAX_INT_DIGITS = 18           # maximum digits in a single integer
MAX_VERTICES = 64             # R(4,6) <= 41 is proved, so no valid graph has more than 40 vertices
CLIQUE = 4                    # forbidden clique size
INDEPENDENT = 6               # forbidden independent set size
CANON_BUDGET = 20_000_000     # work budget of the canonical labelling search (neighbour counts)


class Invalid(Exception):
    """The certificate is invalid. The message is shown verbatim, so it must not contain input strings."""


# ---------- configuration ----------

def find_problem_toml() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here / "problem.toml", here.parent / "problem.toml"):
        if cand.is_file():
            return cand
    raise FileNotFoundError("problem.toml not found")


def load_config(path: Path | None = None) -> dict:
    with open(path or find_problem_toml(), "rb") as f:
        data = tomllib.load(f)
    s = data["params"]["clique"]
    t = data["params"]["independent"]
    limit = data["max_certificate_bytes"]
    if type(s) is not int or s != CLIQUE or type(t) is not int or t != INDEPENDENT:
        raise ValueError("params.clique must be 4 and params.independent must be 6")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"clique": s, "independent": t, "max_certificate_bytes": limit}


# ---------- reading and parsing (shared) ----------

def read_certificate(shot_dir: str | os.PathLike, limit: int) -> bytes:
    path = Path(shot_dir) / CERT_NAME
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise Invalid("certificate.json is missing") from None
    except OSError:
        raise Invalid("cannot read certificate.json (symbolic links are not allowed)") from None
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise Invalid("certificate.json is not a regular file")
        if st.st_size > limit:
            raise Invalid(f"certificate.json exceeds the size limit of {limit} bytes")
        data = f.read(limit + 1)
    if len(data) > limit:
        raise Invalid(f"certificate.json exceeds the size limit of {limit} bytes")
    return data


def check_depth(text: str, limit: int = MAX_DEPTH) -> None:
    depth = 0
    in_str = esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise Invalid(f"JSON is nested deeper than {limit} levels")
        elif ch in "]}":
            depth -= 1


def _no_float(_s: str):
    raise Invalid("fractional or exponent numbers are not allowed")


def _no_constant(_s: str):
    raise Invalid("NaN and Infinity are not allowed")


def _bounded_int(s: str) -> int:
    if len(s.lstrip("-")) > MAX_INT_DIGITS:
        raise Invalid(f"an integer has more than {MAX_INT_DIGITS} digits")
    return int(s)


def _unique_keys(pairs: list) -> dict:
    out: dict = {}
    for k, v in pairs:
        if k in out:
            raise Invalid("a JSON object has duplicate keys")
        out[k] = v
    return out


def strict_json(data: bytes):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Invalid("certificate.json must be UTF-8 text") from None
    check_depth(text)
    try:
        return json.loads(
            text,
            parse_float=_no_float,
            parse_int=_bounded_int,
            parse_constant=_no_constant,
            object_pairs_hook=_unique_keys,
        )
    except RecursionError:
        raise Invalid("JSON is nested too deeply") from None
    except ValueError:
        raise Invalid("certificate.json is not valid JSON") from None


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


# ---------- problem rule ----------

def bits(mask: int) -> list[int]:
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def parse_graph(rows) -> list[int]:
    """Validates the adjacency matrix and returns the neighbourhoods as bit masks."""
    if not isinstance(rows, list) or not rows:
        raise Invalid("adjacency must be a non-empty list of rows")
    n = len(rows)
    if n > MAX_VERTICES:
        raise Invalid(f"at most {MAX_VERTICES} vertices are accepted")
    adj = []
    for i, row in enumerate(rows):
        if type(row) is not str or len(row) != n or not frozenset("01").issuperset(row):
            raise Invalid(f"row {i} must be a string of exactly {n} characters 0 or 1")
        if row[i] != "0":
            raise Invalid(f"the diagonal must be 0 (row {i} has a loop)")
        adj.append(int(row[::-1], 2))  # character j is bit j
    for i in range(n):
        for j in bits(adj[i]):
            if not adj[j] >> i & 1:
                raise Invalid(f"the matrix is not symmetric (rows {i} and {j})")
    return adj


def find_clique(adj: list[int], size: int) -> list[int] | None:
    """Exhaustive search for a clique of the given size; returns its vertices or None."""

    def extend(chosen: list[int], cand: int) -> list[int] | None:
        need = size - len(chosen)
        if need == 0:
            return chosen
        while cand and cand.bit_count() >= need:
            low = cand & -cand
            v = low.bit_length() - 1
            cand ^= low
            found = extend(chosen + [v], cand & adj[v])
            if found is not None:
                return found
        return None

    return extend([], (1 << len(adj)) - 1)


def complement(adj: list[int]) -> list[int]:
    full = (1 << len(adj)) - 1
    return [full & ~a & ~(1 << i) for i, a in enumerate(adj)]


# ---------- canonical labelling ----------

class _OverBudget(Exception):
    """The canonical labelling search exceeded CANON_BUDGET work units."""


def refine(adj: list[int], cells: list[int], budget: list[int]) -> list[int]:
    """Colour refinement of an ordered partition (cells as bit masks) until it is equitable.
    Each round splits every cell by the vector of neighbour counts into all current cells,
    sub-cells ordered by that vector, so the result depends only on the structure.
    budget[0] is decreased by one unit per neighbour count."""
    while True:
        new = []
        budget[0] -= len(adj) * len(cells)
        if budget[0] < 0:
            raise _OverBudget
        for cell in cells:
            vs = bits(cell)
            if len(vs) == 1:
                new.append(cell)
                continue
            groups: dict = {}
            for v in vs:
                key = tuple((adj[v] & c).bit_count() for c in cells)
                groups[key] = groups.get(key, 0) | (1 << v)
            for key in sorted(groups):
                new.append(groups[key])
        if len(new) == len(cells):
            return new
        cells = new


def canonical_form(adj: list[int]) -> tuple[str, list[str]]:
    n = len(adj)
    best: list | None = None
    budget = [CANON_BUDGET]

    def leaf_rows(cells: list[int]) -> list[int]:
        order = [c.bit_length() - 1 for c in cells]
        pos = [0] * n
        for k, v in enumerate(order):
            pos[v] = k
        return [sum(1 << pos[u] for u in bits(adj[v])) for v in order]

    def search(cells: list[int]) -> None:
        nonlocal best
        cells = refine(adj, cells, budget)
        if len(cells) == n:
            budget[0] -= n * n
            if budget[0] < 0:
                raise _OverBudget
            rows = leaf_rows(cells)
            if best is None or rows < best:
                best = rows
            return
        k = next(i for i, c in enumerate(cells) if c & (c - 1))
        target = cells[k]
        for v in bits(target):
            search(cells[:k] + [1 << v, target & ~(1 << v)] + cells[k + 1:])

    try:
        search([(1 << n) - 1])
    except _OverBudget:
        best = None
    if best is not None:
        return "canonical", [format(r, f"0{n}b")[::-1] for r in best]
    return "given", [format(a, f"0{n}b")[::-1] for a in adj]


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    if not isinstance(cert, dict) or set(cert) != {"adjacency"}:
        raise Invalid('the certificate must be a JSON object with the single key "adjacency"')
    adj = parse_graph(cert["adjacency"])
    k = find_clique(adj, cfg["clique"])
    if k is not None:
        raise Invalid("vertices " + ", ".join(map(str, k)) + f" form a clique of size {cfg['clique']}")
    s = find_clique(complement(adj), cfg["independent"])
    if s is not None:
        raise Invalid("vertices " + ", ".join(map(str, s)) + f" form an independent set of size {cfg['independent']}")
    labelling, rows = canonical_form(adj)
    return Fraction(len(adj)), {"labelling": labelling, "adjacency": rows}


# ---------- entry point ----------

def verify_bytes(data: bytes, cfg: dict) -> dict:
    cert = strict_json(data)
    score, canon = check_certificate(cert, cfg)
    return {
        "valid": True,
        "score": str(score),
        "canonical_hash": canonical_hash(canon),
        "message": "ok",
    }


def verify_dir(shot_dir: str | os.PathLike, cfg: dict) -> dict:
    try:
        return verify_bytes(read_certificate(shot_dir, cfg["max_certificate_bytes"]), cfg)
    except Invalid as e:
        return invalid(str(e))
    except RecursionError:
        return invalid("JSON is nested too deeply")
    except MemoryError:
        return invalid("input is too large")
    except Exception:  # no traceback, to avoid leaking details
        return invalid("internal verifier error")


def invalid(message: str) -> dict:
    return {"valid": False, "score": None, "canonical_hash": None, "message": message}


def emit(result: dict) -> None:
    line = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.buffer.write(line.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        emit(invalid("usage: python verify.py <shot_dir>"))
        return 2
    try:
        cfg = load_config()
    except Exception:
        emit(invalid("verifier configuration error"))
        return 2
    emit(verify_dir(argv[1], cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
