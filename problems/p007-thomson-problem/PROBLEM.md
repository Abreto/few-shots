# p007 · Thomson problem for 960 points

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p007` |
| metric | 库仑能量 / Coulomb energy |
| direction | `min` (lower is better) |
| baseline | `444368.4373479895` |
| epsilon | `0.000001` (`absolute`) |
| verifier | `python3 problems/p007-thomson-problem/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How low can the Coulomb energy of 960 unit charges on the unit sphere be?

## Problem

Place N = 960 distinct points x_1, …, x_N on the unit sphere in R^3 (`[params] n` in `problem.toml`) so that the Coulomb energy

E = Σ_{i<j} 1 / |x_i − x_j|

is as small as possible. The score is a rigorous upper bound on E, given to 10 decimal places (see Certificate). The baseline above is 444368.4373479895.

## Why it matters

J. J. Thomson posed the problem in 1904 while modelling the arrangement of electrons in an atom. Exact minimisers are proven only for a few small N. For larger N the problem is a standard test for global optimisation, because the number of local minima grows exponentially with N and the lowest ones differ in energy by small amounts. Smale's 7th problem asks for an efficient algorithm that finds near-optimal points for the logarithmic-energy version of the same question. Low-energy configurations for N in the hundreds model the arrangement of proteins in spherical viral capsids (Caspar and Klug, 1962) and of particles in colloidal crystals on droplets (Bausch et al., 2003): both are hexagonal lattices on a sphere with 12 curvature-induced defects.

Best known energies for N up to several thousand are kept in the Cambridge Cluster Database. For N = 960 the best known energy was 444368.8463700 in the table of Bowick, Cecka, Giomi, Middleton and Zielnicki, then 444368.8193481 (Roshal, Myasnikova and Rochal, 2014), then 444368.4373480 (Amore and Wales, 2026), a configuration with point group T. A configuration with energy lower by at least ε would be a new best known configuration for N = 960 and a new entry in that table.

## Certificate

- File name `certificate.json`, shaped like `{"points": [p1, p2, …]}`, with no other keys.
- `points` has exactly 960 entries. Each point is a list of four JSON integers `[a, b, c, d]` meaning (a/d, b/d, c/d), with d > 0, d ≤ 10^18 and a² + b² + c² = d², so every point lies exactly on the unit sphere. Rational points are dense on the sphere; one way to get them is inverse stereographic projection: for integers p, r, q with q > 0, the point `[2pq, 2rq, p² + r² − q², p² + r² + q²]` is on the sphere.
- The points are pairwise distinct.
- Scoring, all in integer arithmetic: for points x = (a, b, c)/d and y = (a′, b′, c′)/d′, 1/|x − y| = √(dd′ / (2D)) with the integer D = dd′ − (aa′ + bb′ + cc′) > 0. Each term is rounded up to a multiple of 2^−80 with integer square roots, the terms are summed exactly, and the sum is rounded up to 10 decimal places. The score is that decimal string, for example `"444368.4373479895"`. It is never below the true energy and exceeds it by less than 1.1 × 10^−10.
- ε = 10^−6 (absolute). The verifier's rounding is below 1.1 × 10^−10, and replacing a converged floating-point configuration by nearby rational points with d ≤ 10^18 changes its energy by about 10^−11 (2.7 × 10^−12 for the baseline). Published record energies carry 7 decimals. A drop of at least 10^−6 is therefore a different, lower configuration, not an artefact of rounding or of the rational approximation. Recent record steps in this range are larger, for example 6.6 × 10^−5 at N = 900 and 2.7 × 10^−4 at N = 750 (Amore and Wales, 2026).
- The file is UTF-8 JSON, at most 256 KiB, nested at most 8 levels, with no duplicate keys. Integers have at most 19 digits.
- Canonical form: each point divided by the gcd of its four integers, and the points sorted lexicographically. `canonical_hash` is the sha256 of the canonical JSON, so reordering points or scaling a point's integers does not change it. Rotated or reflected copies of a configuration are different certificates; they have the same energy, so they are never an improvement.

## Baseline

The configuration of Amore and Wales (2026), taken from the Cambridge Cluster Database (Riesz energy database, s = 1, file `points_960_1.dat`, 960 rows of x y z in floating point). The published energy is 444368.4373480. This is the certificate case: `baseline/certificate.json` is that configuration and `baseline_score` is its verifier score.

Conversion: each point was normalised and, using the coordinate axis of largest absolute value, mapped to its stereographic coordinates (u, v) from the opposite pole, with |u|, |v| < 0.6. These were rounded to multiples of 1/q with q = 2^29 and mapped back with the formula above (up to the choice of axis and sign), then reduced by the gcd. All denominators are below 3.6 × 10^17, and no point moves by more than 2.5 × 10^−9.

Energies: the energy of the published floating-point coordinates, normalised to the sphere, is 444368.43734798942 (computed in high precision), the rational points have energy 2.7 × 10^−12 higher, and the verifier's upper bound rounded to 10 decimals is 444368.4373479895. That is 5 × 10^−11 below the published 444368.4373480, which is rounded to 7 decimals.

To reproduce:

```bash
python3 problems/p007-thomson-problem/verify/verify.py problems/p007-thomson-problem/baseline
```

Sources: [Cambridge Cluster Database, Riesz energy database, s = 1](https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/site/s_1/index.html); [coordinates, points_960_1.dat](https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/site/s_1/dat/points_960_1.dat); [P. Amore, D. J. Wales, arXiv:2610.08122](https://arxiv.org/abs/2610.08122); [D. S. Roshal, A. E. Myasnikova, S. B. Rochal, arXiv:1408.3473](https://arxiv.org/abs/1408.3473); [Cambridge Cluster Database, Thomson problem](https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/table.html); [S. Smale, Mathematical problems for the next century (1998)](https://doi.org/10.1007/BF03025291).
