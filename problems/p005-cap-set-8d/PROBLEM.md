# p005 · Cap set in dimension 8

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p005` |
| metric | 点数 / points |
| direction | `max` (higher is better) |
| baseline | `512` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p005-cap-set-8d/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How many points of F_3^8 can you choose so that no three of them lie on a line?

## Problem

F_3^8 is the set of vectors of length 8 with coordinates in {0, 1, 2}, added coordinatewise modulo 3. Three distinct points a, b, c lie on a common line exactly when a + b + c = 0 (mod 3) in every coordinate; equivalently, in each coordinate the three values are either all equal or all different. A cap set is a set of points with no three distinct points on a line.

Find a cap set in F_3^8 with as many points as you can. Write cap(8) for the largest possible size. The best known lower bound is cap(8) ≥ 512.

## Why it matters

The card game SET has 81 cards, one for each point of F_3^4, and a "set" of three cards is exactly a line. The largest collection of SET cards containing no set has 20 cards (Pellegrino, 1970). The largest cap sizes are known exactly only in dimensions 1 to 6: 2, 4, 9, 20, 45 (Edel, Ferret, Landjev and Storme, 2002) and 112 (Potechin, 2008). From dimension 7 on, only bounds are known. A cap set is the same as a subset of F_3^n with no three-term arithmetic progression, the finite-field model of Roth's theorem; asymptotically cap(n) = O(2.756^n) (Ellenberg and Gijswijt, 2017).

In dimension 8 the lower bound went from 496 to 512 (Romera-Paredes et al., 2023). A cap with 513 or more points would be a new lower bound for cap(8).

## Certificate

- File name `certificate.json`, shaped like `{"points": [p1, p2, …]}`, with no other keys.
- Each point is a list of 8 JSON integers, each 0, 1 or 2. Points are distinct and may come in any order.
- At most 1008 points. No cap in F_3^8 is larger: each of the three parallel hyperplanes x_1 = 0, 1, 2 meets a cap in a cap of a 7-dimensional space, so cap(8) ≤ 3·cap(7) ≤ 9·cap(6) = 1008.
- For every pair of distinct points a, b in the set, the point c = −(a + b) mod 3 is not in the set. This c is the third point on the line through a and b and differs from both, so the condition says that no line meets the set in three points. The check is exact integer arithmetic.
- The score is the number of points.
- The file is UTF-8 JSON, at most 128 KiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: the points sorted lexicographically. `canonical_hash` is the sha256 of the canonical JSON, so reordering points does not change it. Translates and other affine images of a cap are different certificates.

## Baseline

512 points, the cap set of Romera-Paredes et al. (2023), the current best known lower bound for cap(8). The authors published the point set as `cap_set/n8_size512.txt`, one point per line; the certificate lists the same points in the same order.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p005-cap-set-8d/verify/verify.py problems/p005-cap-set-8d/baseline
```

Sources: [B. Romera-Paredes et al., Nature 625 (2024)](https://doi.org/10.1038/s41586-023-06924-6); [the 512-point set](https://github.com/google-deepmind/funsearch/blob/main/cap_set/n8_size512.txt); [A. Potechin, Des. Codes Cryptogr. 46 (2008)](https://doi.org/10.1007/s10623-007-9132-z); [J. Ellenberg, D. Gijswijt, arXiv:1605.09223](https://arxiv.org/abs/1605.09223); [F. Tyrrell, arXiv:2209.10045](https://arxiv.org/abs/2209.10045).
