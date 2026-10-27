# p006 · Low autocorrelation binary sequence of length 100

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p006` |
| metric | 能量 / energy |
| direction | `min` (lower is better) |
| baseline | `578` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p006-labs-100/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

Which sequence of 100 signs ±1 has the smallest sum of squared aperiodic autocorrelations?

## Problem

Let s_1, …, s_N be a sequence with every s_i ∈ {−1, +1}, and N = 100 (`[params] length` in `problem.toml`). Its aperiodic autocorrelations are

C_k = Σ_{i=1}^{N−k} s_i s_{i+k},  k = 1, …, N − 1,

and its energy is E = Σ_{k=1}^{N−1} C_k². The merit factor is F = N² / (2E).

Find a sequence of length 100 with energy as small as possible. The score is E.

Reversing the sequence, negating every sign, and flipping every second sign (s_i → (−1)^i s_i) do not change E. Together they generate a group of 8 operations, so every sequence has up to 7 trivial copies with the same energy.

For N = 100 every sequence has E ≡ 2 (mod 4), because C_k ≡ N − k (mod 2) gives C_k² ≡ (N − k)² (mod 4). The next possible value below the baseline is therefore 574.

## Why it matters

A binary sequence with small autocorrelations C_k is a binary phase code for pulse compression in radar and sonar: the C_k are the sidelobes of the compressed pulse, and E measures their total power. Golay (1977, 1982) studied the problem through the merit factor and conjectured that the best merit factor tends to about 12.32 as N grows. In statistical physics the same energy is the Bernasconi model (Bernasconi, 1987).

Optimal energies are proven only up to N = 66, by exhaustive branch-and-bound search (Packebusch and Mertens, 2016). Beyond that only best known values from heuristic searches exist, and they are tracked in public tables: the merit factor records of Knauer, the solver archive of Bošković, Brglez and Brest, and the best-known-value table of the LABS problem class in the QOBLIB benchmark library (Koch et al., 2025). LABS is a standard hard instance family for classical solvers and for quantum optimisation methods such as QAOA (Shaydulin et al., 2024).

For N = 100 the best known energy is 578, merit factor 8.6505, about 70% of the conjectured asymptotic value. A sequence with E ≤ 574 would be a new best known value for N = 100 in these tables.

## Certificate

- File name `certificate.json`, shaped like `{"sequence": "++-+…"}`, with no other keys.
- `sequence` is a JSON string of exactly 100 characters, each `+` (meaning +1) or `-` (meaning −1, ASCII hyphen-minus). Position i in the string is s_i.
- The verifier computes every C_k and E in exact integer arithmetic.
- The score is E, always an integer, for example `"578"`.
- The file is UTF-8 JSON, at most 64 KiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: the lexicographically smallest string (with `+` before `-`) among the 8 images of the sequence under reversal, negation and alternation. `canonical_hash` is the sha256 of the canonical JSON, so the trivial copies of one sequence hash the same.

## Baseline

E = 578 (F = 8.6505). The sequence is the length-100 entry in Knauer's table of merit factor records (version of October 2004), where it is marked as Knauer's own result and as not proven optimal. QOBLIB lists 578 as the best known value for N = 100 (instance `labs100`) and ships the same sequence as `labs100.bst.sol`; its run lengths are 6 2 5 5 2 1 2 2 1 2 10 3 1 1 2 2 4 1 1 2 2 4 1 2 1 1 1 1 1 1 1 1 2 3 2 3 2 1 1 1 2 1 1 1 2 2 1 1 1 1.

`baseline/certificate.json` is that solution file converted to the certificate format (1 → `+`, 0 → `-`); the verifier recomputes E = 578. To reproduce:

```bash
python3 problems/p006-labs-100/verify/verify.py problems/p006-labs-100/baseline
```

Sources: [QOBLIB, LABS best known values](https://github.com/ZIB-AOPT/QOBLIB/blob/main/02-labs/solutions/README.md); [QOBLIB, labs100.bst.sol](https://github.com/ZIB-AOPT/QOBLIB/blob/main/02-labs/solutions/labs100.bst.sol); [Knauer, merit factor records (archived copy)](https://github.com/borkob/git_labs/blob/master/results-2016/2004-Knauer-original.html); [T. Packebusch, S. Mertens, arXiv:1512.02475](https://arxiv.org/abs/1512.02475); [B. Bošković, F. Brglez, J. Brest, arXiv:1406.5301](https://arxiv.org/abs/1406.5301); [T. Koch et al., arXiv:2504.03832](https://arxiv.org/abs/2504.03832); [R. Shaydulin et al., arXiv:2308.02342](https://arxiv.org/abs/2308.02342).
