"""p006 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import importlib.util
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
_spec = importlib.util.spec_from_file_location("fewshots_verify_p006", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

N = 100


def naive_energy(seq: str) -> int:
    """Independent reference: E = sum_k C_k^2 straight from the definition."""
    s = [1 if ch == "+" else -1 for ch in seq]
    n = len(s)
    return sum(sum(s[i] * s[i + k] for i in range(n - k)) ** 2 for k in range(1, n))


def random_sequence(rng: random.Random) -> str:
    return "".join(rng.choice("+-") for _ in range(N))


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
        self.assertEqual(baseline, "578")

    def test_constant_sequence(self):
        # all +1: C_k = N - k, so E = sum_{m=1}^{N-1} m^2 = (N-1) N (2N-1) / 6
        res = self.run_obj({"sequence": "+" * N})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], str((N - 1) * N * (2 * N - 1) // 6))
        # strictly alternating is the alternation image of the constant sequence: same energy
        self.assertEqual(self.run_obj({"sequence": "+-" * (N // 2)})["score"], res["score"])

    def test_energy_matches_reference_on_random_sequences(self):
        rng = random.Random(6)
        for _ in range(20):
            seq = random_sequence(rng)
            res = self.run_obj({"sequence": seq})
            self.assertTrue(res["valid"], res)
            self.assertEqual(res["score"], str(naive_energy(seq)))

    def test_small_known_energies(self):
        # The length-13 Barker code has |C_k| <= 1 and E = 6; the energy function itself is length-agnostic
        barker13 = "+++++--++-+-+"
        self.assertEqual(V.energy([1 if c == "+" else -1 for c in barker13]), 6)
        self.assertEqual(V.energy([1, 1, 1, -1]), 2)   # Barker 4: C = (1, 0, -1)
        self.assertEqual(V.energy([1]), 0)

    def test_symmetries_preserve_energy_and_hash(self):
        rng = random.Random(1)
        seq = random_sequence(rng)
        orbit = V.symmetry_orbit(seq)
        self.assertEqual(len(orbit), 8)
        ref = self.run_obj({"sequence": seq})
        for t in orbit:
            res = self.run_obj({"sequence": t})
            self.assertEqual(res["score"], ref["score"])
            self.assertEqual(res["canonical_hash"], ref["canonical_hash"])
            # the orbit is closed: every member has the same orbit
            self.assertEqual(set(V.symmetry_orbit(t)), set(orbit))
        self.assertEqual(V.canonical_sequence(seq), min(orbit))

    def test_canonical_hash_ignores_formatting(self):
        seq = random_sequence(random.Random(2))
        a = self.run_obj({"sequence": seq})["canonical_hash"]
        b = self.run_bytes(json.dumps({"sequence": seq}, indent=4).encode())["canonical_hash"]
        self.assertEqual(a, b)
        other = ("-" if seq[50] == "+" else "+").join((seq[:50], seq[51:]))
        self.assertNotEqual(a, self.run_obj({"sequence": other})["canonical_hash"])

    # ---------- invalid certificates

    def test_wrong_shape(self):
        good = "+" * N
        self.assertInvalid(self.run_obj([good]), "single key")
        self.assertInvalid(self.run_obj({"sequence": good, "note": "x"}), "single key")
        self.assertInvalid(self.run_obj({"seq": good}), "single key")
        self.assertInvalid(self.run_obj({"sequence": [1] * N}), "string")
        self.assertInvalid(self.run_obj({"sequence": None}), "string")
        self.assertInvalid(self.run_obj({"sequence": 1}), "string")

    def test_wrong_length(self):
        for n in (0, 1, N - 1, N + 1, 2 * N):
            self.assertInvalid(self.run_obj({"sequence": "+" * n}), "exactly 100")

    def test_bad_characters(self):
        for bad in ("0", "1", " ", "x", "−", "±", "\x00"):
            seq = "+" * (N - 1) + bad
            self.assertInvalid(self.run_obj({"sequence": seq}), "only the characters")

    def test_duplicate_keys(self):
        good = "+" * N
        text = '{"sequence": "%s", "sequence": "%s"}' % (good, good)
        self.assertInvalid(self.run_bytes(text.encode()), "duplicate keys")

    def test_numbers_are_not_accepted(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "null", "true"):
            self.assertInvalid(self.run_bytes(('{"sequence": %s}' % bad).encode()))
        self.assertInvalid(self.run_bytes(('{"sequence": %s}' % ("9" * 40)).encode()), "digits")

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
        target.write_text(json.dumps({"sequence": "+" * N}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"sequence": "<script>alert(1)</script>"}')
        self.assertNotIn("script", res["message"])
        res = self.run_bytes(b'{"<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"sequence": "+" * N}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "328350")
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
