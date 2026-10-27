"""p009 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import copy
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
_spec = importlib.util.spec_from_file_location("fewshots_verify_p009", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

N, M = 30, 20


def taillard_instance(time_seed: int, machine_seed: int, n: int, m: int):
    """Taillard's generator (Taillard 1993, "Benchmarks for basic scheduling problems"):
    Lehmer generator x <- 16807 x mod (2^31 - 1), unif(low, high) = low + floor(x (high - low + 1) / (2^31 - 1))."""
    state = [0]

    def unif(low: int, high: int) -> int:
        x = state[0]
        k = x // 127773
        x = 16807 * (x % 127773) - k * 2836
        if x < 0:
            x += 2147483647
        state[0] = x
        return low + x * (high - low + 1) // 2147483647

    state[0] = time_seed
    durations = [[unif(1, 99) for _ in range(m)] for _ in range(n)]
    state[0] = machine_seed
    routes = []
    for _ in range(n):
        route = list(range(m))
        for j in range(m):
            k = unif(j, m - 1)
            route[j], route[k] = route[k], route[j]
        routes.append(route)
    return routes, durations


def reference_makespan(orders, routes, durations):
    """Independent evaluator: dispatch operations in machine order, None if the orders deadlock."""
    job_next, mach_next = [0] * N, [0] * M
    job_free, mach_free = [0] * N, [0] * M
    done = 0
    while done < N * M:
        progress = False
        for mach in range(M):
            if mach_next[mach] == N:
                continue
            j = orders[mach][mach_next[mach]]
            k = job_next[j]
            if k < M and routes[j][k] == mach:
                t = max(job_free[j], mach_free[mach]) + durations[j][k]
                job_free[j] = mach_free[mach] = t
                job_next[j] += 1
                mach_next[mach] += 1
                done += 1
                progress = True
        if not progress:
            return None
    return max(job_free)


def random_schedule(rng: random.Random, routes, durations):
    """Machine orders of a random non-delay schedule (always acyclic)."""
    job_next, job_free, mach_free = [0] * N, [0] * N, [0] * M
    orders = [[] for _ in range(M)]
    for _ in range(N * M):
        cands = [j for j in range(N) if job_next[j] < M]
        starts = {j: max(job_free[j], mach_free[routes[j][job_next[j]]]) for j in cands}
        t = min(starts.values())
        j = rng.choice([j for j in cands if starts[j] == t])
        mach = routes[j][job_next[j]]
        job_free[j] = mach_free[mach] = t + durations[j][job_next[j]]
        orders[mach].append(j)
        job_next[j] += 1
    return orders


def load_baseline() -> dict:
    return json.loads((ROOT / "baseline" / "certificate.json").read_text(encoding="utf-8"))


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = V.load_config(ROOT / "problem.toml")
        self.inst = self.cfg["instance"]
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

    # ---------- the instance

    def test_instance_matches_taillard_generator(self):
        routes, durations = taillard_instance(1841414609, 1357882888, N, M)
        self.assertEqual(self.inst["routes"], routes)
        self.assertEqual(self.inst["durations"], durations)
        self.assertEqual(sum(map(sum, durations)), 31279)

    def test_generator_reproduces_taillard_ta01_first_row(self):
        # ta01 (15 x 15, seeds 840612802 / 398197754): first job's times and machines from Taillard's file
        routes, durations = taillard_instance(840612802, 398197754, 15, 15)
        self.assertEqual(durations[0], [94, 66, 10, 53, 26, 15, 65, 82, 10, 27, 93, 92, 96, 70, 83])
        self.assertEqual([r + 1 for r in routes[0]], [7, 13, 5, 8, 4, 3, 11, 12, 9, 15, 10, 14, 6, 1, 2])

    # ---------- valid input

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)
        c = load_baseline()
        self.assertEqual(reference_makespan(c["machines"], self.inst["routes"], self.inst["durations"]), 2006)

    def test_baseline_respects_trivial_lower_bounds(self):
        routes, durations = self.inst["routes"], self.inst["durations"]
        job_bound = max(map(sum, durations))
        load = [0] * M
        for j in range(N):
            for k in range(M):
                load[routes[j][k]] += durations[j][k]
        self.assertLessEqual(max(job_bound, max(load)), 2006)

    def test_same_job_order_on_every_machine(self):
        orders = [list(range(N)) for _ in range(M)]
        res = self.run_obj({"machines": orders})
        self.assertTrue(res["valid"], res)
        self.assertEqual(int(res["score"]), reference_makespan(orders, self.inst["routes"], self.inst["durations"]))

    def test_random_schedules_agree_with_reference(self):
        rng = random.Random(41)
        for _ in range(5):
            orders = random_schedule(rng, self.inst["routes"], self.inst["durations"])
            res = self.run_obj({"machines": orders})
            self.assertTrue(res["valid"], res)
            self.assertEqual(int(res["score"]),
                             reference_makespan(orders, self.inst["routes"], self.inst["durations"]))

    def test_canonical_hash(self):
        c = load_baseline()
        a = self.run_obj(c)["canonical_hash"]
        b = self.run_bytes(json.dumps(c, indent=2).encode())["canonical_hash"]
        self.assertEqual(a, b)
        orders = [list(range(N)) for _ in range(M)]
        self.assertNotEqual(a, self.run_obj({"machines": orders})["canonical_hash"])

    # ---------- invalid certificates

    def test_cycle(self):
        routes = self.inst["routes"]
        # find machines p, q with job 0 visiting p before q and job 1 visiting q before p
        pair = next((p, q) for p in range(M) for q in range(M)
                    if routes[0].index(p) < routes[0].index(q) and routes[1].index(q) < routes[1].index(p))
        p, _q = pair
        orders = [list(range(N)) for _ in range(M)]
        orders[p] = [1, 0] + list(range(2, N))
        # 0@p -> 0@q (route), 0@q -> 1@q (machine q), 1@q -> 1@p (route), 1@p -> 0@p (machine p)
        self.assertIsNone(reference_makespan(orders, routes, self.inst["durations"]))
        self.assertInvalid(self.run_obj({"machines": orders}), "cycle")

    def test_baseline_with_one_swap_is_cyclic_or_valid(self):
        c = load_baseline()
        rng = random.Random(7)
        for _ in range(20):
            d = copy.deepcopy(c)
            mach, i = rng.randrange(M), rng.randrange(N - 1)
            o = d["machines"][mach]
            o[i], o[i + 1] = o[i + 1], o[i]
            ref = reference_makespan(d["machines"], self.inst["routes"], self.inst["durations"])
            res = self.run_obj(d)
            if ref is None:
                self.assertInvalid(res, "cycle")
            else:
                self.assertEqual(res["score"], str(ref))

    def test_wrong_shape(self):
        c = load_baseline()
        self.assertInvalid(self.run_obj(c["machines"]), "single key")
        self.assertInvalid(self.run_obj(dict(c, note="x")), "single key")
        self.assertInvalid(self.run_obj({"orders": c["machines"]}), "single key")
        self.assertInvalid(self.run_obj({"machines": c["machines"][:-1]}), "20 job orders")
        self.assertInvalid(self.run_obj({"machines": c["machines"] + [c["machines"][0]]}), "20 job orders")
        self.assertInvalid(self.run_obj({"machines": {}}), "20 job orders")
        for bad in (c["machines"][0][:-1], c["machines"][0] + [0], "0 1 2", None):
            d = copy.deepcopy(c)
            d["machines"][4] = bad
            self.assertInvalid(self.run_obj(d), "list of 30")

    def test_not_a_permutation(self):
        c = load_baseline()
        for k, v in ((0, 30), (0, -1), (3, c["machines"][2][4]), (5, 10**12)):
            d = copy.deepcopy(c)
            d["machines"][2][k] = v
            self.assertInvalid(self.run_obj(d), "permutation")
        for v in (True, "3", [3], None):
            d = copy.deepcopy(c)
            d["machines"][2][1] = v
            self.assertInvalid(self.run_obj(d), "integers")

    def test_non_integers(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "-0.0"):
            row = ", ".join([bad] + [str(j) for j in range(1, N)])
            text = '{"machines": [[%s]]}' % row
            self.assertInvalid(self.run_bytes(text.encode()))
        self.assertInvalid(self.run_bytes(('{"machines": [[%s]]}' % ("9" * 40)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"machines": [], "machines": []}'), "duplicate keys")

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
        target.write_text(json.dumps(load_baseline()))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"machines": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        res = self.run_bytes(b'{"machines": [["<script>"]]}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps(load_baseline()))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "2006")
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
