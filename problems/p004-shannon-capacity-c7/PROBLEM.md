# p004 · Shannon capacity of the 7-cycle

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p004` |
| metric | 点数 / points |
| direction | `max` (higher is better) |
| baseline | `134753` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p004-shannon-capacity-c7/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How large an independent set can you find in the 10th strong power of the 7-cycle?

## Problem

The strong power C7^⊠10 has vertex set {0, 1, …, 6}^10. Two distinct vertices x and y are adjacent if and only if, in every coordinate i, x_i − y_i is 0, 1 or −1 modulo 7. An independent set is a set of vertices no two of which are adjacent. In coding terms, it is a zero-error code of length 10 for a channel with 7 input symbols in which each symbol can be confused with its two cyclic neighbours.

Find an independent set in C7^⊠10 with as many points as you can. Known bounds: 134,753 ≤ α(C7^⊠10) ≤ ⌊ϑ(C7)^10⌋ = 161,557, where ϑ is the Lovász theta function.

## Why it matters

The Shannon capacity of a graph G is Θ(G) = sup_d α(G^⊠d)^(1/d). Shannon (1956) introduced it as the zero-error capacity of a channel. Lovász (1979) proved Θ(C5) = √5; Θ(C7) is still unknown. The best bounds are 3.25883262 ≤ Θ(C7) ≤ ϑ(C7) = 7cos(π/7)/(1 + cos(π/7)) ≈ 3.3177. The lower bound is due to Tandon (2026), from an independent set in C7^⊠500 built by recursive product constructions.

In dimension 10, the best set had 367² = 134,689 points, the square of the 367-point set in C7^⊠5 of Polak and Schrijver (2019). Itty, Rosin, Carstensen and Reichman (2026) found 134,753 points; the recursive constructions of Gao (2026), of Buys, Polak and Zuiddam (2026) and of Tandon (2026) start from this construction. Every additional point is a new lower bound on α(C7^⊠10). A set of at least 135,090 points would on its own raise the lower bound on Θ(C7) above 3.25883262, since 135,089^(1/10) < 3.25883262 < 135,090^(1/10).

## Certificate

- File name `certificate.json`, shaped like `{"points": ["0202002020", …]}`, with no other keys.
- Each point is a string of exactly 10 characters from `0123456`; character i is coordinate i.
- The points are distinct and pairwise non-adjacent in C7^⊠10. At most 200,000 points.
- The verifier is exact: it groups points by their first five coordinates and compares the last five coordinates of neighbouring groups with bit masks.
- The score is the number of points.
- The file is UTF-8 JSON, at most 4 MiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: each point read as a base-7 integer with the first character most significant, and the list of these integers sorted. `canonical_hash` is the sha256 of the canonical JSON, so reordering points does not change it. Images of a set under automorphisms of C7^⊠10 (permuting coordinates, rotating or reflecting a coordinate) are different certificates.

## Baseline

The 134,753-point set of Itty, Rosin, Carstensen and Reichman (2026), from their public repository (file `c7/CC_10_7_134753.txt`, one point per line as 10 space-separated digits), converted to 10-character strings. It is built from the 367-point set R of Polak and Schrijver: 8 points are removed from R to leave a set B, and B × B is extended by two families of 8 × 367 points derived from R. The record certificate itself is used, so `baseline_kind` is `certificate`.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p004-shannon-capacity-c7/verify/verify.py problems/p004-shannon-capacity-c7/baseline
```

Sources: [N. Itty, C. D. Rosin, C. Carstensen, D. Reichman, arXiv:2607.21517](https://arxiv.org/abs/2607.21517); [their repository with the 134,753-point set](https://github.com/nathanielitty/lower-bounds-for-shannon-capacity/tree/fe8966079013abaac21d1c08441500100f8e3b86/c7); [S. Polak, A. Schrijver, arXiv:1808.07438](https://arxiv.org/abs/1808.07438); [R. Tandon, arXiv:2608.30273](https://arxiv.org/abs/2608.30273); [Y. Gao, arXiv:2607.27869](https://arxiv.org/abs/2607.27869); [P. Buys, S. Polak, J. Zuiddam, arXiv:2607.29681](https://arxiv.org/abs/2607.29681); [L. Lovász, On the Shannon capacity of a graph, IEEE Transactions on Information Theory 25 (1979) 1–7](https://doi.org/10.1109/TIT.1979.1055985).
