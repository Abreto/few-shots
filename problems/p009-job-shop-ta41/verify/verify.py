#!/usr/bin/env python3
"""Verifier for p009: Taillard's job-shop instance ta41 (30 jobs, 20 machines), minimum makespan.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: the certificate gives, for each machine, the order in which the 30 jobs are processed on it.
Together with the fixed route of each job this defines the disjunctive graph; it must be acyclic.
Every operation starts as early as its job predecessor and its machine predecessor allow (the
semi-active schedule). Score = makespan, the completion time of the last operation. Lower is better.

Instance data (INSTANCE below): ta41 of Taillard (1993) in the usual two-integer-per-operation
format. Line 1 is "jobs machines"; line 2 + j lists job j's operations in route order as
"machine duration" pairs, machines numbered 0..19 (Taillard's machine k + 1 is machine k here),
jobs numbered 0..29 (Taillard's job j + 1). The text is the file instances/ta41 of the JSPLIB
repository with trailing spaces removed; its sha256 is checked before use. test_verify.py
regenerates the instance from Taillard's published seeds (time seed 1841414609, machine seed
1357882888) and checks that it is identical.
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
N_JOBS = 30
N_MACHINES = 20

INSTANCE = """\
30 20
 5 59 13 72  3 92 15 35 19 17  9 48 10 57  6 18 12 55  4 51  2  8 14 68  8 90  7 39 16 79 11 40  0 66 17 55 18 62  1 66
13 42  2 60 15 52 12 14  4 83  9 95  3 36  7 28  5  4  0 31  8 14 14 23  6 71 19 95  1 69 10 17 18 13 17 23 16 78 11 51
 8 93  5 12  2 34 18 32 17 59 14 73  0 46  4 25 11 82  3 90 16 70  7 27  6 82  1 85 12 40 15 35 10 61 19 92 13 98  9 53
13 31  8 95  0 36 11 61  3 92 14 24  7 70  4 15 18 76  6 50 19 18  5 30  2 93  9 62 10 83 15 16 17 75  1 29 12 35 16 31
 8 27  6 10  2 93 13 26 16 64 11 70 15 16 12 48  9 46  4 37 19 89 17 83  5 71  3 72  7 45  1 73 10 97 18 12 14 57  0 62
 1  9 13 16 10 75  0 21  2 49 12 97 19  5  5 20 17 26 16 50 18 26  4 20 15  8  8 96  7 50  6 84 14  7 11 52  3 73  9 43
 2 20  3 76 16  3 17 45 10 53 15  6 13 83 12 77  9 21 19 52  8 32  0 27 18 93 11 81 14 78  1  6  5 93  7 60  4 12  6 35
12 41 10 59 17 37  4 89  3 87 11 32  2 98 19 24  8 30  9 84 13 49 14 84  7 44 18 16 15 43  6 65 16 44  1 83  5 71  0 71
10 46 14 36  3 60  0 59  7 53 17 58 19  8  2 33 11 70 16 93  6 38  4  5 18 75  1 23 13 98  5 90 12 18 15 62  8  4  9 56
 0 27  2 31  3 45  9 57  8 79 12 14 16 82 13 96  4  4 10 17  6 46 19  3 15  7  1 42  5 24 17 86  7 67 14 79 18 43 11 17
 1 72  4 54  0 51 10 87 15 52 11  4 16 35  9 62 19 15 13 45 14 84  8 65  6 85 17 49 18 98 12  5  2 81  7  8  3 72  5 33
 6 31  5 86  9 46 10  3  0 63  2 58  3 81 12  7 11 54  7 39 13 46  8 92 19 96 14 57 16 40  4 49 17 57  1 86 18 20 15 91
