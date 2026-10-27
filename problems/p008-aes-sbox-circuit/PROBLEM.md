# p008 · Smallest circuit for the AES S-box

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p008` |
| metric | 门数 / gates |
| direction | `min` (lower is better) |
| baseline | `106` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p008-aes-sbox-circuit/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How few two-input AND, XOR and XNOR gates are enough to compute the AES S-box?

## Problem

The AES S-box is the fixed permutation S of the 256 bytes defined in FIPS-197, Section 5.1.1: the multiplicative inverse in GF(2^8) modulo x^8 + x^4 + x^3 + x + 1 (with 0 mapped to 0), followed by an affine map over GF(2). For example S(0x00) = 0x63, S(0x01) = 0x7c, S(0x53) = 0xed.

Find a circuit that computes S on all 256 inputs with as few gates as possible. The gate basis is two-input AND, XOR and XNOR (XNOR(a, b) = 1 ⊕ a ⊕ b), each costing one gate, with unlimited fan-out. Depth is not scored. There is no NOT gate and no constant input; negations have to be absorbed into XNOR gates. This is the model of Boyar and Peralta, of the Circuit Minimization Team page and of the NIST circuit-complexity list.

Gate counts in richer bases are not comparable with this one. Maximov and Ekdahl (2019) report 102 gates with NAND, NOR and MUX gates, and Reyhani-Masoleh, Taha and Ashmawy (2018) use a richer gate library. Such circuits are accepted here only after they are rewritten over AND, XOR and XNOR, and then each gate counts.

## Why it matters

The S-box is the only non-linear step of AES, the most widely deployed block cipher, and its circuit dominates the cost of AES in hardware and in bitsliced software. A smaller circuit gives a smaller, lower-power AES core and faster constant-time software. For masked (side-channel protected) implementations the number of AND gates dominates the cost. The fewest AND gates for the S-box, its multiplicative complexity, is a related open problem: 32 AND gates suffice in the circuits of Boyar and Peralta, and circuits with 28 AND gates were added to the NIST list in 2026 (Nasr).

The smallest known size in this basis went from 115 gates (Boyar and Peralta, 2010) to 113 (Calik, posted on the Circuit Minimization Team page), then 110 (NIST list, 2026) and 106 (Jain, 2026). A circuit with 105 gates or fewer would be the smallest known circuit for the AES S-box in this model.

## Certificate

- File name `certificate.json`, shaped like `{"gates": [g1, g2, …], "outputs": [w0, …, w7]}`, with no other keys.
- The input wires are `x0` … `x7`, where `xi` is bit i of the input byte: `x7` is the most significant bit and `x0` the least significant (bits b7 … b0 in FIPS-197).
- Each gate is an object `{"op": "AND" | "XOR" | "XNOR", "a": <wire>, "b": <wire>, "out": <new wire>}` with no other keys. `a` and `b` must be input wires or outputs of earlier gates in the list, and they must be two different wires. `out` must be a new name: every wire is assigned exactly once, and no gate output may be named like an input.
- Wire names match `[A-Za-z_][A-Za-z0-9_]{0,31}` (ASCII).
- `outputs` lists exactly 8 wires; entry i is the wire for output bit `yi`, bit i of S(x), so the last entry is the most significant bit. An output may be any input or gate wire, and two outputs may share a wire.
- The verifier evaluates the circuit on all 256 inputs at once (each wire is a 256-bit integer) and requires every output bit to equal the embedded FIPS-197 table, which the tests recompute from GF(2^8) inversion and the affine map.
- At most 2000 gates. The score is the number of gates, including gates whose outputs are not used.
- The file is UTF-8 JSON, at most 256 KiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: wires are renumbered (inputs 0 … 7, then gates 8, 9, …) in a fixed topological order: repeatedly take, among the gates whose operands are already numbered, the one with the smallest (op, smaller operand number, larger operand number), with AND < XOR < XNOR. Each gate is written as `[op, smaller operand, larger operand]`, followed by the 8 output numbers. `canonical_hash` is the sha256 of the canonical JSON, so renaming wires, swapping the two operands of a gate or listing independent gates in another order does not change it.

## Baseline

A circuit with 106 gates (34 AND, 69 XOR, 3 XNOR) and depth 24, from Jain (2026), "Smaller Gate Counts for the AES S-box and Inverse S-box in the AND/XOR/XNOR Model", preprint. It is the smallest published circuit in this basis; the paper also gives a second 106-gate circuit (32 AND, depth 34). Smaller published counts, such as the 102 gates of Maximov and Ekdahl, use a richer basis and do not apply here.

The certificate is the file `sbox/circuits/sbox106_d24.json` of the paper's repository, converted to this format: signals U0 … U7 there (U0 most significant) are `x7` … `x0` here, outputs S0 … S7 there (S0 most significant) are `y7` … `y0`, and gate i is wire `ti`. The tests also check the 113-gate circuit of the Circuit Minimization Team page.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p008-aes-sbox-circuit/verify/verify.py problems/p008-aes-sbox-circuit/baseline
```

Sources: [FIPS-197](https://doi.org/10.6028/NIST.FIPS.197-upd1); [Circuit Minimization Team page, 113-gate circuit](https://www.cs.yale.edu/homes/peralta/CircuitStuff/CMT.html); [Boyar and Peralta, SEA 2010](https://doi.org/10.1007/978-3-642-13193-6_16); [Boyar, Matthews and Peralta, J. Cryptology 2013](https://doi.org/10.1007/s00145-012-9124-7); [NIST circuit complexity, AES S-box circuits](https://github.com/usnistgov/Circuits/tree/master/data/slp/aes/aes-sbox); [Jain 2026, paper and circuits](https://github.com/ahrazzle/gf2m-circuits); [Maximov and Ekdahl, TCHES 2019](https://doi.org/10.13154/tches.v2019.i4.91-125); [Reyhani-Masoleh, Taha and Ashmawy, TCHES 2018](https://doi.org/10.13154/tches.v2018.i2.298-336).
