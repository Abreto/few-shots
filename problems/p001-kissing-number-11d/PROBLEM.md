# p001 · Kissing number in dimension 11

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p001` |
| metric | 球数 / spheres |
| direction | `max` (higher is better) |
| baseline | `604` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p001-kissing-number-11d/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How many unit spheres in 11-dimensional space can touch one central unit sphere without overlapping each other?

## Problem

The kissing number τ(n) is the largest number of non-overlapping unit spheres in R^n that all touch a common unit sphere. Equivalently, it is the largest number of nonzero vectors of equal length in R^n such that any two of them make an angle of at least 60°.

Find as many such vectors in R^11 as you can. Known bounds: 604 ≤ τ(11) ≤ 868.

## Why it matters

The kissing problem goes back to a 1694 exchange between Isaac Newton and David Gregory about dimension 3, settled only in 1953. Exact values are known in dimensions 1, 2, 3, 4, 8 and 24. In every other dimension only bounds are known, and they are tracked in Henry Cohn's public table. A kissing configuration is a spherical code with minimum angle 60°, the same object that coding theory uses to place equal-energy signals as far apart as possible; the E8 and Leech lattices were found in this line of work.

Dimension 11 has moved recently: 592 (Ganzhinov, 2022), 593 (Georgiev, Gómez-Serrano, Tao and Wagner, 2025), then 594 and 604 (Bianchi, Kwon, Pappu and Zou, 2026). Every additional vector is a new lower bound in Cohn's table.

## Certificate

- File name `certificate.json`, shaped like `{"vectors": [v1, v2, …]}`, with no other keys.
- Each vector is a list of 11 coordinates. Each coordinate is a pair of JSON integers `[p, q]` meaning p + q√2, so coordinates live in Z[√2]. Use `[p, 0]` for integer coordinates.
- |p| and |q| are at most 10^9. At most 2000 vectors.
- All vectors are nonzero, distinct and have the same squared length.
- For every pair x ≠ y: ⟨x, y⟩ ≤ |x|² / 2 (angle at least 60°, so the spheres touch at most at one point).
- All arithmetic is exact in Z[√2]: the verifier never uses floating point.
- The score is the number of vectors.
- The file is UTF-8 JSON, at most 1 MiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: the vectors sorted lexicographically. `canonical_hash` is the sha256 of the canonical JSON, so reordering vectors does not change it. Rotated copies of a configuration are different certificates.

## Baseline

604 vectors with coordinates in Z[√2], scaled so that every squared length is 36 and every pairwise inner product is at most 18. This is the configuration of Bianchi, Kwon, Pappu and Zou (2026), listed as the current lower bound in Cohn's table.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p001-kissing-number-11d/verify/verify.py problems/p001-kissing-number-11d/baseline
```

Sources: [Henry Cohn, table of kissing number bounds](https://cohn.mit.edu/kissing-numbers); [the 604-vector configuration](https://github.com/togethercomputer/EinsteinArena-new-SOTA/tree/main/kissing-number); [M. Ganzhinov, arXiv:2207.08266](https://arxiv.org/abs/2207.08266); [Georgiev, Gómez-Serrano, Tao, Wagner, arXiv:2511.02864](https://arxiv.org/abs/2511.02864).
