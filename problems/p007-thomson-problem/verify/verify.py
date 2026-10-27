#!/usr/bin/env python3
"""Verifier for p007: the Thomson problem for N = 960 points on the unit sphere.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: N = 960 distinct points on the unit sphere, each given by integers (a, b, c, d) with d > 0
and a^2 + b^2 + c^2 = d^2, meaning the rational point (a/d, b/d, c/d). The Coulomb energy is
E = sum_{i<j} 1/|x_i - x_j|. Each squared distance is an exact rational; each 1/|x_i - x_j| is
bounded from above with integer square roots at precision 2^-80, the bounds are summed exactly,
and the score is that sum rounded up to 10 decimal places. So score >= E always, and
score - E < 10^-10 + N(N-1)/2 * 2^-79.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import sys
import tomllib
from pathlib import Path

CERT_NAME = "certificate.json"
MAX_DEPTH = 8                 # maximum JSON nesting depth
MAX_INT_DIGITS = 19           # maximum digits in a single integer (10^18 has 19 digits)
MAX_D = 10**18                # bound on d (and so on |a|, |b|, |c|)
NUM_POINTS = 960              # must match [params] n in problem.toml
PREC_BITS = 80                # each 1/r is rounded up to a multiple of 2^-PREC_BITS
DECIMALS = 10                 # the score is the energy bound rounded up to this many decimals


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
    n = data["params"]["n"]
    limit = data["max_certificate_bytes"]
    if type(n) is not int or n != NUM_POINTS:
        raise ValueError("params.n must be 960")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"n": n, "max_certificate_bytes": limit}


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

def parse_point(p) -> tuple[int, int, int, int]:
    """Checks one point and returns it reduced by the gcd of its four integers."""
    if not isinstance(p, list) or len(p) != 4 or not all(is_int(v) for v in p):
        raise Invalid("each point must be a list of four integers [a, b, c, d]")
    a, b, c, d = p
    if d <= 0:
        raise Invalid("the denominator d must be positive")
    if d > MAX_D:
        raise Invalid("the denominator d exceeds the bound 10^18")
    if a * a + b * b + c * c != d * d:
        raise Invalid("a point is not on the unit sphere: a^2 + b^2 + c^2 must equal d^2")
    g = math.gcd(math.gcd(a, b), math.gcd(c, d))
    return a // g, b // g, c // g, d // g


def energy_upper_bound(pts: list[tuple[int, int, int, int]]) -> int:
    """An integer S with S / 2^PREC_BITS >= sum_{i<j} 1/|x_i - x_j|.

    For x = (a, b, c)/d and y = (a', b', c')/d' on the unit sphere,
    |x - y|^2 = 2 (d d' - (a a' + b b' + c c')) / (d d'), so 1/|x - y| = sqrt(d d' / (2 D))
    with the positive integer D = d d' - (a a' + b b' + c c'). Per pair the bound is
    ceil(sqrt(ceil(d d' 4^k / (2 D)))) with k = PREC_BITS, which exceeds 2^k / |x - y| by less than 2.
    """
    shift = PREC_BITS
    isqrt = math.isqrt
    total = 0
    n = len(pts)
    for i in range(n):
        a, b, c, d = pts[i]
        for j in range(i + 1, n):
            a2, b2, c2, d2 = pts[j]
            num = d * d2
            dd = num - (a * a2 + b * b2 + c * c2)
            if dd <= 0:
                raise Invalid("two points coincide")
            m = -((-num << (2 * shift)) // (2 * dd))   # ceil(num * 4^k / (2 D))
            s = isqrt(m)
            total += s if s * s == m else s + 1
    return total


def round_up_decimal(num: int, shift: int, decimals: int) -> str:
    """num / 2^shift rounded up to `decimals` places, as a decimal string (num >= 0)."""
    scaled = -((-num * 10**decimals) >> shift)   # ceil(num * 10^decimals / 2^shift)
    whole, frac = divmod(scaled, 10**decimals)
    return f"{whole}.{frac:0{decimals}d}"


def check_certificate(cert, cfg: dict) -> tuple[str, dict]:
    """Returns (score string, canonical object)."""
    n = cfg["n"]
    if not isinstance(cert, dict) or set(cert) != {"points"}:
        raise Invalid('the certificate must be a JSON object with the single key "points"')
    raw = cert["points"]
    if not isinstance(raw, list) or len(raw) != n:
        raise Invalid(f"points must be a list of exactly {n} points")
    pts = [parse_point(p) for p in raw]
    if len(set(pts)) != len(pts):
        raise Invalid("two points coincide")
    score = round_up_decimal(energy_upper_bound(pts), PREC_BITS, DECIMALS)
    canon = {"points": sorted([list(p) for p in pts])}
    return score, canon


# ---------- entry point ----------

def verify_bytes(data: bytes, cfg: dict) -> dict:
    cert = strict_json(data)
    score, canon = check_certificate(cert, cfg)
    return {
        "valid": True,
        "score": score,
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
