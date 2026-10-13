#!/usr/bin/env python3
"""运行全部测试：tests/test_*.py 与每道题的 problems/<题目>/verify/test_verify.py。只用标准库。

用法：python3 tools/run_tests.py [-v]
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def problem_suites(loader: unittest.TestLoader) -> list:
    """每道题的验证器测试文件同名（test_verify.py），按题目目录分别加载成不同的模块。"""
    suites = []
    for path in sorted((ROOT / "problems").glob("*/verify/test_verify.py")):
        name = "verify_tests_" + path.parent.parent.name.replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        suites.append(loader.loadTestsFromModule(module))
    return suites


def main() -> int:
    verbosity = 2 if "-v" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(start_dir=str(ROOT / "tests"), pattern="test_*.py",
                                   top_level_dir=str(ROOT / "tests")))
    suite.addTests(problem_suites(loader))
    result = unittest.TextTestRunner(verbosity=verbosity, buffer=True).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