13 35 19  5 11 43  5 84  2 77 15 20 14 84  4 70  3 79  6 52 10 92  1 34 12 39 18 30  9 65  7 11 16 88 17 32  8 80  0  2
10 59  3 36  4 72  9 46 17 48  8 72  0 76 19 48  2 69 11 62 12 30  1 48 18  7 15 89  5 37 16 49  6 30 14 52 13  1  7 56
 4 18 14 35  8 61 15 23 11 46  9 12 10 38  1 59 17 50 16 75  5 60 18 57  6 63 13 89 19 71 12 52  7 83  3 86  2 81  0 98
 4 33  9 14 18 19 19 84  3 69 17 59 15  2 16 83  5 12  8 21 11 73 14 83  0 26  2 94  1 65 12 98  6 83 10 45 13 40  7 89
17 63 10 72 13 80 19  2  0 94 12 11 14 25 18 10  2 90  5 73 11 20 16 92  7 11  4 85  8 63  1 97 15 38  6 13  9 42  3 59
19 95 13  4  9 95  3  6  6 67 17 30  7 88 16 26  5 57 14 61 15  9 18 35  0 23  2 47  1 46 12 96  8 19 11 54 10 75  4 11
 9 64 11 79 17 87 13 91  3  2  1 61 10 31 16 85  0 53  5 77  7 25  6 94  4 43  2 13 18 40 15 59 14  3 19 80  8  7 12 98
17 56  8 12 13 74  7 42  4 98  0 75  6 18  9 98 16 20 18 72 11 34  5 74 10 10 12 98  2 12 19 95 15 33 14 69  3 93  1 81
17 73  2 38  7 25 16 92  6 38 12 91 14 95  9  2  3 79 18 41  0  3  4 99  5 83  8 18  1 12 19 71 10  4 11 66 15 20 13 53
 0 61  7 24 16 24 12 22  3 85  6 56 19 98  2  5 10 29  9 73 18 27  8 99 13  4  5 99 11 63  4 25 15 61  1 51 17 84 14 30
10  5 18 17  4 40  5 88 12 30  6  3  9  1  1 96 11  9 13 94  8 69  7 72 17 90  0 14  2 41 14 50 19 69 15 38 16 12  3  1
14 55  0 19  5 61 11 61  9 97 19 76 10 38 15 69  2 24  3 62  4 24 18 94 17  3 13  5 12 84  7 43  6 73  1 76 16 47  8 91
11 85  6 98 18 68 14 57 16 63  0 58 17 74 10 52  9 59  2 47  7 73  4 79 19 48  5 38  8 88  1 85 12  4 15 44 13 37  3 75
18 44 13 32 10 38 12 93  1 40  9 56  0 80  7 90  2 74  5 82 16 59  6 91 17 40  8 26 14 74  3  7  4 49 11 88 19 60 15 35
14 75  2 73 19 13 10  4 11 77 16  5  9 57  7 98 15 60  1 99  5 12 13 14  4 25  8 86 18 13  0 93  3 41 12  1  6 53 17 54
 0 33 18 75  8 97  9 31 12 84 17 49 16 51 19 30 15 62 11 67  2 84 13 45  3 48 10 62  5 64  7 87  6 14  4 76  1 42 14 71
