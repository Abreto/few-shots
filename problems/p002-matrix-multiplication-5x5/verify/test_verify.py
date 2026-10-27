"""p002 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import copy
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
_spec = importlib.util.spec_from_file_location("fewshots_verify_p002", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

N = 5


def unit(i: int, j: int, value=1) -> list:
    m = [[0] * N for _ in range(N)]
    m[i][j] = value
    return m


def standard() -> list:
    """The schoolbook algorithm: 125 terms E_ij (x) E_jk (x) E_ki."""
    return [[unit(i, j), unit(j, k), unit(k, i)] for i, j, k in itertools.product(range(N), repeat=3)]


def mat(entries: dict) -> list:
    m = [[0] * N for _ in range(N)]
    for (i, j), x in entries.items():
        m[i][j] = x
    return m


def strassen_block() -> list:
    """Strassen's 7 products on the indices {0, 1} plus the 117 remaining schoolbook terms: 124 terms."""
    a = lambda **kw: mat({(int(k[1]) - 1, int(k[2]) - 1): v for k, v in kw.items()})
    # m_r = <U_r, A> <V_r, B>; C = sum_r m_r G_r, and in the trace convention W_r = G_r transposed.
    products = [
        (a(x11=1, x22=1), a(x11=1, x22=1), a(x11=1, x22=1)),
        (a(x21=1, x22=1), a(x11=1), a(x21=1, x22=-1)),
        (a(x11=1), a(x12=1, x22=-1), a(x12=1, x22=1)),
        (a(x22=1), a(x21=1, x11=-1), a(x11=1, x21=1)),
        (a(x11=1, x12=1), a(x22=1), a(x11=-1, x12=1)),
        (a(x21=1, x11=-1), a(x11=1, x12=1), a(x22=1)),
        (a(x12=1, x22=-1), a(x21=1, x22=1), a(x11=1)),
    ]
    out = []
    for u, v, g in products:
        w = [[g[j][i] for j in range(N)] for i in range(N)]
        out.append([u, v, w])
    rest = [[unit(i, j), unit(j, k), unit(k, i)] for i, j, k in itertools.product(range(N), repeat=3)
            if not (i < 2 and j < 2 and k < 2)]
    return out + rest


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

    def test_baseline_multiplies_matrices(self):
        # The documented reading: m_t = <U_t, A> <V_t, B>, and (AB)[i][k] = sum_t m_t W_t[k][i].
        terms = json.loads((ROOT / "baseline" / "certificate.json").read_text())["terms"]
        rng = random.Random(2)
        for _ in range(3):
            A = [[rng.randint(-9, 9) for _ in range(N)] for _ in range(N)]
            B = [[rng.randint(-9, 9) for _ in range(N)] for _ in range(N)]
            ms = [sum(u[i][j] * A[i][j] for i in range(N) for j in range(N))
                  * sum(v[i][j] * B[i][j] for i in range(N) for j in range(N)) for u, v, _ in terms]
            C = [[sum(m * w[k][i] for m, (_, _, w) in zip(ms, terms)) for k in range(N)] for i in range(N)]
            AB = [[sum(A[i][j] * B[j][k] for j in range(N)) for k in range(N)] for i in range(N)]
            self.assertEqual(C, AB)

    def test_standard_algorithm(self):
        res = self.run_obj({"terms": standard()})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "125")

    def test_strassen_block(self):
        res = self.run_obj({"terms": strassen_block()})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "124")

    def test_rational_entries(self):
        terms = strassen_block()
        u, v, w = terms[0]
        terms[0] = [[[f"{x}/2" for x in row] for row in u], [[3 * x for x in row] for row in v],
                    [[f"{2 * x}/3" for x in row] for row in w]]
        res = self.run_obj({"terms": terms})
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "124")

    def test_canonical_hash_ignores_order_scaling_and_spelling(self):
        terms = strassen_block()
        a = self.run_obj({"terms": terms})["canonical_hash"]
        other = copy.deepcopy(list(reversed(terms)))
        u, v, w = other[0]
        other[0] = [[[f"{-2 * x}/4" for x in row] for row in u], [[f"{x}/1" for x in row] for row in v],
                    [[-2 * x for x in row] for row in w]]
        b = self.run_bytes(json.dumps({"terms": other}, indent=2).encode())
        self.assertTrue(b["valid"], b)
        self.assertEqual(a, b["canonical_hash"])
        self.assertNotEqual(a, self.run_obj({"terms": standard()})["canonical_hash"])

    # ---------- invalid certificates

    def test_wrong_decompositions(self):
        terms = standard()
        self.assertInvalid(self.run_obj({"terms": terms[:-1]}), "do not sum")
        bad = copy.deepcopy(terms)
        bad[7][2] = unit(*[(r, c) for r in range(N) for c in range(N) if bad[7][2][r][c]][0], value=-1)
        self.assertInvalid(self.run_obj({"terms": bad}), "1 of 15625")
        # C = AB written without the transpose, W_t = E_ik, is a different tensor
        plain = [[unit(i, j), unit(j, k), unit(i, k)] for i, j, k in itertools.product(range(N), repeat=3)]
        self.assertInvalid(self.run_obj({"terms": plain}), "do not sum")
        # the same term twice is not the same as once
        block = strassen_block()
        self.assertInvalid(self.run_obj({"terms": block + [block[0]]}), "do not sum")

    def test_first_mismatch_is_reported_by_index(self):
        res = self.run_obj({"terms": standard()[1:]})
        self.assertInvalid(res, "U[1][1] V[1][1] W[1][1]")

    def test_zero_factor(self):
        terms = strassen_block()
        terms.append([unit(0, 0), unit(0, 0), [[0] * N for _ in range(N)]])
        self.assertInvalid(self.run_obj({"terms": terms}), "factor matrix is zero")

    def test_wrong_shape(self):
        good = standard()[0]
        self.assertInvalid(self.run_obj([good]), "single key")
        self.assertInvalid(self.run_obj({"terms": [good], "note": "x"}), "single key")
        self.assertInvalid(self.run_obj({"terms": []}), "non-empty")
        self.assertInvalid(self.run_obj({"terms": {"0": good}}), "non-empty")
        self.assertInvalid(self.run_obj({"terms": [good[:2]]}), "three matrices")
        self.assertInvalid(self.run_obj({"terms": [good + [good[0]]]}), "three matrices")
        self.assertInvalid(self.run_obj({"terms": [[good[0][:4], good[1], good[2]]]}), "5 rows")
        self.assertInvalid(self.run_obj({"terms": [[[r[:4] for r in good[0]], good[1], good[2]]]}), "5 entries")
        self.assertInvalid(self.run_obj({"terms": [[1, 2, 3]]}), "5 rows")

    def test_entries(self):
        for bad in (True, None, [1, 2], {"p": 1}, "1.5", "1/0", "abc", " 1/2", "1/2 ", "1/-2", "+1/2",
                    "1", "1//2", "1/2\n", "\u0661/2", "0x1/2",
                    "-/2", "1/", "/2", "--1/2", "1/2/3", "1/2\u0000"):
            with self.subTest(bad=bad):
                terms = standard()
                terms[0][0][0][0] = bad
                res = self.run_obj({"terms": terms})
                self.assertInvalid(res, "zero" if bad == "1/0" else "")
                if bad != "1/0":
                    self.assertIn("JSON integer or a string", res["message"])

    def test_non_integers_in_json(self):
        for bad in ("1.5", "1e3", "-0.0", "NaN", "Infinity", "-Infinity"):
            text = json.dumps({"terms": standard()}).replace("1", bad, 1)
            self.assertInvalid(self.run_bytes(text.encode()))

    def test_bounds(self):
        for bad in (10**9 + 1, -(10**9) - 1, "1000000001/2", "1/1000000001"):
            terms = standard()
            terms[0][0][0][0] = bad
            self.assertInvalid(self.run_obj({"terms": terms}), "bound")
        terms = standard()
        terms[0][0][0][0] = "1/999999937"
        terms[1][0][0][1] = "1/999999929"
        terms[2][0][0][2] = "1/3"
        self.assertInvalid(self.run_obj({"terms": terms}), "least common multiple")
        self.assertInvalid(self.run_bytes(('{"terms": [[[[%s]]]]}' % ("9" * 40)).encode()), "digits")
        self.assertInvalid(self.run_obj({"terms": [f"{'9' * 19}/1"]}), "three matrices")
        terms = standard()
        terms[0][0][0][0] = f"{'9' * 19}/1"
        self.assertInvalid(self.run_obj({"terms": terms}), "JSON integer or a string")
        self.assertInvalid(self.run_obj({"terms": standard() + standard()[:1]}), "at most 125")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"terms": [], "terms": []}'), "duplicate keys")

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
        target.write_text(json.dumps({"terms": standard()}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"terms": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        terms = standard()
        terms[0][0][0][0] = "<script>"
        self.assertNotIn("script", self.run_obj({"terms": terms})["message"])

    def test_dense_worst_case_is_fast(self):
        # 125 dense terms with large numerators and the largest allowed common denominator
        terms = [[[[f"{-(10**9) + r * 5 + c}/{(999999937, 999999929)[(r + c + m + t) % 2]}" for c in range(N)]
                   for r in range(N)] for m in range(3)] for t in range(125)]
        data = json.dumps({"terms": terms}, separators=(",", ":")).encode()
        self.assertLessEqual(len(data), self.cfg["max_certificate_bytes"])
        self.assertInvalid(self.run_bytes(data), "do not sum")

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"terms": standard()}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "125")
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
        self.assertLessEqual(imported, {"__future__", "hashlib", "json", "math", "os", "re", "stat", "sys",
                                        "tomllib", "fractions", "pathlib"})
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
