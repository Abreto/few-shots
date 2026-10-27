"""p004 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

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
import time
import tomllib
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("fewshots_verify_p004", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


def word(digits) -> str:
    return "".join(str(d) for d in digits)


def adjacent(a: str, b: str) -> bool:
    """Reference rule, straight from the definition."""
    return a != b and all((int(x) - int(y)) % 7 in (0, 1, 6) for x, y in zip(a, b))


def brute_independent(points: list) -> bool:
    return len(set(points)) == len(points) and not any(
        adjacent(a, b) for a, b in itertools.combinations(points, 2))


def doubling_set() -> list:
    """{(p, 2p mod 7) : p in Z_7^5}: 16807 points, one in every prefix group; independent, because a
    nonzero difference in {0, +1, -1}^5 doubles to a difference with some coordinate equal to +2 or -2."""
    return [word(p + tuple(2 * x % 7 for x in p)) for p in itertools.product(range(7), repeat=5)]


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

    def run_points(self, points) -> dict:
        return self.run_obj({"points": list(points)})

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

    def test_single_point(self):
        self.assertEqual(self.run_points(["0000000000"])["score"], "1")

    def test_cube_of_0_2_4(self):
        # {0, 2, 4} is independent in C7, so {0, 2, 4}^3 x {0}^7 is independent in C7^10
        pts = [word(c + (0,) * 7) for c in itertools.product((0, 2, 4), repeat=3)]
        self.assertEqual(self.run_points(pts)["score"], "27")
        pts = [word((0,) * 7 + c) for c in itertools.product((0, 2, 4), repeat=3)]
        self.assertEqual(self.run_points(pts)["score"], "27")

    def test_doubling_set_fills_every_prefix_group(self):
        res = self.run_points(doubling_set())
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "16807")

    def test_baseline_subsets_stay_valid(self):
        pts = json.loads((ROOT / "baseline" / "certificate.json").read_text())["points"]
        rng = random.Random(4)
        sub = rng.sample(pts, 500)
        self.assertEqual(self.run_points(sub)["score"], "500")

    def test_agrees_with_brute_force(self):
        rng = random.Random(2026)
        seen = {True: 0, False: 0}
        for trial in range(400):
            alphabet = rng.choice(([0, 1, 2, 6], [0, 2, 4], [0, 1, 3, 5], list(range(7))))
            n = rng.randint(2, 12)
            pts = list({word(rng.choice(alphabet) for _ in range(10)) for _ in range(n)})
            if trial % 3 == 0:  # plant a near pair: change some coordinates by 0, +1 or -1
                base = [int(c) for c in pts[0]]
                pts.append(word((d + rng.choice((-1, 0, 0, 1, 2))) % 7 for d in base))
                pts = list(dict.fromkeys(pts))
            expect = brute_independent(pts)
            seen[expect] += 1
            res = self.run_points(pts)
            self.assertEqual(res["valid"], expect, (pts, res))
            if expect:
                self.assertEqual(res["score"], str(len(pts)))
        self.assertGreater(seen[True], 20)
        self.assertGreater(seen[False], 20)

    def test_canonical_hash_ignores_order_and_formatting(self):
        pts = doubling_set()[:300]
        a = self.run_points(pts)["canonical_hash"]
        b = self.run_bytes(json.dumps({"points": list(reversed(pts))}, indent=2).encode())["canonical_hash"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, self.run_points(pts[:-1])["canonical_hash"])

    def test_canonical_form_is_sorted_base7_integers(self):
        pts = ["0000000030", "0000000002", "3000000000"]
        canon = {"points": sorted(int(p, 7) for p in pts)}
        self.assertEqual(self.run_points(pts)["canonical_hash"], V.canonical_hash(canon))

    def test_neighbour_masks_match_definition(self):
        nm = V.NeighbourMasks()
        rng = random.Random(7)
        for idx in [0, 1, 6, 7, 16806, 2400] + [rng.randrange(16807) for _ in range(20)]:
            d = V.half_digits(idx)
            self.assertEqual(int(word(d), 7), idx)
            expect = {j for j in range(16807)
                      if all((a - b) % 7 in (0, 1, 6) for a, b in zip(d, V.half_digits(j)))}
            self.assertEqual(set(V.neighbour_indices(idx)), expect)
            mask = nm.mask(d)
            self.assertEqual({j for j in range(16807) if mask >> j & 1}, expect)

    # ---------- invalid certificates

    def test_adjacent_pairs(self):
        a = "0000000000"
        for b in ("1000000000", "6000000000", "0000000001", "0000000006", "6666666666", "1111111111",
                  "1616161616", "0000010000", "0000100000"):
            with self.subTest(b):
                self.assertInvalid(self.run_points([a, b]), "adjacent")
        # adjacency needs every coordinate to be close: one coordinate at distance 2 or 3 separates
        for b in ("2000000000", "5000000000", "3111111111", "1111141111", "1111111114", "6666662666"):
            with self.subTest(b):
                self.assertEqual(self.run_points([a, b])["score"], "2")

    def test_conflict_found_in_last_group(self):
        pts = doubling_set()
        last = [int(c) for c in pts[-1]]
        last[9] = (last[9] + 1) % 7
        self.assertInvalid(self.run_points(pts + [word(last)]), "adjacent")
        last = [int(c) for c in pts[-1]]
        last[0] = (last[0] + 1) % 7
        last[9] = (last[9] + 1) % 7
        self.assertInvalid(self.run_points([word(last)] + pts), "adjacent")

    def test_identical_points(self):
        self.assertInvalid(self.run_points(["0123456012", "0123456012"]), "identical")

    def test_wrong_shape(self):
        self.assertInvalid(self.run_obj(["0000000000"]), "single key")
        self.assertInvalid(self.run_obj({"points": ["0000000000"], "note": "x"}), "single key")
        self.assertInvalid(self.run_obj({"vectors": ["0000000000"]}), "single key")
        self.assertInvalid(self.run_obj({"points": []}), "non-empty")
        self.assertInvalid(self.run_obj({"points": "0000000000"}), "non-empty")
        for bad in ("000000000", "00000000000", "0000000007", "000000000a", " 000000000", "+000000000",
                    "-000000000", "0_00000000", "０" * 10, "٣" * 10, "", 123, 0, None, True,
                    [0] * 10):
            with self.subTest(bad):
                self.assertInvalid(self.run_points(["0000000000", bad]), "10 characters")

    def test_too_many_points(self):
        pts = ["0000000000"] * (V.MAX_POINTS + 1)
        self.assertInvalid(self.run_points(pts), "at most")

    def test_non_strings(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "null", "true"):
            text = '{"points": ["0000000000", %s]}' % bad
            self.assertInvalid(self.run_bytes(text.encode()))
        self.assertInvalid(self.run_bytes(('{"points": [%s]}' % ("9" * 40)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"points": ["0000000000"], "points": ["0000000000"]}'),
                           "duplicate keys")

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
        target.write_text(json.dumps({"points": ["0000000000"]}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"points": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        res = self.run_points(["0000000000", "<script>x"])
        self.assertNotIn("script", res["message"])

    def test_worst_case_time(self):
        # every prefix group non-empty, 11 suffixes per group, maximal file: all masks and all
        # 16807 x 242 group pairs are touched before the first conflict can be reported
        pts = doubling_set()
        lifts = [(0, 0, 0, 0, 0), (3, 3, 3, 3, 3), (0, 3, 0, 3, 0), (3, 0, 3, 0, 3), (0, 0, 3, 3, 0),
                 (3, 3, 0, 0, 3), (2, 4, 2, 4, 2), (4, 2, 4, 2, 4), (2, 2, 4, 4, 2), (4, 4, 2, 2, 4), (0, 2, 4, 3, 0)]
        big = [p[:5] + word((int(c) + o) % 7 for c, o in zip(p[5:], off)) for off in lifts for p in pts]
        big = big[:V.MAX_POINTS]
        for name, cert in (("doubling", pts), ("spread", big), ("baseline", None)):
            with self.subTest(name):
                if cert is None:
                    data = (ROOT / "baseline" / "certificate.json").read_bytes()
                else:
                    data = json.dumps({"points": cert}).encode()
                self.assertLessEqual(len(data), self.cfg["max_certificate_bytes"])
                t = time.perf_counter()
                self.run_bytes(data)
                self.assertLess(time.perf_counter() - t, 10)

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        pts = [word(c + (0,) * 7) for c in itertools.product((0, 2, 4), repeat=3)]
        (self.dir / "certificate.json").write_text(json.dumps({"points": pts}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "27")
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
