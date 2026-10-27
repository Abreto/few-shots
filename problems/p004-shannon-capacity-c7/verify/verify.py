#!/usr/bin/env python3
"""Verifier for p004: independent sets in the 10th strong power of the 7-cycle.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON strings and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: a set S of distinct points of {0..6}^10 such that no two of them are adjacent in C7^10, where
x and y are adjacent iff x != y and, in every coordinate, x_i - y_i is 0, 1 or -1 mod 7. Score = |S|.

Method (exact, and the work is bounded independently of the input's structure): split each point
into a prefix (coordinates 0-4) and a suffix (coordinates 5-9), each an index in [0, 7^5).
Two distinct points conflict iff their prefixes are equal or adjacent in C7^5 and their suffixes
are equal or adjacent in C7^5. Points are grouped by prefix; each group keeps the set of its
suffixes and the union of their closed neighbourhoods in C7^5, both as 16807-bit integers. A group
is checked internally, then against each of the 242 neighbouring prefixes with a bitwise AND.
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
MAX_POINTS = 200000           # the Lovasz bound gives alpha(C7^10) <= 161557
CYCLE = 7
DIM = 10
HALF = 5                      # prefix and suffix length
HALF_SIZE = CYCLE ** HALF     # 16807
DIGITS = frozenset("0123456")


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
    cycle = data["params"]["cycle"]
    dim = data["params"]["dimension"]
    limit = data["max_certificate_bytes"]
    if type(cycle) is not int or cycle != CYCLE:
        raise ValueError("params.cycle must be 7")
    if type(dim) is not int or dim != DIM:
        raise ValueError("params.dimension must be 10")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"cycle": cycle, "dimension": dim, "max_certificate_bytes": limit}


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

def half_digits(index: int) -> tuple[int, ...]:
    """Digits of a half-point index, most significant first (the order they appear in the string)."""
    out = []
    for _ in range(HALF):
        index, r = divmod(index, CYCLE)
        out.append(r)
    return tuple(reversed(out))


def neighbour_indices(index: int) -> list[int]:
    """The 3^5 = 243 indices of the closed neighbourhood of a half-point in C7^5 (itself included)."""
    lists = []
    for k, d in enumerate(half_digits(index)):
        w = CYCLE ** (HALF - 1 - k)
        lists.append(((d - 1) % CYCLE * w, d * w, (d + 1) % CYCLE * w))
    a, b, c, d, e = lists
    return [x0 + x1 + x2 + x3 + x4 for x0 in a for x1 in b for x2 in c for x3 in d for x4 in e]


class NeighbourMasks:
    """Closed neighbourhood of a half-point in C7^5 as a 16807-bit integer, built as a tensor product
    over the coordinates; tails are cached, so at most 7 + 49 + 343 + 2401 + 16807 masks are built."""

    def __init__(self) -> None:
        self.cache: dict = {}

    def mask(self, digits: tuple[int, ...]) -> int:
        m = self.cache.get(digits)
        if m is not None:
            return m
        k = len(digits)
        if k == 1:
            d = digits[0]
            m = (1 << ((d - 1) % CYCLE)) | (1 << d) | (1 << ((d + 1) % CYCLE))
        else:
            tail = self.mask(digits[1:])
            w = CYCLE ** (k - 1)
            d = digits[0]
            m = (tail << ((d - 1) % CYCLE * w)) | (tail << (d * w)) | (tail << ((d + 1) % CYCLE * w))
        self.cache[digits] = m
        return m


def parse_points(raw) -> list[int]:
    """Validates the point strings and returns them as integers in [0, 7^10), first character most significant."""
    out = []
    for s in raw:
        if type(s) is not str or len(s) != DIM or not DIGITS.issuperset(s):
            raise Invalid("each point must be a string of exactly 10 characters from 0123456")
        out.append(int(s, CYCLE))
    return out


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    if not isinstance(cert, dict) or set(cert) != {"points"}:
        raise Invalid('the certificate must be a JSON object with the single key "points"')
    raw = cert["points"]
    if not isinstance(raw, list) or not raw:
        raise Invalid("points must be a non-empty list")
    if len(raw) > MAX_POINTS:
        raise Invalid(f"at most {MAX_POINTS} points are accepted")
    pts = parse_points(raw)
    if len(set(pts)) != len(pts):
        raise Invalid("two points are identical")

    # group suffixes by prefix
    groups: dict[int, list[int]] = {}
    for v in pts:
        p, s = divmod(v, HALF_SIZE)
        groups.setdefault(p, []).append(s)

    nm = NeighbourMasks()
    members: dict[int, int] = {}   # prefix -> bit set of its suffixes
    reach: dict[int, int] = {}     # prefix -> union of the closed neighbourhoods of its suffixes
    for p, suffixes in groups.items():
        mem = 0
        cover = 0
        for s in suffixes:
            bit = 1 << s
            if cover & bit:
                raise Invalid("two points are adjacent in C7^10")
            mem |= bit
            cover |= nm.mask(half_digits(s))
        members[p] = mem
        reach[p] = cover

    for p, cover in reach.items():
        for q in neighbour_indices(p):
            if q > p:
                mem = members.get(q)
                if mem is not None and mem & cover:
                    raise Invalid("two points are adjacent in C7^10")

    canon = {"points": sorted(pts)}
    return Fraction(len(pts)), canon


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
