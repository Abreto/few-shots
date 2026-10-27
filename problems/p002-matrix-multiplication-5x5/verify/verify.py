#!/usr/bin/env python3
"""Verifier for p002: rank decompositions of the 5x5x5 matrix multiplication tensor over Q.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON, integers and "p/q" strings only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: r terms (U_t, V_t, W_t) of 5x5 rational matrices with
    sum_t U_t (x) V_t (x) W_t = sum_{i,j,k} E_ij (x) E_jk (x) E_ki,
that is sum_t U_t[i1][j1] * V_t[j2][k2] * W_t[k3][i3] = [i1 = i3][j1 = j2][k2 = k3] for every index.
Score = r. All arithmetic is exact: every entry is multiplied by the common denominator D of the
certificate (at most 10^18), and the integer sum is compared with D^3 times the target tensor.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

CERT_NAME = "certificate.json"
MAX_DEPTH = 8                 # maximum JSON nesting depth
MAX_INT_DIGITS = 18           # maximum digits in a single integer
MAX_ABS_NUM = 10**9           # bound on |p| in an entry p or p/q
MAX_DEN = 10**9               # bound on q in an entry p/q
MAX_COMMON_DEN = 10**18       # bound on the lcm of all denominators in the certificate
MAX_TERMS = 125               # the standard algorithm uses n^3 = 125 terms


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
    if type(n) is not int or n != 5:
        raise ValueError("params.n must be 5")
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

ENTRY_MSG = 'each matrix entry must be a JSON integer or a string "p/q" with integers p and q'


def is_digits(s: str) -> bool:
    return bool(s) and all(ch in "0123456789" for ch in s)  # ASCII digits only


def parse_entry(x) -> Fraction:
    if is_int(x):
        if abs(x) > MAX_ABS_NUM:
            raise Invalid("a matrix entry exceeds the bound 10^9")
        return Fraction(x)
    if isinstance(x, str):
        num, slash, den = x.partition("/")
        digits = num[1:] if num.startswith("-") else num
        if (not slash or not is_digits(digits) or not is_digits(den)
                or len(digits) > MAX_INT_DIGITS or len(den) > MAX_INT_DIGITS):
            raise Invalid(ENTRY_MSG)
        p, q = int(num), int(den)
        if abs(p) > MAX_ABS_NUM or q > MAX_DEN:
            raise Invalid("a matrix entry exceeds the bound 10^9")
        if q == 0:
            raise Invalid("a denominator is zero")
        return Fraction(p, q)
    raise Invalid(ENTRY_MSG)


def parse_matrix(m, n: int) -> list[list[Fraction]]:
    if not isinstance(m, list) or len(m) != n:
        raise Invalid(f"each matrix must be a list of {n} rows")
    rows = []
    for row in m:
        if not isinstance(row, list) or len(row) != n:
            raise Invalid(f"each matrix row must be a list of {n} entries")
        rows.append([parse_entry(x) for x in row])
    if not any(x for row in rows for x in row):
        raise Invalid("a factor matrix is zero")
    return rows


def normalize_term(u, v, w) -> list:
    """Scale U and V so that their first nonzero entry (row-major) is 1; W absorbs the factors."""
    lu = next(x for row in u for x in row if x)
    lv = next(x for row in v for x in row if x)
    u = [[x / lu for x in row] for row in u]
    v = [[x / lv for x in row] for row in v]
    w = [[x * lu * lv for x in row] for row in w]
    enc = lambda x: x.numerator if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
    return [[[enc(x) for x in row] for row in m] for m in (u, v, w)]


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    n = cfg["n"]
    if not isinstance(cert, dict) or set(cert) != {"terms"}:
        raise Invalid('the certificate must be a JSON object with the single key "terms"')
    raw = cert["terms"]
    if not isinstance(raw, list) or not raw:
        raise Invalid("terms must be a non-empty list")
    if len(raw) > MAX_TERMS:
        raise Invalid(f"at most {MAX_TERMS} terms are accepted")
    terms = []
    for t in raw:
        if not isinstance(t, list) or len(t) != 3:
            raise Invalid("each term must be a list of three matrices [U, V, W]")
        terms.append([parse_matrix(m, n) for m in t])

    # Common denominator D of every entry; with all entries multiplied by D the check is in integers.
    den = 1
    for t in terms:
        for m in t:
            for row in m:
                for x in row:
                    den = math.lcm(den, x.denominator)
                    if den > MAX_COMMON_DEN:
                        raise Invalid("the least common multiple of all denominators exceeds 10^18")

    nn = n * n
    tensor = [0] * (nn * nn * nn)  # flat index (a * nn + b) * nn + c, a = U index, b = V index, c = W index
    for t in terms:
        us, vs, ws = ([(i * n + j, int(x * den)) for i, row in enumerate(m) for j, x in enumerate(row) if x]
                      for m in t)
        for a, x in us:
            for b, y in vs:
                xy = x * y
                base = (a * nn + b) * nn
                for c, z in ws:
                    tensor[base + c] += xy * z

    den3 = den ** 3
    target = [0] * (nn * nn * nn)
    for i in range(n):
        for j in range(n):
            for k in range(n):
                target[((i * n + j) * nn + (j * n + k)) * nn + (k * n + i)] = den3
    if tensor != target:
        wrong = [idx for idx in range(len(tensor)) if tensor[idx] != target[idx]]
        a, rest = divmod(wrong[0], nn * nn)
        b, c = divmod(rest, nn)
        where = (f"U[{a // n + 1}][{a % n + 1}] V[{b // n + 1}][{b % n + 1}] "
                 f"W[{c // n + 1}][{c % n + 1}]")
        raise Invalid(f"the terms do not sum to the matrix multiplication tensor: {len(wrong)} of "
                      f"{len(tensor)} coefficients are wrong, the first at {where} (1-based)")

    canon = {"terms": sorted((normalize_term(*t) for t in terms),
                             key=lambda t: json.dumps(t, separators=(",", ":")))}
    return Fraction(len(terms)), canon


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
