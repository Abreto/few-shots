"""p008 verifier tests: valid, invalid and hostile inputs. Run with: python3 tools/run_tests.py"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
_spec = importlib.util.spec_from_file_location("fewshots_verify_p008", HERE / "verify.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

# The 113-gate circuit of the Circuit Minimization Team page (Boyar and Peralta, improved by Calik):
# https://www.cs.yale.edu/homes/peralta/CircuitStuff/SLP_AES_113.txt
# Notation there: U0 is the most significant input bit, S0 the most significant output bit,
# "+" is XOR, "x" is AND, "#" is XNOR.
CMT_113 = """
y14 = U3 + U5
y13 = U0 + U6
y9 = U0 + U3
y8 = U0 + U5
t0 = U1 + U2
y1 = t0 + U7
y4 = y1 + U3
y12 = y13 + y14
y2 = y1 + U0
y5 = y1 + U6
y3 = y5 + y8
t1 = U4 + y12
y15 = t1 + U5
y20 = t1 + U1
y6 = y15 + U7
y10 = y15 + t0
y11 = y20 + y9
y7 = U7 + y11
y17 = y10 + y11
y19 = y10 + y8
y16 = t0 + y11
y21 = y13 + y16
y18 = U0 + y16
t2 = y12 x y15
t3 = y3 x y6
t4 = t3 + t2
t5 = y4 x U7
t6 = t5 + t2
t7 = y13 x y16
t8 = y5 x y1
t9 = t8 + t7
t10 = y2 x y7
t11 = t10 + t7
t12 = y9 x y11
t13 = y14 x y17
t14 = t13 + t12
t15 = y8 x y10
t16 = t15 + t12
t17 = t4 + y20
t18 = t6 + t16
t19 = t9 + t14
t20 = t11 + t16
t21 = t17 + t14
t22 = t18 + y19
t23 = t19 + y21
t24 = t20 + y18
t25 = t21 + t22
t26 = t21 x t23
t27 = t24 + t26
t28 = t25 x t27
t29 = t28 + t22
t30 = t23 + t24
t31 = t22 + t26
t32 = t31 x t30
t33 = t32 + t24
t34 = t23 + t33
t35 = t27 + t33
t36 = t24 x t35
t37 = t36 + t34
t38 = t27 + t36
t39 = t29 x t38
t40 = t25 + t39
t41 = t40 + t37
t42 = t29 + t33
t43 = t29 + t40
t44 = t33 + t37
t45 = t42 + t41
z0 = t44 x y15
z1 = t37 x y6
z2 = t33 x U7
z3 = t43 x y16
z4 = t40 x y1
z5 = t29 x y7
z6 = t42 x y11
z7 = t45 x y17
z8 = t41 x y10
z9 = t44 x y12
z10 = t37 x y3
z11 = t33 x y4
z12 = t43 x y13
z13 = t40 x y5
z14 = t29 x y2
z15 = t42 x y9
z16 = t45 x y14
z17 = t41 x y8
tc1 = z15 + z16
tc2 = z10 + tc1
tc3 = z9 + tc2
tc4 = z0 + z2
tc5 = z1 + z0
tc6 = z3 + z4
tc7 = z12 + tc4
tc8 = z7 + tc6
tc9 = z8 + tc7
tc10 = tc8 + tc9
tc11 = tc6 + tc5
tc12 = z3 + z5
tc13 = z13 + tc1
tc14 = tc4 + tc12
S3 = tc3 + tc11
tc16 = z6 + tc8
tc17 = z14 + tc10
tc18 = tc13 + tc14
S7 = z12 # tc18
tc20 = z15 + tc16
tc21 = tc2 + z11
S0 = tc3 + tc16
S6 = tc10 # tc18
S4 = tc14 + S3
S1 = S3 # tc16
tc26 = tc17 + tc20
S2 = tc26 # z17
S5 = tc21 + tc17
"""


def cmt_113() -> dict:
    """Converts the CMT listing: U_k is x_(7-k), S_k is y_(7-k)."""
    ren = lambda w: f"x{7 - int(w[1])}" if re.fullmatch(r"U[0-7]", w) else w  # noqa: E731
    gates = []
    for line in CMT_113.strip().splitlines():
        out, _, a, op, b = line.split()
        gates.append({"op": {"+": "XOR", "x": "AND", "#": "XNOR"}[op], "a": ren(a), "b": ren(b), "out": out})
    return {"gates": gates, "outputs": [f"S{7 - i}" for i in range(8)]}


def gf_mul(a: int, b: int) -> int:
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11B
        b >>= 1
    return r


def reference_sbox() -> list:
    """FIPS-197 Section 5.1.1: multiplicative inverse in GF(2^8) mod x^8+x^4+x^3+x+1, then the affine map."""
    out = []
    for x in range(256):
        inv = 0 if x == 0 else next(y for y in range(1, 256) if gf_mul(x, y) == 1)
        s = 0
        for i in range(8):
            bit = (inv >> i) ^ (inv >> ((i + 4) % 8)) ^ (inv >> ((i + 5) % 8)) ^ (inv >> ((i + 6) % 8)) \
                ^ (inv >> ((i + 7) % 8)) ^ (0x63 >> i)
            s |= (bit & 1) << i
        out.append(s)
    return out


def load_baseline() -> dict:
    return json.loads((ROOT / "baseline" / "certificate.json").read_text(encoding="utf-8"))


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

    # ---------- the reference table

    def test_embedded_table_is_the_fips197_sbox(self):
        table = V.sbox_table()
        self.assertEqual(table, reference_sbox())
        self.assertEqual((table[0x00], table[0x01], table[0x53], table[0xFF]), (0x63, 0x7C, 0xED, 0x16))
        self.assertEqual(sorted(table), list(range(256)))

    def test_input_bit_order(self):
        ins = V.input_truth_tables()
        for k in (0, 1, 0x80, 0x53, 0xFF):
            self.assertEqual([(ins[i] >> k) & 1 for i in range(8)], [(k >> i) & 1 for i in range(8)])

    # ---------- valid input

    def test_baseline_reproduces_baseline_score(self):
        with open(ROOT / "problem.toml", "rb") as f:
            baseline = tomllib.load(f)["baseline_score"]
        res = V.verify_dir(ROOT / "baseline", self.cfg)
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], baseline)

    def test_cmt_113_gate_circuit(self):
        res = self.run_obj(cmt_113())
        self.assertTrue(res["valid"], res)
        self.assertEqual(res["score"], "113")

    def test_gate_semantics(self):
        gates, _ = V.parse_circuit({"gates": [{"op": "AND", "a": "x0", "b": "x1", "out": "p"},
                                              {"op": "XOR", "a": "x0", "b": "x1", "out": "q"},
                                              {"op": "XNOR", "a": "p", "b": "q", "out": "r"}],
                                    "outputs": ["x0"] * 8}, 10)
        vals = V.simulate(gates)
        for k in range(256):
            a, b = k & 1, (k >> 1) & 1
            self.assertEqual((vals[8] >> k) & 1, a & b)
            self.assertEqual((vals[9] >> k) & 1, a ^ b)
            self.assertEqual((vals[10] >> k) & 1, 1 ^ (a & b) ^ (a ^ b))

    def test_dead_gate_counts(self):
        c = load_baseline()
        c["gates"].append({"op": "AND", "a": "x0", "b": "x1", "out": "unused"})
        self.assertEqual(self.run_obj(c)["score"], "107")

    def test_canonical_hash_ignores_names_operand_order_and_independent_reordering(self):
        c = load_baseline()
        h = self.run_obj(c)["canonical_hash"]
        # rename every internal wire, swap the operands of every gate
        ren = {g["out"]: f"w_{i * 7 % 1000}_{g['out']}" for i, g in enumerate(c["gates"])}
        r = lambda w: ren.get(w, w)  # noqa: E731
        d = {"gates": [{"out": r(g["out"]), "op": g["op"], "a": r(g["b"]), "b": r(g["a"])} for g in c["gates"]],
             "outputs": [r(w) for w in c["outputs"]]}
        self.assertEqual(self.run_bytes(json.dumps(d, indent=3).encode())["canonical_hash"], h)
        # a different topological order of the same gates
        rng = random.Random(8)
        for _ in range(3):
            todo = list(c["gates"])
            defined, order = set(V.INPUTS), []
            while todo:
                ready = [g for g in todo if g["a"] in defined and g["b"] in defined]
                g = rng.choice(ready)
                todo.remove(g)
                order.append(g)
                defined.add(g["out"])
            e = {"gates": order, "outputs": c["outputs"]}
            res = self.run_obj(e)
            self.assertTrue(res["valid"], res)
            self.assertEqual(res["canonical_hash"], h)
        self.assertNotEqual(self.run_obj(cmt_113())["canonical_hash"], h)

    # ---------- invalid certificates

    def test_wrong_function(self):
        c = load_baseline()
        for i in (0, 20, 60, len(c["gates"]) - 1):
            for op in ("AND", "XOR", "XNOR"):
                if op != c["gates"][i]["op"]:
                    d = copy.deepcopy(c)
                    d["gates"][i]["op"] = op
                    self.assertInvalid(self.run_obj(d), "differs from bit")
        d = copy.deepcopy(c)
        d["outputs"][0], d["outputs"][1] = d["outputs"][1], d["outputs"][0]
        self.assertInvalid(self.run_obj(d), "y0 differs")
        # most-significant-bit-first wiring is rejected: x7 is the top bit
        swap = {f"x{i}": f"x{7 - i}" for i in range(8)}
        d = copy.deepcopy(c)
        for g in d["gates"]:
            g["a"], g["b"] = swap.get(g["a"], g["a"]), swap.get(g["b"], g["b"])
        self.assertInvalid(self.run_obj(d), "differs from bit")
        d = copy.deepcopy(c)
        d["outputs"].reverse()
        self.assertInvalid(self.run_obj(d), "differs from bit")

    def test_ops(self):
        for op in ("OR", "NOT", "NAND", "and", "Xor", "", 1, None, ["AND"]):
            c = load_baseline()
            c["gates"][3]["op"] = op
            self.assertInvalid(self.run_obj(c), "op must be")

    def test_wiring_rules(self):
        c = load_baseline()
        d = copy.deepcopy(c)
        d["gates"][5]["a"] = "nowhere"
        self.assertInvalid(self.run_obj(d), "not an input")
        d = copy.deepcopy(c)
        d["gates"][5]["b"] = d["gates"][40]["out"]  # forward reference
        self.assertInvalid(self.run_obj(d), "not an input")
        d = copy.deepcopy(c)
        d["gates"][5]["out"] = d["gates"][2]["out"]
        self.assertInvalid(self.run_obj(d), "assigned once")
        d = copy.deepcopy(c)
        d["gates"][5]["out"] = "x3"
        self.assertInvalid(self.run_obj(d), "assigned once")
        d = copy.deepcopy(c)
        d["gates"][5]["b"] = d["gates"][5]["a"]
        self.assertInvalid(self.run_obj(d), "different wires")
        d = copy.deepcopy(c)
        d["gates"].insert(0, {"op": "XOR", "a": "x0", "b": "x0", "out": "zero"})
        self.assertInvalid(self.run_obj(d), "different wires")

    def test_wire_names(self):
        for bad in ("", "1abc", "a-b", "a b", "é", "a" * 33, 5, None, True, ["x0"]):
            c = load_baseline()
            c["gates"][7]["a"] = bad
            self.assertInvalid(self.run_obj(c), "wire names")
            c = load_baseline()
            c["gates"][7]["out"] = bad
            self.assertInvalid(self.run_obj(c), "wire names")
        c = load_baseline()
        c["gates"][0]["out"] = "_" + "a" * 31
        c["gates"] = [dict(g, a="_" + "a" * 31 if g["a"] == "t0" else g["a"],
                           b="_" + "a" * 31 if g["b"] == "t0" else g["b"]) for g in c["gates"]]
        self.assertEqual(self.run_obj(c)["score"], "106")

    def test_outputs(self):
        c = load_baseline()
        for bad in (c["outputs"][:7], c["outputs"] + ["t0"], [], "t90", None, [1] * 8, c["outputs"][:7] + ["nope"]):
            d = copy.deepcopy(c)
            d["outputs"] = bad
            self.assertInvalid(self.run_obj(d))
        d = copy.deepcopy(c)
        d["outputs"][3] = "x3"
        self.assertInvalid(self.run_obj(d), "y3 differs")

    def test_wrong_shape(self):
        c = load_baseline()
        self.assertInvalid(self.run_obj([c]), "exactly the keys")
        self.assertInvalid(self.run_obj({"gates": c["gates"]}), "exactly the keys")
        self.assertInvalid(self.run_obj(dict(c, note="x")), "exactly the keys")
        self.assertInvalid(self.run_obj({"gates": [], "outputs": c["outputs"]}), "non-empty")
        self.assertInvalid(self.run_obj({"gates": {}, "outputs": c["outputs"]}), "non-empty")
        for g in ([], ["AND", "x0", "x1", "t"], {"op": "AND", "a": "x0", "b": "x1"},
                  {"op": "AND", "a": "x0", "b": "x1", "out": "t", "depth": 1}):
            self.assertInvalid(self.run_obj({"gates": [g], "outputs": c["outputs"]}), "each gate")

    def test_too_many_gates(self):
        c = load_baseline()
        extra = [{"op": "XOR", "a": "x0", "b": "x1", "out": f"pad{i}"} for i in range(self.cfg["max_gates"])]
        c["gates"] += extra
        self.assertInvalid(self.run_obj(c), "at most")

    def test_non_integers_and_constants(self):
        for bad in ("1.5", "1e3", "NaN", "Infinity", "-Infinity"):
            text = '{"gates": [{"op": "AND", "a": "x0", "b": "x1", "out": "t"}], "outputs": [%s]}' % bad
            self.assertInvalid(self.run_bytes(text.encode()))
        self.assertInvalid(self.run_bytes(('{"gates": [%s]}' % ("9" * 40)).encode()), "digits")

    def test_duplicate_keys(self):
        self.assertInvalid(self.run_bytes(b'{"gates": [], "gates": [], "outputs": []}'), "duplicate keys")
        text = b'{"gates": [{"op": "AND", "op": "XOR", "a": "x0", "b": "x1", "out": "t"}], "outputs": []}'
        self.assertInvalid(self.run_bytes(text), "duplicate keys")

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
        c = load_baseline()
        c["gates"][0]["op"] = "<script>alert(1)</script>"
        self.assertNotIn("script", self.run_obj(c)["message"])
        c = load_baseline()
        c["gates"][9]["a"] = "script_tag"
        self.assertNotIn("script", self.run_obj(c)["message"])
        res = self.run_bytes(b'{"gates": [], "<script>alert(1)</script>": 1}')
        self.assertNotIn("script", res["message"])

    # ---------- command-line contract

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(HERE / "verify.py"), *args],
                              capture_output=True, timeout=60)

    def test_cli_prints_exactly_one_json_line(self):
        (self.dir / "certificate.json").write_text(json.dumps(cmt_113()))
        proc = self.run_cli(str(self.dir))
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(set(obj), {"valid", "score", "canonical_hash", "message"})
        self.assertEqual(obj["score"], "113")
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
        self.assertLessEqual(imported, {"__future__", "hashlib", "heapq", "json", "os", "stat", "sys",
                                        "tomllib", "fractions", "pathlib"})
        self.assertFalse(called & {"eval", "exec", "compile", "__import__", "literal_eval",
                                   "sympify", "system", "popen"})


if __name__ == "__main__":
    unittest.main()
