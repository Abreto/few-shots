#!/usr/bin/env python3
"""Verifier for p005: cap sets in F_3^8.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: N distinct points of F_3^8 (coordinates 0, 1, 2) with no three distinct points a, b, c
satisfying a + b + c = 0 (mod 3), i.e. no three points on a line. Score = N. For distinct a, b the
third point c = -(a + b) mod 3 differs from both, so it suffices to check that c is never in the set.
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
MAX_POINTS = 1008             # no cap in F_3^8 is larger: 9 * 112, since the largest cap in F_3^6 has 112 points


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
    dim = data["params"]["dimension"]
    limit = data["max_certificate_bytes"]
    if type(dim) is not int or dim != 8:
        raise ValueError("params.dimension must be 8")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"dimension": dim, "max_certificate_bytes": limit}


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


def is_int(x) -> bool:
    return type(x) is int  # excludes bool


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()


# ---------- problem rule ----------

def parse_point(p, dim: int) -> tuple[int, ...]:
    if not isinstance(p, list) or len(p) != dim:
        raise Invalid(f"each point must be a list of {dim} coordinates")
    for x in p:
        if not is_int(x) or x not in (0, 1, 2):
            raise Invalid("each coordinate must be the integer 0, 1 or 2")
    return tuple(p)


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    dim = cfg["dimension"]
    if not isinstance(cert, dict) or set(cert) != {"points"}:
        raise Invalid('the certificate must be a JSON object with the single key "points"')
    raw = cert["points"]
    if not isinstance(raw, list) or not raw:
        raise Invalid("points must be a non-empty list")
    if len(raw) > MAX_POINTS:
        raise Invalid(f"at most {MAX_POINTS} points are accepted")
    pts = [parse_point(p, dim) for p in raw]
    if len(set(pts)) != len(pts):
        raise Invalid("two points are identical")

    # Encode a point as two base-3 halves; third(a, b) = -(a + b) mod 3 is computed half by half.
    h = dim // 2
    size = 3 ** h
    neg_sum = [[0] * size for _ in range(size)]
    for u in range(size):
        for v in range(size):
            w, x, y, place = 0, u, v, 1
            for _ in range(h):
                w += (-(x % 3 + y % 3)) % 3 * place
                x, y, place = x // 3, y // 3, place * 3
            neg_sum[u][v] = w

    def code(p):
        hi = lo = 0
        for x in p[:h]:
            hi = hi * 3 + x
        for x in p[h:]:
            lo = lo * 3 + x
        return hi, lo

    codes = [code(p) for p in pts]
    member = bytearray(size * size)
    for hi, lo in codes:
        member[hi * size + lo] = 1
    n = len(codes)
    for i in range(n):
        ahi, alo = codes[i]
        row_hi, row_lo = neg_sum[ahi], neg_sum[alo]
        for j in range(i + 1, n):
            bhi, blo = codes[j]
            if member[row_hi[bhi] * size + row_lo[blo]]:
                raise Invalid("three of the points lie on a line (a + b + c = 0 mod 3)")

    canon = {"points": sorted(list(p) for p in pts)}
    return Fraction(n), canon


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
