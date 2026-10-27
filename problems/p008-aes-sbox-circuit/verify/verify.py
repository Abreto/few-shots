#!/usr/bin/env python3
"""Verifier for p008: the smallest circuit for the AES S-box over {AND, XOR, XNOR}.

Contract (shared by every problem):
    python verify.py <shot_dir>
Reads <shot_dir>/certificate.json and prints exactly one line of JSON to stdout:
    {"valid": bool, "score": "exact rational string" | null,
     "canonical_hash": "sha256 hex of the canonical certificate" | null, "message": str}
Exit code 0 means a verdict was given (valid or not); non-zero means a usage or configuration error.

Safety: parses JSON and integers only; no eval, pickle, yaml or symbolic maths; no network;
never echoes strings from the input. Python 3.12 standard library only.

Rule: a straight-line program of two-input AND, XOR and XNOR gates over the input wires x0..x7
(xi is bit i of the input byte, x7 the most significant, as b7..b0 in FIPS-197) whose output wires
y0..y7 compute the forward AES S-box of FIPS-197 for all 256 inputs. There are no NOT gates and no
constants; the two operands of a gate are different wires. Score = number of gates. Lower is better.

Simulation is exhaustive and exact: each wire is a 256-bit integer whose bit k is the wire's value
on input byte k.
"""

from __future__ import annotations

import hashlib
import heapq
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
N_BITS = 8
INPUTS = tuple(f"x{i}" for i in range(N_BITS))
OPS = ("AND", "XOR", "XNOR")  # canonical rank = index in this tuple
NAME_FIRST = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
NAME_REST = NAME_FIRST | frozenset("0123456789")
MAX_NAME = 32
FULL = (1 << 256) - 1

# FIPS-197 forward S-box, row r column c = S(16 r + c); test_verify.py recomputes it from GF(2^8) inversion
SBOX_HEX = """\
63 7c 77 7b f2 6b 6f c5 30 01 67 2b fe d7 ab 76
ca 82 c9 7d fa 59 47 f0 ad d4 a2 af 9c a4 72 c0
b7 fd 93 26 36 3f f7 cc 34 a5 e5 f1 71 d8 31 15
04 c7 23 c3 18 96 05 9a 07 12 80 e2 eb 27 b2 75
09 83 2c 1a 1b 6e 5a a0 52 3b d6 b3 29 e3 2f 84
53 d1 00 ed 20 fc b1 5b 6a cb be 39 4a 4c 58 cf
d0 ef aa fb 43 4d 33 85 45 f9 02 7f 50 3c 9f a8
51 a3 40 8f 92 9d 38 f5 bc b6 da 21 10 ff f3 d2
cd 0c 13 ec 5f 97 44 17 c4 a7 7e 3d 64 5d 19 73
60 81 4f dc 22 2a 90 88 46 ee b8 14 de 5e 0b db
e0 32 3a 0a 49 06 24 5c c2 d3 ac 62 91 95 e4 79
e7 c8 37 6d 8d d5 4e a9 6c 56 f4 ea 65 7a ae 08
ba 78 25 2e 1c a6 b4 c6 e8 dd 74 1f 4b bd 8b 8a
70 3e b5 66 48 03 f6 0e 61 35 57 b9 86 c1 1d 9e
e1 f8 98 11 69 d9 8e 94 9b 1e 87 e9 ce 55 28 df
8c a1 89 0d bf e6 42 68 41 99 2d 0f b0 54 bb 16
"""
SBOX_SHA256 = "c2d8e5eed6cbebd8625fc18f81486a7733c04f9b0129ffbe974c68b90308b4f2"  # of the 256 bytes


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
    max_gates = data["params"]["max_gates"]
    limit = data["max_certificate_bytes"]
    if type(max_gates) is not int or not 1 <= max_gates <= 100000:
        raise ValueError("params.max_gates out of range")
    if type(limit) is not int or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("max_certificate_bytes out of range")
    return {"max_gates": max_gates, "max_certificate_bytes": limit, "targets": target_truth_tables()}


def sbox_table() -> list:
    table = [int(t, 16) for t in SBOX_HEX.split()]
    if len(table) != 256 or hashlib.sha256(bytes(table)).hexdigest() != SBOX_SHA256:
        raise ValueError("embedded S-box table is corrupt")
    return table


def input_truth_tables() -> list:
    """Bit k of entry i is bit i of the byte k."""
    return [sum(((k >> i) & 1) << k for k in range(256)) for i in range(N_BITS)]


def target_truth_tables() -> list:
    """Bit k of entry i is bit i of S(k)."""
    table = sbox_table()
    return [sum(((table[k] >> i) & 1) << k for k in range(256)) for i in range(N_BITS)]


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

