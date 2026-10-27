# p000 · Golomb ruler (sandbox)

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p000` |
| metric | 长度 / length |
| direction | `min` (lower is better) |
| baseline | `2047` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p000-sandbox/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

p000 is the sandbox problem for walking through a submission end to end. Its scores are not on the board and earn no rewards.

## Problem

A Golomb ruler is a set of distinct integer marks such that all pairwise differences between marks are distinct. Its length is the largest mark minus the smallest.

For n = 12 marks (`[params] n` in `problem.toml`), find a Golomb ruler that is as short as possible.

## Why it matters

Golomb rulers are used to place antennas in radio-telescope arrays and to design error-correcting codes. For n = 12 the shortest length, 85, is proven optimal, so answers here can be checked against a known value, which makes it a good practice problem.

## Certificate

- File name `certificate.json`, shaped like `{"marks": [0, 1, 3, …]}`. It may also carry `"n": 12`; no other keys are allowed.
- `marks` has exactly 12 entries. Each is a JSON integer (not a float, string or boolean) with absolute value at most 10^15. Marks are distinct and may come in any order.
- All pairwise differences are distinct.
- The file is UTF-8 JSON, at most 64 KiB, nested at most 8 levels, with no duplicate keys.
- The score is the length, always an integer, for example `"85"`.
- Canonical form: shift the marks to start at 0 and take the lexicographically smaller of the ruler and its mirror image. `canonical_hash` is the sha256 of the canonical JSON, so shifted or mirrored copies of one ruler hash the same.

## Baseline

Marks 2^k − 1 for k = 0, 1, …, 11: 0, 1, 3, 7, 15, …, 2047. Every difference has the form 2^j − 2^i, and these have distinct binary expansions, so this is a valid Golomb ruler of length 2047.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p000-sandbox/verify/verify.py problems/p000-sandbox/baseline
```
