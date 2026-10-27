"""p010 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import hashlib
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("fewshots_verify_p010", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

N = 100000
TSP_SHA256 = "532fefbfb9ad66cc2550bece766fa069acaa8e34ee511ac1949ae101da4d70ad"  # mona-lisa100K.tsp


def float_nint(dx: int, dy: int) -> int:
    """TSPLIB's reference formula, (int)(sqrt(xd*xd + yd*yd) + 0.5), in double precision."""
    return int(math.sqrt(dx * dx + dy * dy) + 0.5)


class VerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ROOT / "baseline" / "certificate.json").read_text(encoding="utf-8"))

    def setUp(self):
        self.cfg = V.load_config(ROOT / "problem.toml")
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def tour(self) -> list:
        return list(self.baseline["tour"])

    def run_bytes(self, data: bytes) -> dict:
        (self.dir / "certificate.json").write_bytes(data)
        return V.verify_dir(self.dir, self.cfg)

    def run_obj(self, obj) -> dict:
        return self.run_bytes(json.dumps(obj).encode("utf-8"))

    def assertInvalid(self, res: dict, fragment: str = ""):
        self.assertFalse(res["valid"], res)
        self.assertIsNone(res["score"])
        self.assertIsNone(res["canonical_hash"])
        self.assertIn(fragment, res["message"])

    # ---------- the instance

    def test_embedded_coordinates_rebuild_the_tsplib_file(self):
        xs, ys = V.coordinates()
        lines = ["NAME: mona-lisa100K", "COMMENT: TSP art (Bosch)", "TYPE: TSP", "DIMENSION: 100000",
                 "EDGE_WEIGHT_TYPE: EUC_2D", "NODE_COORD_SECTION"]
        lines += [f"{i + 1} {xs[i]} {ys[i]}" for i in range(N)]
        lines.append("EOF")
        text = ("\n".join(lines) + "\n").encode("ascii")
        self.assertEqual(hashlib.sha256(text).hexdigest(), TSP_SHA256)
        self.assertEqual((xs[0], ys[0], xs[-1], ys[-1]), (14991, 8390, 13425, 1002))

    def test_euc_2d_matches_tsplib_formula(self):
        rng = random.Random(10)
        cases = [(0, 0), (1, 0), (0, -1), (3, 4), (1, 1), (2, 1), (20000, 20000), (-19986, 19978)]
        cases += [(rng.randint(-20000, 20000), rng.randint(-20000, 20000)) for _ in range(20000)]
        cases += [(rng.randint(-60, 60), rng.randint(-60, 60)) for _ in range(5000)]
        for dx, dy in cases:
            self.assertEqual(V.euc_2d(dx, dy), float_nint(dx, dy), (dx, dy))
        # the rounding boundary: s = r^2 + r rounds down to r, s = r^2 + r + 1 rounds up to r + 1
        self.assertEqual(V.euc_2d(1, 1), 1)      # s = 2 = 1 + 1, sqrt = 1.414
        self.assertEqual(V.euc_2d(4, 2), 4)      # s = 20 = 16 + 4, sqrt = 4.472
        self.assertEqual(V.euc_2d(3, 2), 4)      # s = 13 = 9 + 3 + 1, sqrt = 3.606
        self.assertEqual(V.euc_2d(5, 0), 5)
        self.assertEqual(V.euc_2d(-3, -4), 5)
        for s_root in (2, 17, 1000, 19999):
            self.assertEqual(V.euc_2d(s_root, 0), s_root)

    # ---------- valid input

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)

    def test_lengths_agree_with_float_reference(self):
        xs, ys = V.coordinates()
        rng = random.Random(3)
        for tour in (list(range(1, N + 1)), rng.sample(range(1, N + 1), N), self.tour()):
            ref = sum(float_nint(xs[a - 1] - xs[b - 1], ys[a - 1] - ys[b - 1])
                      for a, b in zip(tour, tour[1:] + tour[:1]))
            self.assertEqual(V.tour_length(tour), ref)
        self.assertEqual(V.tour_length(self.tour()), 5757191)

    def test_identity_tour(self):
        res = self.run_obj({"tour": list(range(1, N + 1))})
        self.assertTrue(res["valid"], res)
        self.assertGreater(int(res["score"]), 5757191)

    def test_canonical_hash_ignores_rotation_and_direction(self):
        t = self.tour()
        h = self.run_obj({"tour": t})["canonical_hash"]
        rotated = t[12345:] + t[:12345]
        self.assertEqual(self.run_obj({"tour": rotated})["canonical_hash"], h)
        self.assertEqual(self.run_obj({"tour": rotated[::-1]})["canonical_hash"], h)
        self.assertEqual(self.run_bytes(json.dumps({"tour": t}, indent=1).encode())["canonical_hash"], h)
        u = list(t)
        u[10], u[11] = u[11], u[10]
        res = self.run_obj({"tour": u})
        self.assertTrue(res["valid"], res)
        self.assertNotEqual(res["canonical_hash"], h)

    def test_canonical_tour(self):
        self.assertEqual(V.canonical_tour([3, 1, 4, 2, 5]), [1, 3, 5, 2, 4])
        self.assertEqual(V.canonical_tour([1, 2, 3, 4]), [1, 2, 3, 4])
        self.assertEqual(V.canonical_tour([4, 3, 2, 1]), [1, 2, 3, 4])

    # ---------- invalid certificates

    def test_not_a_permutation(self):
        t = self.tour()
        self.assertInvalid(self.run_obj({"tour": t[:-1]}), "exactly 100000")
        self.assertInvalid(self.run_obj({"tour": t + [t[0]]}), "exactly 100000")
        u = list(t)
        u[500] = u[400]
        self.assertInvalid(self.run_obj({"tour": u}), "more than once")
        for bad in (0, -1, N + 1, 10**12):
            u = list(t)
            u[7] = bad
            self.assertInvalid(self.run_obj({"tour": u}), "between 1 and")
        for bad in (True, "5", None, [5]):
            u = list(t)
            u[7] = bad
            self.assertInvalid(self.run_obj({"tour": u}), "JSON integer")

    def test_zero_based_tour_is_rejected(self):
        self.assertInvalid(self.run_obj({"tour": list(range(N))}), "between 1 and")

    def test_wrong_shape(self):
        t = self.tour()
        self.assertInvalid(self.run_obj(t), "single key")
        self.assertInvalid(self.run_obj({"tour": t, "length": 5757191}), "single key")
        self.assertInvalid(self.run_obj({"cities": t}), "single key")
        self.assertInvalid(self.run_obj({"tour": {}}), "list of city numbers")
        self.assertInvalid(self.run_obj({"tour": []}), "exactly 100000")

    def test_non_integers(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "2.0"):
            self.assertInvalid(self.run_bytes(('{"tour": [%s, 2, 3]}' % bad).encode()))
        self.assertInvalid(self.run_bytes(('{"tour": [%s]}' % ("9" * 40)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"tour": [], "tour": []}'), "duplicate keys")

    # ---------- hostile input

    def test_oversized_file(self):
        self.assertInvalid(self.run_bytes(b" " * (self.cfg["max_certificate_bytes"] + 1)), "size limit")

    def test_size_limit_fits_a_spacious_tour(self):
        text = json.dumps({"tour": self.tour()}, indent=2).encode()
        self.assertLessEqual(len(text), self.cfg["max_certificate_bytes"])

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
        target.write_text(json.dumps({"tour": self.tour()}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"tour": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        res = self.run_bytes(b'{"tour": ["<script>"]}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"tour": self.tour()}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "5757191")
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
        self.assertLessEqual(imported, {"__future__", "base64", "hashlib", "json", "math", "os", "stat",
                                        "struct", "sys", "tomllib", "zlib", "fractions", "pathlib"})
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
