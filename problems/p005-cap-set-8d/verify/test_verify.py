"""p005 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import importlib.util
import itertools
import json
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
_spec = importlib.util.spec_from_file_location("fewshots_verify_p005", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

D = 8


def binary_cube() -> list:
    """{0, 1}^8: a cap of 256 points, since x + y + z = 0 mod 3 with x, y, z in {0, 1} forces x = y = z."""
    return [list(p) for p in itertools.product((0, 1), repeat=D)]


def is_cap_brute_force(points: list) -> bool:
    s = {tuple(p) for p in points}
    for a, b, c in itertools.combinations(s, 3):
        if all((x + y + z) % 3 == 0 for x, y, z in zip(a, b, c)):
            return False
    return True


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

    def assertInvalid(self, res: dict, fragment: str = ""):
        self.assertFalse(res["valid"], res)
        self.assertIsNone(res["score"])
        self.assertIsNone(res["canonical_hash"])
        self.assertIn(fragment, res["message"])

    # ---------- valid input

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)

    def test_baseline_has_no_line_by_direct_check(self):
        pts = [tuple(p) for p in json.loads((ROOT / "baseline" / "certificate.json").read_text())["points"]]
        s = set(pts)
        self.assertEqual(len(s), 512)
        for a, b in itertools.combinations(pts, 2):
            self.assertNotIn(tuple((-(x + y)) % 3 for x, y in zip(a, b)), s)

    def test_binary_cube(self):
        res = self.run_obj({"points": binary_cube()})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "256")

    def test_small_sets(self):
        self.assertEqual(self.run_obj({"points": [[0] * D]})["score"], "1")
        self.assertEqual(self.run_obj({"points": [[0] * D, [2] * D]})["score"], "2")

    def test_agrees_with_brute_force(self):
        rng = random.Random(5)
        space = list(itertools.product(range(3), repeat=D))
        seen = set()
        for _ in range(300):
            pts = [list(p) for p in rng.sample(space, rng.randint(3, 40))]
            if rng.random() < 0.5:  # plant a line
                a, b = pts[0], pts[1]
                pts.append([(-(x + y)) % 3 for x, y in zip(a, b)])
                pts = [list(p) for p in {tuple(p) for p in pts}]
            expected = is_cap_brute_force(pts)
            seen.add(expected)
            res = self.run_obj({"points": pts})
            self.assertEqual(res["valid"], expected, res)
            if expected:
                self.assertEqual(res["score"], str(len(pts)))
        self.assertEqual(seen, {True, False})

    def test_canonical_hash_ignores_order_and_formatting(self):
        pts = binary_cube()
        a = self.run_obj({"points": pts})["canonical_hash"]
        b = self.run_bytes(json.dumps({"points": list(reversed(pts))}, indent=2).encode())["canonical_hash"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, self.run_obj({"points": pts[:-1]})["canonical_hash"])
        # a translate of the same cap is a different certificate
        shifted = [[(x + 1) % 3 for x in p] for p in pts]
        c = self.run_obj({"points": shifted})
        self.assertTrue(c["valid"], c)
        self.assertNotEqual(a, c["canonical_hash"])

    # ---------- invalid certificates

    def test_line(self):
        self.assertInvalid(self.run_obj({"points": [[0] * D, [1] * D, [2] * D]}), "line")
        self.assertInvalid(self.run_obj({"points": binary_cube() + [[2] * D]}), "line")
        # a line in a single coordinate direction
        line = [[x] + [0] * (D - 1) for x in range(3)]
        self.assertInvalid(self.run_obj({"points": line}), "line")
        # a line with direction (1, 2, 0, ...) through (0, 1, 2, ...)
        a = [0, 1, 2, 0, 0, 0, 0, 0]
        b = [1, 0, 2, 0, 0, 0, 0, 0]
        c = [2, 2, 2, 0, 0, 0, 0, 0]
        self.assertInvalid(self.run_obj({"points": [a, [1] * D, b, c]}), "line")

    def test_duplicate_points(self):
        pts = binary_cube()
        self.assertInvalid(self.run_obj({"points": pts + [pts[3]]}), "identical")

    def test_wrong_shape(self):
        self.assertInvalid(self.run_obj([[0] * D]), "single key")
        self.assertInvalid(self.run_obj({"points": [[0] * D], "note": "x"}), "single key")
        self.assertInvalid(self.run_obj({"points": []}), "non-empty")
        self.assertInvalid(self.run_obj({"points": {"a": [0] * D}}), "non-empty")
        self.assertInvalid(self.run_obj({"points": [[0] * (D - 1)]}), "8 coordinates")
        self.assertInvalid(self.run_obj({"points": [[0] * (D + 1)]}), "8 coordinates")
        self.assertInvalid(self.run_obj({"points": ["00000000"]}), "8 coordinates")
        for bad in (3, -1, -2, True, False, None, "1", [1], 10**12):
            with self.subTest(bad=bad):
                self.assertInvalid(self.run_obj({"points": [[bad] + [0] * (D - 1)]}), "0, 1 or 2")

    def test_bounds(self):
        too_many = [list(p) for p in itertools.product(range(3), repeat=D)][:V.MAX_POINTS + 1]
        self.assertInvalid(self.run_obj({"points": too_many}), "at most 1008")
        self.assertInvalid(self.run_bytes(('{"points": [[%s]]}' % ("9" * 40)).encode()), "digits")

    def test_non_integers(self):
        for bad in ("1.0", "1e0", "NaN", "Infinity", '"1"', "null"):
            text = '{"points": [[%s, 0, 0, 0, 0, 0, 0, 0]]}' % bad
            self.assertInvalid(self.run_bytes(text.encode()))

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"points": [], "points": []}'), "duplicate keys")

    # ---------- hostile input

    def test_oversized_file(self):
        self.assertInvalid(self.run_bytes(b" " * (self.cfg["max_certificate_bytes"] + 1)), "size limit")

    def test_largest_allowed_input_fits_and_is_fast(self):
        pts = [list(p) for p in itertools.product(range(3), repeat=D)][-V.MAX_POINTS:]
        data = json.dumps({"points": pts}).encode()
        self.assertLessEqual(len(data), self.cfg["max_certificate_bytes"])
        self.assertInvalid(self.run_bytes(data), "line")

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
        target.write_text(json.dumps({"points": binary_cube()}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"points": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        res = self.run_bytes(b'{"points": [["<script>", 0, 0, 0, 0, 0, 0, 0]]}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"points": binary_cube()}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "256")
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
        self.assertLessEqual(imported, {"__future__", "hashlib", "json", "os", "stat", "sys",
                                        "tomllib", "fractions", "pathlib"})
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
