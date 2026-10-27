"""每道题目录的约定：目录名、problem.toml、PROBLEM.md 固定表头、验证器镜像、基线可复现。"""

from __future__ import annotations

import re
import tomllib
import unittest

from helpers import ROOT, SANDBOX, F

SECTIONS = ("## Problem", "## Why it matters", "## Certificate", "## Baseline")


class ProblemDirsTest(unittest.TestCase):
    def setUp(self):
        self.names = F.list_problem_dirs(ROOT)

    def test_problems_dir_contains_only_problem_dirs(self):
        self.assertIn(SANDBOX, self.names)
        entries = sorted(p.name for p in (ROOT / "problems").iterdir())
        self.assertEqual(entries, self.names)

    def test_each_problem(self):
        for name in self.names:
            with self.subTest(name):
                d = ROOT / "problems" / name
                p = F.load_problem_dir(ROOT, name)
                self.assertEqual(f"{p.id}-{p.slug}", name)
                for rel in ("PROBLEM.md", "problem.toml", "FEWSHOT.md", ".dockerignore", "baseline/certificate.json",
                            "verify/verify.py", "verify/Dockerfile", "verify/test_verify.py"):
                    self.assertTrue((d / rel).is_file(), rel)
                allowed = {"PROBLEM.md", "problem.toml", "FEWSHOT.md", ".dockerignore", "baseline", "verify", "shots"}
                self.assertLessEqual({c.name for c in d.iterdir() if c.name != "__pycache__"}, allowed)

    def test_problem_md_opens_with_the_fixed_header(self):
        for name in self.names:
            with self.subTest(name):
                p = F.load_problem_dir(ROOT, name)
                text = (ROOT / "problems" / name / "PROBLEM.md").read_text(encoding="utf-8")
                header = F.render_problem_header(p)
                self.assertTrue(text.startswith(f"# {p.id} · "), text[:40])
                # 标题之后紧接着就是固定表头，内容与 problem.toml 一致
                self.assertEqual(text.split("\n\n", 2)[1], header)
                self.assertEqual(text.count(F.HEADER_START), 1)
                last = -1
                for h in SECTIONS:
                    self.assertIn(f"\n{h}\n", text)
                    self.assertGreater(text.index(f"\n{h}\n"), last, h)
                    last = text.index(f"\n{h}\n")

    def test_header_format_is_machine_readable(self):
        p = F.load_problem_dir(ROOT, SANDBOX)
        rows = dict(re.findall(r"^\| (\w+) \| (.+) \|$", F.render_problem_header(p), re.M))
        self.assertEqual(list(rows), ["key", "id", "metric", "direction", "baseline", "epsilon", "verifier"])
        self.assertEqual(rows["verifier"], f"`python3 problems/{SANDBOX}/verify/verify.py <shot_dir>`")
        self.assertEqual(rows["baseline"], "`2047`")

    def test_verifier_image(self):
        for name in self.names:
            with self.subTest(name):
                d = ROOT / "problems" / name
                text = (d / "verify" / "Dockerfile").read_text(encoding="utf-8")
                self.assertRegex(text, r"(?m)^FROM python:3\.12\.\d+-slim-\w+@sha256:[0-9a-f]{64}$")
                self.assertIn("USER 65534:65534", text)
                self.assertIn("COPY problem.toml /verifier/problem.toml", text)
                lines = (d / ".dockerignore").read_text(encoding="utf-8").split()
                self.assertEqual([ln for ln in lines if not ln.startswith("#")][-3:],
                                 ["*", "!problem.toml", "!verify/verify.py"])

    def test_baseline_reproduces(self):
        for name in self.names:
            with self.subTest(name):
                p = F.load_problem_dir(ROOT, name)
                d = ROOT / "problems" / name
                res = F.run_verifier_local(d / "baseline", p.verifier_timeout_sec, d / "verify" / "verify.py")
                self.assertTrue(res["valid"], res)
                with open(d / "problem.toml", "rb") as f:
                    kind = tomllib.load(f).get("baseline_kind", "certificate")
                self.assertIn(kind, ("certificate", "literature"))
                if kind == "certificate":
                    self.assertEqual(res["score"], p.baseline)
                else:
                    # 基线取文献纪录；baseline/ 里是能复现的最好公开证书，不能比基线更好
                    self.assertTrue(F.at_least(p.direction, p.baseline, res["score"]), res)

    def test_sandbox(self):
        p = F.load_problem_dir(ROOT, SANDBOX)
        self.assertTrue(p.sandbox)
        self.assertIn("sandbox problem", (ROOT / "problems" / SANDBOX / "PROBLEM.md").read_text(encoding="utf-8"))

    def test_load_problem_dir_rejects_bad_names(self):
        for bad in ("../p000-sandbox", "p000", "p000-sandbox/", "", "p001-sandbox"):
            with self.subTest(bad), self.assertRaises(F.ConfigError):
                F.load_problem_dir(ROOT, bad)


if __name__ == "__main__":
    unittest.main()
