"""p007 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import tomllib
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("fewshots_verify_p007", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

N = 960
OCTAHEDRON = [[1, 0, 0, 1], [-1, 0, 0, 1], [0, 1, 0, 1], [0, -1, 0, 1], [0, 0, 1, 1], [0, 0, -1, 1]]


def stereo_point(p1: int, p2: int, q: int) -> list:
    """Inverse stereographic projection of (p1/q, p2/q): an exact rational point on the sphere."""
    d = p1 * p1 + p2 * p2 + q * q
    return [2 * p1 * q, 2 * p2 * q, p1 * p1 + p2 * p2 - q * q, d]


def random_points(n: int, seed: int, q: int = 10**8) -> list:
    rng = random.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        p = stereo_point(rng.randint(-2 * q, 2 * q), rng.randint(-2 * q, 2 * q), q)
        g = math.gcd(math.gcd(p[0], p[1]), math.gcd(p[2], p[3]))
        key = tuple(v // g for v in p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def reference_energy(points: list, digits: int = 40) -> Decimal:
    """Independent high-precision energy with Decimal square roots (accurate to far below 10^-10)."""
    with localcontext() as ctx:
        ctx.prec = digits
        total = Decimal(0)
        for i in range(len(points)):
            a, b, c, d = points[i]
            for j in range(i + 1, len(points)):
                a2, b2, c2, d2 = points[j]
                r2 = Fraction((a * d2 - a2 * d) ** 2 + (b * d2 - b2 * d) ** 2 + (c * d2 - c2 * d) ** 2, (d * d2) ** 2)
                total += (Decimal(r2.denominator) / Decimal(r2.numerator)).sqrt()
        return total


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = V.load_config(ROOT / "problem.toml")
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_bytes(self, data: bytes) -> dict:
        (self.dir / "certificate.json").write_bytes(data)
        return V.verify_dir(self.dir, self.cfg)

    def run_obj(self, obj) -> dict:
        return self.run_bytes(json.dumps(obj).encode("utf-8"))

    def small(self, points: list) -> str:
        """Score of a small configuration, checked with the same rules but a different point count."""
        score, _ = V.check_certificate({"points": points}, dict(self.cfg, n=len(points)))
        return score

    def assertInvalid(self, res: dict, fragment: str = ""):
        self.assertFalse(res["valid"], res)
        self.assertIsNone(res["score"])
        self.assertIsNone(res["canonical_hash"])
        self.assertIn(fragment, res["message"])

    def assertRigorousBound(self, score: str, points: list):
        exact = reference_energy(points)
        bound = Decimal(score)
        self.assertGreaterEqual(bound, exact)
        self.assertLess(bound - exact, Decimal("1e-10") + Decimal(len(points) ** 2) * Decimal(2) ** -79)

    # ---------- valid input

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)

    def test_octahedron(self):
        # 12 edges of length sqrt 2 and 3 antipodal pairs: E = 6 sqrt 2 + 3/2 = 9.98528137423857...
        self.assertEqual(self.small(OCTAHEDRON), "9.9852813743")
        self.assertRigorousBound(self.small(OCTAHEDRON), OCTAHEDRON)

    def test_two_point_bounds_are_tight_and_rigorous(self):
        k = V.PREC_BITS
        # antipodal: 1/r = 1/2 exactly
        self.assertEqual(V.energy_upper_bound([(0, 0, 1, 1), (0, 0, -1, 1)]), 1 << (k - 1))
        # orthogonal: 1/r = 1/sqrt 2, so S is the least integer with S^2 >= 2^(2k-1)
        s = V.energy_upper_bound([(1, 0, 0, 1), (0, 1, 0, 1)])
        self.assertGreaterEqual(s * s, 1 << (2 * k - 1))
        self.assertLess((s - 1) ** 2, 1 << (2 * k - 1))
        # (3, 4, 0)/5 and (0, 0, 1): r^2 = 2, same as above
        self.assertEqual(V.energy_upper_bound([(3, 4, 0, 5), (0, 0, 1, 1)]), s)

    def test_rounding_is_upward(self):
        k = V.PREC_BITS
        self.assertEqual(V.round_up_decimal(1 << k, k, 10), "1.0000000000")
        self.assertEqual(V.round_up_decimal((1 << k) + 1, k, 10), "1.0000000001")
        self.assertEqual(V.round_up_decimal(0, k, 10), "0.0000000000")
        self.assertEqual(V.round_up_decimal(3 << (k - 2), k, 3), "0.750")

    def test_random_configurations_are_bounded_rigorously(self):
        for seed in range(3):
            pts = random_points(25, seed)
            self.assertRigorousBound(self.small(pts), pts)

    def test_full_size_random_configuration(self):
        pts = random_points(N, 7)
        res = self.run_obj({"points": pts})
        self.assertTrue(res["valid"], res)
        # a random configuration is far worse than an optimised one
        self.assertGreater(Fraction(res["score"]), 444369)

    def test_canonical_hash_ignores_order_scaling_and_formatting(self):
        pts = random_points(N, 3)
        a = self.run_obj({"points": pts})
        shuffled = list(pts)
        random.Random(0).shuffle(shuffled)
        scaled = [[3 * v for v in p] for p in shuffled[:10]] + shuffled[10:]
        b = self.run_bytes(json.dumps({"points": scaled}, indent=2).encode())
        self.assertTrue(b["valid"], b)
        self.assertEqual(a["canonical_hash"], b["canonical_hash"])
        self.assertEqual(a["score"], b["score"])
        # a rotation (here x <-> y) is a different certificate with the same energy
        swapped = [[p[1], p[0], p[2], p[3]] for p in pts]
        c = self.run_obj({"points": swapped})
        self.assertEqual(c["score"], a["score"])
        self.assertNotEqual(c["canonical_hash"], a["canonical_hash"])

    # ---------- invalid certificates

    def test_wrong_count(self):
        pts = random_points(N + 1, 4)
        self.assertInvalid(self.run_obj({"points": pts[:N - 1]}), "exactly 960")
        self.assertInvalid(self.run_obj({"points": pts}), "exactly 960")
        self.assertInvalid(self.run_obj({"points": []}), "exactly 960")

    def test_wrong_shape(self):
        self.assertInvalid(self.run_obj([OCTAHEDRON]), "single key")
        self.assertInvalid(self.run_obj({"points": OCTAHEDRON, "n": 6}), "single key")
        self.assertInvalid(self.run_obj({"points": "x"}), "exactly 960")
        bad_points = ([1, 0, 0], [1, 0, 0, 1, 0], [True, 0, 0, 1], [1, 0, 0, "1"], 7, None)
        for bad in bad_points:
            pts = random_points(N - 1, 5) + [bad]
            self.assertInvalid(self.run_obj({"points": pts}), "four integers")

    def test_point_rules(self):
        base = random_points(N - 1, 6)
        cases = [
            ([1, 0, 0, 0], "positive"),
            ([-1, 0, 0, -1], "positive"),
            ([1, 1, 1, 2], "unit sphere"),
            ([0, 0, 0, 1], "unit sphere"),
            ([0, 0, 10**18 + 1, 10**18 + 1], "10^18"),
        ]
        for bad, fragment in cases:
            self.assertInvalid(self.run_obj({"points": base + [bad]}), fragment)
        self.assertTrue(self.run_obj({"points": base + [[0, 0, 10**18, 10**18]]})["valid"])

    def test_coincident_points(self):
        base = random_points(N - 1, 8)
        self.assertInvalid(self.run_obj({"points": base + [base[0]]}), "coincide")
        self.assertInvalid(self.run_obj({"points": base + [[5 * v for v in base[0]]]}), "coincide")

    def test_non_integers(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", '"1"', "null"):
            text = '{"points": [[%s, 0, 0, 1]]}' % bad
            self.assertInvalid(self.run_bytes(text.encode()))
        self.assertInvalid(self.run_bytes(('{"points": [[%s, 0, 0, 1]]}' % ("9" * 20)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"points": [], "points": []}'), "duplicate keys")

    # ---------- hostile input

    def test_oversized_file(self):
        self.assertInvalid(self.run_bytes(b" " * (self.cfg["max_certificate_bytes"] + 1)), "size limit")

    def test_max_size_points_fit_the_limit(self):
        # 960 points with 18-digit integers must fit in the certificate size limit
        q = 5 * 10**8
        pts = [stereo_point(q - i, -(q - 2 * i), q) for i in range(N)]
        self.assertLess(len(json.dumps({"points": pts}).encode()), self.cfg["max_certificate_bytes"])

    def test_deeply_nested_json(self):
        for depth in (9, 30000):
            self.assertInvalid(self.run_bytes(("[" * depth + "]" * depth).encode()), "nested")

    def test_not_json_or_not_utf8(self):
        self.assertInvalid(self.run_bytes(b""), "valid JSON")
        self.assertInvalid(self.run_bytes(b"\xff\xfe{}"), "UTF-8")
        self.assertInvalid(self.run_bytes(b'__import__("os").system("id")'), "valid JSON")

    def test_missing_file_and_symlink(self):
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "missing")
        target = self.dir / "real.json"
        target.write_text(json.dumps({"points": OCTAHEDRON}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"points": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=120)

    def test_cli_prints_exactly_one_json_line(self):
        proc = self.run_cli(str(ROOT / "baseline"))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertTrue(obj["valid"], obj)
        (self.dir / "certificate.json").write_text("[" * 100000)
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(json.loads(proc.stdout)["valid"])
        self.assertEqual(proc.stderr, b"")

    def test_cli_usage_error(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["valid"])

    def test_source_has_no_dangerous_constructs(self):
        tree = ast.parse((HERE / "verify.py").read_text(encoding="utf-8"))
        imported, called = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                f = node.func
                called.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
        self.assertLessEqual(imported, {"__future__", "hashlib", "json", "math", "os", "stat", "sys",
                                        "tomllib", "pathlib"})
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