def is_wire_name(x) -> bool:
    """[A-Za-z_][A-Za-z0-9_]{0,31}, ASCII only."""
    return (isinstance(x, str) and 1 <= len(x) <= MAX_NAME and x[0] in NAME_FIRST
            and all(ch in NAME_REST for ch in x))


def parse_circuit(cert, max_gates: int) -> tuple[list, list]:
    """Returns (gates, outputs) with wires as indices: inputs 0..7, gate g is wire 8 + g.
    gates[g] = (op rank, operand a, operand b); outputs[i] = wire of y_i."""
    if not isinstance(cert, dict) or set(cert) != {"gates", "outputs"}:
        raise Invalid('the certificate must be a JSON object with exactly the keys "gates" and "outputs"')
    raw_gates, raw_outputs = cert["gates"], cert["outputs"]
    if not isinstance(raw_gates, list) or not raw_gates:
        raise Invalid("gates must be a non-empty list")
    if len(raw_gates) > max_gates:
        raise Invalid(f"at most {max_gates} gates are accepted")
    index = {name: i for i, name in enumerate(INPUTS)}
    gates = []
    for g in raw_gates:
        if not isinstance(g, dict) or set(g) != {"op", "a", "b", "out"}:
            raise Invalid('each gate must be an object with exactly the keys "op", "a", "b", "out"')
        op, a, b, out = g["op"], g["a"], g["b"], g["out"]
        if not isinstance(op, str) or op not in OPS:
            raise Invalid('op must be one of "AND", "XOR", "XNOR"')
        if not (is_wire_name(a) and is_wire_name(b) and is_wire_name(out)):
            raise Invalid("wire names must match [A-Za-z_][A-Za-z0-9_]{0,31}")
        if a not in index or b not in index:
            raise Invalid("a gate uses a wire that is not an input or the output of an earlier gate")
        if a == b:
            raise Invalid("the two operands of a gate must be different wires")
        if out in index:
            raise Invalid("each wire is assigned once: a gate output repeats an input or an earlier gate output")
        gates.append((OPS.index(op), index[a], index[b]))
        index[out] = N_BITS + len(gates) - 1
    if not isinstance(raw_outputs, list) or len(raw_outputs) != N_BITS:
        raise Invalid("outputs must be a list of 8 wire names, for y0 .. y7")
    outputs = []
    for name in raw_outputs:
        if not is_wire_name(name) or name not in index:
            raise Invalid("each output must name an input or a gate output")
        outputs.append(index[name])
    return gates, outputs


def simulate(gates: list) -> list:
    values = input_truth_tables()
    for op, a, b in gates:
        x, y = values[a], values[b]
        if op == 0:
            values.append(x & y)
        elif op == 1:
            values.append(x ^ y)
        else:
            values.append((x ^ y) ^ FULL)
    return values


def canonical_form(gates: list, outputs: list) -> dict:
    """Renumber gates in a fixed topological order: repeatedly take, among the gates whose operands
    are already numbered, the one with the smallest (op, smaller operand number, larger operand number).
    Renaming wires, swapping operands or reordering independent gates does not change the result."""
    n = len(gates)
    users = [[] for _ in range(N_BITS + n)]
    pending = [2] * n
    for g, (_op, a, b) in enumerate(gates):
        users[a].append(g)
        users[b].append(g)
    new = [-1] * (N_BITS + n)
    for i in range(N_BITS):
        new[i] = i
    heap: list = []

    def release(wire: int) -> None:
        for g in users[wire]:
            pending[g] -= 1
            if pending[g] == 0:
                op, a, b = gates[g]
                lo, hi = sorted((new[a], new[b]))
                heapq.heappush(heap, (op, lo, hi, g))

    for i in range(N_BITS):
        release(i)
    out_gates = []
    while heap:
        op, lo, hi, g = heapq.heappop(heap)
        new[N_BITS + g] = N_BITS + len(out_gates)
        out_gates.append([OPS[op], lo, hi])
        release(N_BITS + g)
    return {"gates": out_gates, "outputs": [new[w] for w in outputs]}


def check_certificate(cert, cfg: dict) -> tuple[Fraction, dict]:
    """Returns (score, canonical object)."""
    gates, outputs = parse_circuit(cert, cfg["max_gates"])
    values = simulate(gates)
    for i, w in enumerate(outputs):
        if values[w] != cfg["targets"][i]:
            raise Invalid(f"output y{i} differs from bit {i} of the AES S-box on at least one input")
    return Fraction(len(gates)), canonical_form(gates, outputs)


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
