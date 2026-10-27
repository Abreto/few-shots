"""p003 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

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
_spec = importlib.util.spec_from_file_location("fewshots_verify_p003", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)


# ---------- graph helpers (adjacency as a set of edges or as bit masks)

def rows_from_pred(n: int, adjacent) -> list:
    return ["".join("1" if i != j and adjacent(i, j) else "0" for j in range(n)) for i in range(n)]


def rows_from_masks(adj: list) -> list:
    n = len(adj)
    return ["".join("1" if a >> j & 1 else "0" for j in range(n)) for a in adj]


def masks_from_rows(rows: list) -> list:
    return [sum(1 << j for j, c in enumerate(r) if c == "1") for r in rows]


def circulant(n: int, steps) -> list:
    return rows_from_pred(n, lambda i, j: min((i - j) % n, (j - i) % n) in steps)


def disjoint_union(*graphs) -> list:
    out, off = [], 0
    total = sum(len(g) for g in graphs)
    for g in graphs:
        m = len(g)
        out += ["0" * off + r + "0" * (total - off - m) for r in g]
        off += m
    return out


def relabel(rows: list, perm: list) -> list:
    """Vertex k of the new graph is vertex perm[k] of the old one."""
    return ["".join(rows[perm[i]][perm[j]] for j in range(len(rows))) for i in range(len(rows))]


def brute(rows: list, s: int = 4, t: int = 6) -> bool:
    n = len(rows)
    for c in itertools.combinations(range(n), s):
        if all(rows[a][b] == "1" for a, b in itertools.combinations(c, 2)):
            return False
    for c in itertools.combinations(range(n), t):
        if all(rows[a][b] == "0" for a, b in itertools.combinations(c, 2)):
            return False
    return True


def brute_canonical(rows: list) -> tuple:
    n = len(rows)
    return min(tuple(rows[p[i]][p[j]] for i in range(n) for j in range(n))
               for p in itertools.permutations(range(n)))


def creates_k4(adj: list, i: int, j: int) -> bool:
    common = adj[i] & adj[j]
    return any(adj[k] & common for k in V.bits(common))


def greedy_k4_free(n: int, seed: int) -> list:
    """A random maximal K4-free graph."""
    rng = random.Random(seed)
    adj = [0] * n
    pairs = list(itertools.combinations(range(n), 2))
    rng.shuffle(pairs)
    for i, j in pairs:
        if not creates_k4(adj, i, j):
            adj[i] |= 1 << j
            adj[j] |= 1 << i
    return adj


PALEY17 = circulant(17, {1, 2, 4, 8})                                       # K4-free, alpha = 3
CLEBSCH = rows_from_pred(16, lambda i, j: bin(i ^ j).count("1") in (1, 4))  # triangle-free, alpha = 5
C5 = circulant(5, {1})
K3 = circulant(3, {1})


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.cfg = V.load_config(ROOT / "problem.toml")
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.baseline = json.loads((ROOT / "baseline" / "certificate.json").read_text())["adjacency"]

    def tearDown(self):
        self._tmp.cleanup()

    def run_bytes(self, data: bytes) -> dict:
        (self.dir / "certificate.json").write_bytes(data)
        return V.verify_dir(self.dir, self.cfg)

    def run_obj(self, obj) -> dict:
        return self.run_bytes(json.dumps(obj).encode("utf-8"))

    def run_rows(self, rows) -> dict:
        return self.run_obj({"adjacency": rows})

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

    def test_small_valid_graphs(self):
        cases = {
            "single vertex": (["0"], "1"),
            "C5": (C5, "5"),
            "Paley 17": (PALEY17, "17"),
            "Clebsch": (CLEBSCH, "16"),
            "Paley 17 + C5": (disjoint_union(PALEY17, C5), "22"),
            "5 triangles": (disjoint_union(K3, K3, K3, K3, K3), "15"),
            "K3,3 + C5": (disjoint_union(circulant(6, {1, 3}), C5), "11"),
        }
        for name, (rows, score) in cases.items():
            with self.subTest(name):
                res = self.run_rows(rows)
                self.assertTrue(res["valid"], res)
                self.assertEqual(res["score"], score)

    def test_agrees_with_brute_force(self):
        rng = random.Random(46)
        seen = {True: 0, False: 0}
        for _ in range(300):
            n = rng.randint(1, 11)
            p = rng.choice((0.2, 0.4, 0.5, 0.6))
            edges = {(i, j) for i, j in itertools.combinations(range(n), 2) if rng.random() < p}
            rows = rows_from_pred(n, lambda i, j: (min(i, j), max(i, j)) in edges)
            expect = brute(rows)
            seen[expect] += 1
            res = self.run_rows(rows)
            self.assertEqual(res["valid"], expect, (rows, res))
        self.assertGreater(seen[True], 30)
        self.assertGreater(seen[False], 30)

    def test_witnesses_are_correct(self):
        rng = random.Random(7)
        for _ in range(200):
            n = rng.randint(6, 20)
            adj = [0] * n
            for i, j in itertools.combinations(range(n), 2):
                if rng.random() < rng.choice((0.1, 0.8)):
                    adj[i] |= 1 << j
                    adj[j] |= 1 << i
            k = V.find_clique(adj, 4)
            if k is not None:
                self.assertTrue(all(adj[a] >> b & 1 for a, b in itertools.combinations(k, 2)))
            s = V.find_clique(V.complement(adj), 6)
            if s is not None:
                self.assertTrue(all(not adj[a] >> b & 1 for a, b in itertools.combinations(s, 2)))
                self.assertEqual(len(set(s)), 6)

    # ---------- canonical form

    def test_relabelled_baseline_has_the_same_hash(self):
        h = self.run_rows(self.baseline)["canonical_hash"]
        rng = random.Random(35)
        for _ in range(5):
            perm = list(range(35))
            rng.shuffle(perm)
            res = self.run_rows(relabel(self.baseline, perm))
            self.assertTrue(res["valid"], res)
            self.assertEqual(res["canonical_hash"], h)
        _, canon = V.check_certificate({"adjacency": self.baseline}, self.cfg)
        self.assertEqual(canon["labelling"], "canonical")

    def test_canonical_form_matches_brute_force(self):
        rng = random.Random(1)
        graphs = []
        for _ in range(60):
            n = rng.randint(1, 7)
            edges = {(i, j) for i, j in itertools.combinations(range(n), 2) if rng.random() < 0.5}
            graphs.append(rows_from_pred(n, lambda i, j: (min(i, j), max(i, j)) in edges))
        graphs += [C5, circulant(6, {1}), circulant(6, {1, 3}), circulant(7, {1, 2}), disjoint_union(K3, K3)]
        forms = []
        for rows in graphs:
            label, canon = V.canonical_form(masks_from_rows(rows))
            self.assertEqual(label, "canonical")
            perm = list(range(len(rows)))
            rng.shuffle(perm)
            self.assertEqual(V.canonical_form(masks_from_rows(relabel(rows, perm))), (label, canon))
            self.assertEqual(sorted(r.count("1") for r in canon), sorted(r.count("1") for r in rows))
            forms.append((brute_canonical(rows), tuple(canon)))
        for (b1, c1), (b2, c2) in itertools.combinations(forms, 2):
            self.assertEqual(b1 == b2, c1 == c2)

    def test_canonical_form_is_a_relabelling(self):
        rows = self.baseline
        _, canon = V.canonical_form(masks_from_rows(rows))
        self.assertEqual(sorted(r.count("1") for r in canon), sorted(r.count("1") for r in rows))
        self.assertEqual(brute_k3_count(canon), brute_k3_count(rows))

    def test_highly_symmetric_graphs_fall_back_to_given_labelling(self):
        rows = disjoint_union(K3, K3, K3, K3, K3)
        _, canon = V.check_certificate({"adjacency": rows}, self.cfg)
        self.assertEqual(canon, {"labelling": "given", "adjacency": rows})
        res = self.run_rows(rows)
        self.assertEqual(res["canonical_hash"], V.canonical_hash(canon))
        # Clebsch graph (automorphism group of order 1920) still gets a canonical labelling
        h = self.run_rows(CLEBSCH)["canonical_hash"]
        perm = list(range(16))
        random.Random(3).shuffle(perm)
        self.assertEqual(self.run_rows(relabel(CLEBSCH, perm))["canonical_hash"], h)

    def test_hash_ignores_formatting(self):
        a = self.run_rows(self.baseline)["canonical_hash"]
        b = self.run_bytes(json.dumps({"adjacency": self.baseline}, indent=4).encode())["canonical_hash"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, self.run_rows(PALEY17)["canonical_hash"])

    # ---------- invalid certificates

    def test_clique_of_size_4(self):
        self.assertInvalid(self.run_rows(circulant(4, {1, 2})), "clique of size 4")
        self.assertInvalid(self.run_rows(circulant(64, set(range(1, 33)))), "clique of size 4")
        # add one edge to the baseline that closes a K4
        adj = masks_from_rows(self.baseline)
        for i, j in itertools.combinations(range(35), 2):
            if not adj[i] >> j & 1 and creates_k4(adj, i, j):
                adj[i] |= 1 << j
                adj[j] |= 1 << i
                break
        self.assertInvalid(self.run_rows(rows_from_masks(adj)), "clique of size 4")

    def test_independent_set_of_size_6(self):
        self.assertInvalid(self.run_rows(["0" * 6] * 6), "independent set of size 6")
        self.assertInvalid(self.run_rows(disjoint_union(PALEY17, PALEY17)), "independent set of size 6")
        # remove one edge from the baseline that opens an independent 6-set
        adj = masks_from_rows(self.baseline)
        comp = V.complement(adj)
        for i, j in itertools.combinations(range(35), 2):
            if adj[i] >> j & 1:
                trial = list(comp)
                trial[i] |= 1 << j
                trial[j] |= 1 << i
                if V.find_clique(trial, 6) is not None:
                    adj[i] ^= 1 << j
                    adj[j] ^= 1 << i
                    break
        self.assertInvalid(self.run_rows(rows_from_masks(adj)), "independent set of size 6")
        # one more vertex on the baseline, joined to as much as possible without a K4
        adj = masks_from_rows(self.baseline) + [0]
        for u in range(35):
            if not creates_k4(adj, 35, u):
                adj[35] |= 1 << u
                adj[u] |= 1 << 35
        res = self.run_rows(rows_from_masks(adj))
        self.assertFalse(res["valid"], res)

    def test_malformed_matrix(self):
        self.assertInvalid(self.run_rows(["01", "00"]), "not symmetric")
        self.assertInvalid(self.run_rows(["10", "00"]), "diagonal")
        self.assertInvalid(self.run_rows(["01", "1"]), "exactly 2 characters")
        self.assertInvalid(self.run_rows(["012", "100", "200"]), "0 or 1")
        self.assertInvalid(self.run_rows(["0 1", "1 0", "0 0"]), "0 or 1")
        self.assertInvalid(self.run_rows(["0１", "１0"]), "0 or 1")
        self.assertInvalid(self.run_rows([[0, 1], [1, 0]]), "string")
        self.assertInvalid(self.run_rows(["01", 10]), "string")
        self.assertInvalid(self.run_rows([]), "non-empty")
        self.assertInvalid(self.run_rows("0"), "non-empty")
        self.assertInvalid(self.run_rows(["0" * 65] * 65), "at most 64")

    def test_wrong_shape(self):
        self.assertInvalid(self.run_obj(["0"]), "single key")
        self.assertInvalid(self.run_obj({"adjacency": ["0"], "n": 1}), "single key")
        self.assertInvalid(self.run_obj({"graph6": "@"}), "single key")

    def test_non_strings(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "null", "true"):
            self.assertInvalid(self.run_bytes(('{"adjacency": ["0", %s]}' % bad).encode()))
        self.assertInvalid(self.run_bytes(('{"adjacency": [%s]}' % ("9" * 40)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"adjacency": ["0"], "adjacency": ["0"]}'), "duplicate keys")

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
        target.write_text(json.dumps({"adjacency": C5}))
        os.symlink(target, self.dir / "certificate.json")
        self.assertInvalid(V.verify_dir(self.dir, self.cfg), "symbolic links")

    def test_messages_never_echo_input_strings(self):
        res = self.run_bytes(b'{"adjacency": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])
        res = self.run_rows(["<script>", "0"])
        self.assertNotIn("script", res["message"])

    def test_worst_case_time(self):
        full = (1 << 64) - 1
        cases = {
            "baseline": self.baseline,
            "empty 64": ["0" * 64] * 64,
            "complete 64": rows_from_masks([full & ~(1 << i) for i in range(64)]),
            "Turan 64": rows_from_pred(64, lambda i, j: i % 3 != j % 3),
            "K32,32": rows_from_pred(64, lambda i, j: (i < 32) != (j < 32)),
            "hypercube Q6": rows_from_pred(64, lambda i, j: bin(i ^ j).count("1") == 1),
            "5 triangles": disjoint_union(K3, K3, K3, K3, K3),
            "K8,8": rows_from_pred(16, lambda i, j: (i < 8) != (j < 8)),
            "Paley 17 + C5": disjoint_union(PALEY17, C5),
        }
        for n in (40, 52, 64):
            for seed in range(3):
                cases[f"maximal K4-free {n}/{seed}"] = rows_from_masks(greedy_k4_free(n, seed))
        rng = random.Random(9)
        for k in range(10):  # the baseline plus up to five vertices, each joined greedily without a K4
            adj = masks_from_rows(self.baseline)
            for _ in range(1 + k % 5):
                m = len(adj)
                adj = adj + [0]
                order = list(range(m))
                rng.shuffle(order)
                for u in order:
                    if not creates_k4(adj, m, u):
                        adj[m] |= 1 << u
                        adj[u] |= 1 << m
            if k % 2:
                adj = masks_from_rows(relabel(rows_from_masks(adj), list(range(len(adj)))[::-1]))
            cases[f"baseline extension {k}"] = rows_from_masks(adj)
        for name, rows in cases.items():
            with self.subTest(name):
                t = time.perf_counter()
                self.run_rows(rows)
                self.assertLess(time.perf_counter() - t, 10)

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps({"adjacency": PALEY17}))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "17")
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


def brute_k3_count(rows: list) -> int:
    return sum(all(rows[a][b] == "1" for a, b in itertools.combinations(c, 2))
               for c in itertools.combinations(range(len(rows)), 3))


if __name__ == "__main__":
    unittest.main()
