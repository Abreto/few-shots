# p003 · Lower bound for the Ramsey number R(4,6)

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p003` |
| metric | 顶点数 / vertices |
| direction | `max` (higher is better) |
| baseline | `35` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p003-ramsey-r46/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How many vertices can a graph have if it contains no 4 pairwise adjacent vertices and no 6 pairwise non-adjacent vertices?

## Problem

The Ramsey number R(4,6) is the smallest N such that every graph on N vertices contains a clique of size 4 or an independent set of size 6. A graph on n vertices with neither, a (4,6)-graph, proves R(4,6) ≥ n + 1.

Find a (4,6)-graph with as many vertices as you can. Known bounds: 36 ≤ R(4,6) ≤ 40, so the largest (4,6)-graph has between 35 and 39 vertices.

## Why it matters

R(4,6) and R(3,10) are the smallest classical two-colour Ramsey numbers whose values are unknown; the neighbouring cases R(4,5) = 25 (McKay and Radziszowski, 1995) and R(3,9) = 36 (Grinstead and Roberts, 1982) are settled. The bounds are tracked in Tables Ia and Ib of Radziszowski's dynamic survey "Small Ramsey Numbers".

The lower bound went from 35 (Exoo, 1993) to 36 (Exoo, 2012, with 37 graphs on 35 vertices). The upper bound went from 41 (McKay and Radziszowski, 1997) to 40 (Angeltveit and McKay, by computation, listed in Table Ib of the survey). A (4,6)-graph on 36 vertices would be a new lower bound R(4,6) ≥ 37 in Table Ia of the survey, and every further vertex raises it by one more.

## Certificate

- File name `certificate.json`, shaped like `{"adjacency": [row_0, row_1, …, row_{n-1}]}`, with no other keys.
- `row_i` is a string of exactly n characters, each `0` or `1`. Character j of `row_i` is `1` if and only if vertices i and j are adjacent.
- The matrix is symmetric with zeros on the diagonal. 1 ≤ n ≤ 64.
- No 4 vertices are pairwise adjacent, and no 6 vertices are pairwise non-adjacent. The verifier checks both by exhaustive search and names a witness when one exists.
- The score is n.
- The file is UTF-8 JSON, at most 64 KiB, nested at most 8 levels, with no duplicate keys.
- Graphs in graph6 format, such as the files in McKay's collection, convert directly: the bits of the graph6 string list the upper triangle column by column.
- Canonical form: the lexicographically smallest relabelled adjacency matrix over all leaves of an individualisation-refinement search (colour refinement, first non-singleton cell, every vertex of that cell tried). Isomorphic graphs hash the same. If that search would exceed a fixed work budget, which happens only for graphs with very large automorphism groups, the matrix is hashed in the given labelling and relabelled copies hash differently. `canonical_hash` is the sha256 of the canonical JSON.

## Baseline

A (4,6)-graph on 35 vertices with 248 edges: the first of the 37 graphs of Exoo (2012), as published in graph6 format in McKay's collection of Ramsey graphs (file `r46_35some.g6`), converted to adjacency rows. It is the construction behind the current lower bound R(4,6) ≥ 36. The record certificate itself is used, so `baseline_kind` is `certificate`.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p003-ramsey-r46/verify/verify.py problems/p003-ramsey-r46/baseline
```

Sources: [S. Radziszowski, Small Ramsey Numbers, Electronic Journal of Combinatorics DS1, revision #18 (2026)](https://www.combinatorics.org/ojs/index.php/eljc/article/view/DS1); [G. Exoo, On the Ramsey number R(4,6), Electronic Journal of Combinatorics 19(1) (2012) #P66](https://www.combinatorics.org/ojs/index.php/eljc/article/view/v19i1p66); [B. McKay, Ramsey graphs](https://users.cecs.anu.edu.au/~bdm/data/ramsey.html); [the 37 graphs on 35 vertices](https://users.cecs.anu.edu.au/~bdm/data/r46_35some.g6); [B. McKay and S. Radziszowski, Subgraph counting identities and Ramsey numbers, Journal of Combinatorial Theory B 69 (1997) 193–209](https://doi.org/10.1006/jctb.1996.1741).
