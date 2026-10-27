#!/usr/bin/env python3
"""Verifier for p001: kissing configurations in dimension 11.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: N nonzero vectors in R^11 with coordinates in Z[sqrt 2], all of the same squared norm,
and every pair at angle >= 60 degrees, i.e. <x, y> <= |x|^2 / 2. Score = N. All arithmetic is
exact: a + b*sqrt(2) is kept as the integer pair (a, b).
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
MAX_ABS_COORD = 10**9         # bound on |p| and |q| in each coordinate p + q*sqrt(2)
MAX_VECTORS = 2000            # the best upper bound in dimension 11 is 868


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
    if type(dim) is not int or dim != 11:
        raise ValueError("params.dimension must be 11")
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

def sign_q2(a: int, b: int) -> int:
    """Sign of a + b*sqrt(2), exactly."""
    if a >= 0 and b >= 0:
        return 0 if a == 0 and b == 0 else 1
    if a <= 0 and b <= 0:
        return -1
    # opposite signs: compare a^2 with 2 b^2
    if a > 0:  # b < 0
        return 1 if a * a > 2 * b * b else -1
    return 1 if 2 * b * b > a * a else -1  # a < 0 < b; a^2 = 2b^2 is impossible for integers


def parse_vector(v, dim: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not isinstance(v, list) or len(v) != dim:
        raise Invalid(f"each vector must be a list of {dim} coordinates")
    ps, qs = [], []
    for c in v:
        if not isinstance(c, list) or len(c) != 2 or not is_int(c[0]) or not is_int(c[1]):
            raise Invalid("each coordinate must be a pair of integers [p, q] meaning p + q*sqrt(2)")
        if abs(c[0]) > MAX_ABS_COORD or abs(c[1]) > MAX_ABS_COORD:
            raise Invalid("a coordinate exceeds the bound 10^9")
        ps.append(c[0])
        qs.append(c[1])
    return tuple(ps), tuple(qs)


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    dim = cfg["dimension"]
    if not isinstance(cert, dict) or set(cert) != {"vectors"}:
        raise Invalid('the certificate must be a JSON object with the single key "vectors"')
    raw = cert["vectors"]
    if not isinstance(raw, list) or not raw:
        raise Invalid("vectors must be a non-empty list")
    if len(raw) > MAX_VECTORS:
        raise Invalid(f"at most {MAX_VECTORS} vectors are accepted")
    vecs = [parse_vector(v, dim) for v in raw]
    if len(set(vecs)) != len(vecs):
        raise Invalid("two vectors are identical")

    # squared norm a + b*sqrt(2): a = sum(p^2 + 2 q^2), b = 2 * sum(p q)
    def norm(v):
        ps, qs = v
        return (sum(p * p + 2 * q * q for p, q in zip(ps, qs)), 2 * sum(p * q for p, q in zip(ps, qs)))

    na, nb = norm(vecs[0])
    if (na, nb) == (0, 0):
        raise Invalid("the zero vector is not allowed")
    for v in vecs[1:]:
        if norm(v) != (na, nb):
            raise Invalid("all vectors must have the same squared norm")

    # <x, y> = c + d*sqrt(2); need 2c - na + (2d - nb)*sqrt(2) <= 0
    n = len(vecs)
    for i in range(n):
        pi, qi = vecs[i]
        for j in range(i + 1, n):
            pj, qj = vecs[j]
            c = d = 0
            for k in range(dim):
                c += pi[k] * pj[k] + 2 * qi[k] * qj[k]
                d += pi[k] * qj[k] + qi[k] * pj[k]
            if sign_q2(2 * c - na, 2 * d - nb) > 0:
                raise Invalid("two vectors are closer than 60 degrees; the spheres overlap")

    canon = {"vectors": sorted([[p, q] for p, q in zip(ps, qs)] for ps, qs in vecs)}
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
