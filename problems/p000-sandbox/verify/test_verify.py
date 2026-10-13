"""p000 验证器单元测试：合法、非法与恶意输入。运行：python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import importlib.util
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
_spec = importlib.util.spec_from_file_location("fewshots_verify", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

OPTIMAL_12 = [0, 2, 6, 24, 29, 40, 43, 55, 68, 75, 76, 85]


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

    def run_text(self, text: str) -> dict:
        return self.run_bytes(text.encode("utf-8"))

    def assertInvalid(self, res: dict, fragment: str = ""):
        self.assertFalse(res["valid"], res)
        self.assertIsNone(res["score"])
        self.assertIsNone(res["canonical_hash"])
        self.assertIn(fragment, res["message"])

    # ---------- 合法输入

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)

    def test_known_optimal_ruler(self):
        res = self.run_text(json.dumps({"marks": OPTIMAL_12}))
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "85")
        self.assertRegex(res["canonical_hash"], r"^[0-9a-f]{64}$")

    def test_optional_n_and_unsorted_and_negative(self):
        marks = [m - 50 for m in reversed(OPTIMAL_12)]
        res = self.run_text(json.dumps({"n": 12, "marks": marks}))
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "85")

    def test_canonical_hash_ignores_shift_mirror_order_and_formatting(self):
        a = self.run_text(json.dumps({"marks": OPTIMAL_12}))["canonical_hash"]
        mirror = [85 - m + 1000 for m in OPTIMAL_12]
        b = self.run_text(json.dumps({"marks": mirror}, indent=4))["canonical_hash"]
        c = self.run_text('{"n":12,"marks":%s}' % json.dumps(sorted(OPTIMAL_12, reverse=True)))["canonical_hash"]
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        other = self.run_text(json.dumps({"marks": [2**k - 1 for k in range(12)]}))["canonical_hash"]
        self.assertNotEqual(a, other)

    def test_exactly_at_size_limit_is_ok(self):
        body = json.dumps({"marks": OPTIMAL_12})
        data = body.encode() + b" " * (self.cfg["max_certificate_bytes"] - len(body))
        self.assertEqual(len(data), self.cfg["max_certificate_bytes"])
        self.assertTrue(self.run_bytes(data)["valid"])

    # ---------- 不合规的证书

    def test_duplicate_marks(self):
        self.assertInvalid(self.run_text(json.dumps({"marks": OPTIMAL_12[:-1] + [0]})), "重复")

    def test_repeated_difference(self):
        marks = list(range(12))  # 差值 1 出现多次
        self.assertInvalid(self.run_text(json.dumps({"marks": marks})), "不是 Golomb 尺")

    def test_wrong_count(self):
        self.assertInvalid(self.run_text(json.dumps({"marks": OPTIMAL_12[:11]})), "恰好有 12 个")
        self.assertInvalid(self.run_text(json.dumps({"marks": OPTIMAL_12 + [200]})), "恰好有 12 个")

    def test_n_mismatch(self):
        self.assertInvalid(self.run_text(json.dumps({"n": 11, "marks": OPTIMAL_12})), "n 必须等于")
        self.assertInvalid(self.run_text('{"n": true, "marks": %s}' % json.dumps(OPTIMAL_12)), "n 必须等于")

    def test_non_integer_marks(self):
        for bad in ("1.5", "1.0", "1e3", "-0.0", '"3"', "true", "null", "[1]", "{}"):
            text = '{"marks": [%s, %s]}' % (bad, ", ".join(str(m) for m in OPTIMAL_12[1:]))
            res = self.run_text(text)
            self.assertInvalid(res)

    def test_nan_and_infinity(self):
        for bad in ("NaN", "Infinity", "-Infinity"):
            res = self.run_text('{"marks": [%s, 2, 6, 24, 29, 40, 43, 55, 68, 75, 76, 85]}' % bad)
            self.assertInvalid(res, "NaN")

    def test_huge_integers(self):
        res = self.run_text('{"marks": [%s, 2, 6, 24, 29, 40, 43, 55, 68, 75, 76, 85]}' % ("9" * 5000))
        self.assertInvalid(res, "位")
        res = self.run_text('{"marks": [%d, 2, 6, 24, 29, 40, 43, 55, 68, 75, 76, 85]}' % (10**15 + 1))
        self.assertInvalid(res, "上限")

    def test_wrong_shape(self):
        self.assertInvalid(self.run_text(json.dumps(OPTIMAL_12)), "JSON 对象")
        self.assertInvalid(self.run_text(json.dumps({"marks": "0,2,6"})), "整数数组")
        self.assertInvalid(self.run_text(json.dumps({"marks": OPTIMAL_12, "note": "hi"})), "只允许")
        self.assertInvalid(self.run_text("{}"), "整数数组")

    def test_duplicate_keys(self):
        text = '{"marks": [1, 2], "marks": %s}' % json.dumps(OPTIMAL_12)
        self.assertInvalid(self.run_text(text), "重复的键")

    # ---------- 恶意输入

    def test_oversized_file(self):
        data = b" " * (self.cfg["max_certificate_bytes"] + 1)
        self.assertInvalid(self.run_bytes(data), "大小上限")
        big = b'{"marks": [' + b"0, " * 1_000_000 + b"1]}"
        self.assertInvalid(self.run_bytes(big), "大小上限")

    def test_deeply_nested_json(self):
        for depth in (9, 50, 30000):
            text = "[" * depth + "]" * depth
            self.assertInvalid(self.run_text(text), "嵌套")
        text = '{"marks": %s}' % ("[" * 20000 + "]" * 20000)
        self.assertInvalid(self.run_text(text), "嵌套")

    def test_brackets_inside_strings_do_not_count_as_nesting(self):
        text = '{"marks": %s, "x": "[[[[[[[[[[[["}' % json.dumps(OPTIMAL_12)
        self.assertInvalid(self.run_text(text), "只允许")  # 因多余键被拒，而不是嵌套

    def test_not_json_or_not_utf8(self):
        self.assertInvalid(self.run_bytes(b""), "合法的 JSON")
        self.assertInvalid(self.run_bytes(b"\xff\xfe{}"), "UTF-8")
        self.assertInvalid(self.run_bytes(b"\xef\xbb\xbf" + json.dumps({"marks": OPTIMAL_12}).encode()), "合法的 JSON")
        self.assertInvalid(self.run_text("{'marks': [1]}"), "合法的 JSON")
        self.assertInvalid(self.run_text('__import__("os").system("id")'), "合法的 JSON")

    def test_missing_file(self):
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "缺少")

    def test_symlink_and_directory_rejected(self):
        target = self.dir / "real.json"
        target.write_text(json.dumps({"marks": OPTIMAL_12}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "符号链接")
        os.remove(self.dir / "certificate.json")
        (self.dir / "certificate.json").mkdir()
        self.assertInvalid(V.verify_dir(self.dir, self.cfg))

    def test_messages_never_echo_input_strings(self):
        res = self.run_text('{"marks": [0], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])

    # ---------- 命令行契约

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"marks": OPTIMAL_12}))
        for _ in range(2):
            proc = self.run_cli(str(self.dir))
            self.assertEqual(proc.returncode, 0)
            lines = proc.stdout.decode("utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
            self.assertTrue(obj["valid"])
            self.assertEqual(obj["score"], "85")
            (self.dir / "certificate.json").write_text("[" * 100000)
            proc = self.run_cli(str(self.dir))
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(len(proc.stdout.splitlines()), 1)
            self.assertFalse(json.loads(proc.stdout)["valid"])
            self.assertEqual(proc.stderr, b"")
            (self.dir / "certificate.json").write_text(json.dumps({"marks": OPTIMAL_12}))

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
        # 导入已限定在白名单内（没有 pickle / yaml / sympy），这里再禁止求值类调用
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
