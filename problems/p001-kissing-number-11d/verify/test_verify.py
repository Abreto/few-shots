"""p001 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("fewshots_verify_p001", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


def d11_roots() -> list:
    """The 220 vectors ±e_i ± e_j of the D11 root system: a valid kissing configuration."""
    out = []
    for i, j in itertools.combinations(range(11), 2):
        for si, sj in itertools.product((1, -1), repeat=2):
            v = [[0, 0] for _ in range(11)]
            v[i] = [si, 0]
            v[j] = [sj, 0]
            out.append(v)
    return out


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

    def test_d11_root_system(self):
        res = self.run_obj({"vectors": d11_roots()})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "220")

    def test_sqrt2_coordinates(self):
        # e1 and (1/sqrt2)(e1 + e2) scaled by sqrt2: (sqrt2, 0) and (1, 1); norm 2, inner product sqrt2 > 1 -> 45 degrees
        close = [[[0, 1], [0, 0]] + [[0, 0]] * 9, [[1, 0], [1, 0]] + [[0, 0]] * 9]
        self.assertInvalid(self.run_obj({"vectors": close}), "60 degrees")
        # (sqrt2, 0) and (0, sqrt2): orthogonal, fine
        ok = [[[0, 1], [0, 0]] + [[0, 0]] * 9, [[0, 0], [0, 1]] + [[0, 0]] * 9]
        self.assertEqual(self.run_obj({"vectors": ok})["score"], "2")

    def test_exactly_60_degrees_is_allowed(self):
        a = [[1, 0], [1, 0]] + [[0, 0]] * 9
        b = [[1, 0], [0, 0], [1, 0]] + [[0, 0]] * 8
        self.assertEqual(self.run_obj({"vectors": [a, b]})["score"], "2")

    def test_canonical_hash_ignores_order_and_formatting(self):
        vs = d11_roots()
        a = self.run_obj({"vectors": vs})["canonical_hash"]
        b = self.run_bytes(json.dumps({"vectors": list(reversed(vs))}, indent=2).encode())["canonical_hash"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, self.run_obj({"vectors": vs[:-1]})["canonical_hash"])

    def test_sign_q2(self):
        for a, b in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (3, -2), (-3, 2), (2, -2), (-2, 2), (7, -5), (-7, 5)]:
            exact = V.sign_q2(a, b)
            approx = a + b * 2 ** 0.5
            self.assertEqual(exact, (approx > 0) - (approx < 0), (a, b))

    # ---------- invalid certificates

    def test_overlap(self):
        vs = d11_roots()
        vs.append([[1, 0], [1, 0], [1, 0], [1, 0]] + [[0, 0]] * 7)  # norm 4, not 2
        self.assertInvalid(self.run_obj({"vectors": vs}), "same squared norm")
        vs = d11_roots()[:3]
        vs.append([[1, 0], [0, 0]] + [[0, 0]] * 9)
        self.assertInvalid(self.run_obj({"vectors": vs}), "same squared norm")

    def test_duplicate_and_zero(self):
        vs = d11_roots()
        self.assertInvalid(self.run_obj({"vectors": vs + [vs[5]]}), "identical")
        self.assertInvalid(self.run_obj({"vectors": [[[0, 0]] * 11]}), "zero vector")

    def test_wrong_shape(self):
        good = d11_roots()[0]
        self.assertInvalid(self.run_obj([good]), "single key")
        self.assertInvalid(self.run_obj({"vectors": [good], "note": "x"}), "single key")
        self.assertInvalid(self.run_obj({"vectors": []}), "non-empty")
        self.assertInvalid(self.run_obj({"vectors": [good[:10]]}), "11 coordinates")
        self.assertInvalid(self.run_obj({"vectors": [[1] * 11]}), "pair of integers")
        self.assertInvalid(self.run_obj({"vectors": [[[1, 0, 0]] * 11]}), "pair of integers")
        self.assertInvalid(self.run_obj({"vectors": [[[True, 0]] * 11]}), "pair of integers")

    def test_bounds(self):
        self.assertInvalid(self.run_obj({"vectors": [[[10**9 + 1, 0]] + [[0, 0]] * 10]}), "bound")
        self.assertInvalid(self.run_bytes(('{"vectors": [[[%s, 0]]]}' % ("9" * 40)).encode()), "digits")
        too_many = [[[1, 0]] + [[0, 0]] * 10] * (V.MAX_VECTORS + 1)
        self.assertInvalid(self.run_obj({"vectors": too_many}), "at most")

    def test_non_integers(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", '"1"', "null"):
            text = '{"vectors": [[[%s, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]]}' % bad
            self.assertInvalid(self.run_bytes(text.encode()))

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"vectors": [], "vectors": []}'), "duplicate keys")

    # ---------- hostile input

    def test_oversized_file(self):
        self.assertInvalid(self.run_bytes(b" " * (self.cfg["max_certificate_bytes"] + 1)), "size limit")

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
        target.write_text(json.dumps({"vectors": d11_roots()}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"vectors": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"vectors": d11_roots()}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "220")
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