18 74 11 98  9 11 14 96  4 39  0 31 16 54  3 49  8 51  6 40 13 21 15 19  7 44  2 76 10 64 12 43 19  9 17 30  5 66  1 17
16 31  3 77  9 92  6 27  2 71 18 82 11 36  1 33  4 48  0 91  5 49  7 39 12 91 15 47  8 74 14 17 13 62 19 28 10 91 17 58
"""
INSTANCE_SHA256 = "fec53111ca4624c4095e10cd92a4f3f3201414705c6ffff18a20c0a9ec1f5789"


class Invalid(Exception):
    """The certificate is invalid. The message is shown verbatim, so it must not contain input strings."""


# ---------- configuration

def find_problem_toml() -> Path:
    here = Path(__file__).resolve().parent
    for cand in (here / "problem.toml", here.parent / "problem.toml"):
        if cand.is_file():
            return cand
    raise FileNotFoundError("problem.toml not found")


def load_config(path: Path | None = None) -> dict:
    with open(path or find_problem_toml(), "rb") as f:
        data = tomllib.load(f)
    params = data["params"]
    limit = data["max_certificate_bytes"]
    if params.get("instance") != "ta41" or params.get("jobs") != N_JOBS or params.get("machines") != N_MACHINES:
        raise ValueError("params must be instance = ta41, jobs = 30, machines = 20")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"max_certificate_bytes": limit, "instance": load_instance()}


def load_instance() -> dict:
    """routes[j][k] = machine of job j's k-th operation; durations[j][k] = its processing time."""
    if hashlib.sha256(INSTANCE.encode("ascii")).hexdigest() != INSTANCE_SHA256:
        raise ValueError("embedded instance data is corrupt")
    lines = INSTANCE.splitlines()
    if lines[0].split() != [str(N_JOBS), str(N_MACHINES)] or len(lines) != N_JOBS + 1:
        raise ValueError("embedded instance has the wrong shape")
    routes, durations = [], []
    for line in lines[1:]:
        nums = [int(t) for t in line.split()]
        route, dur = nums[0::2], nums[1::2]
        if sorted(route) != list(range(N_MACHINES)) or len(dur) != N_MACHINES or min(dur) < 1:
            raise ValueError("embedded instance is malformed")
        routes.append(route)
        durations.append(dur)
    return {"routes": routes, "durations": durations}


# ---------- reading and parsing (shared)

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


def is_int(x) -> bool:
    return type(x) is int  # excludes bool


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


# ---------- problem rule

def parse_orders(cert) -> list:
    if not isinstance(cert, dict) or set(cert) != {"machines"}:
        raise Invalid('the certificate must be a JSON object with the single key "machines"')
    orders = cert["machines"]
    if not isinstance(orders, list) or len(orders) != N_MACHINES:
        raise Invalid(f"machines must be a list of {N_MACHINES} job orders, one per machine")
    for order in orders:
        if not isinstance(order, list) or len(order) != N_JOBS:
            raise Invalid(f"each machine order must be a list of {N_JOBS} job numbers")
        if not all(is_int(j) for j in order):
            raise Invalid("job numbers must be JSON integers")
        if sorted(order) != list(range(N_JOBS)):
            raise Invalid(f"each machine order must be a permutation of the jobs 0..{N_JOBS - 1}")
    return orders


def makespan(orders: list, inst: dict) -> int:
    """Earliest-start (semi-active) schedule of the disjunctive graph; Invalid if it has a cycle."""
    routes, durations = inst["routes"], inst["durations"]
    n, m = N_JOBS, N_MACHINES
    # operation (j, k) is node j * m + k; pos[j][machine] = k
    pos = [[0] * m for _ in range(n)]
    for j in range(n):
        for k, mach in enumerate(routes[j]):
            pos[j][mach] = k
    succ = [[] for _ in range(n * m)]
    indeg = [0] * (n * m)
    for j in range(n):
        for k in range(m - 1):
            succ[j * m + k].append(j * m + k + 1)
            indeg[j * m + k + 1] += 1
    for mach, order in enumerate(orders):
        for a, b in zip(order, order[1:]):
            u, v = a * m + pos[a][mach], b * m + pos[b][mach]
            succ[u].append(v)
            indeg[v] += 1
    start = [0] * (n * m)
    stack = [v for v in range(n * m) if indeg[v] == 0]
    done = 0
    end = 0
    while stack:
        u = stack.pop()
        done += 1
        fin = start[u] + durations[u // m][u % m]
        if fin > end:
            end = fin
        for v in succ[u]:
            if fin > start[v]:
                start[v] = fin
            indeg[v] -= 1
            if indeg[v] == 0:
                stack.append(v)
    if done != n * m:
        raise Invalid("the machine orders contradict the job routes (the disjunctive graph has a cycle)")
    return end


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object). The machine orders determine the schedule, so they are the canonical form."""
    orders = parse_orders(cert)
    return Fraction(makespan(orders, cfg["instance"])), {"machines": orders}


# ---------- entry point

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
