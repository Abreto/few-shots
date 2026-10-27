# p010 · Mona Lisa 100,000-city TSP

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p010` |
| metric | 路线长度 / tour length |
| direction | `min` (lower is better) |
| baseline | `5757191` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p010-mona-lisa-tsp/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

What is the shortest closed tour through the 100,000 cities of the Mona Lisa TSP instance?

## Problem

The instance `mona-lisa100K.tsp` (Bosch, 2009) has 100,000 cities with integer coordinates between 0 and 20,000 in the plane, placed so that a short tour draws Leonardo da Vinci's Mona Lisa as one continuous line. Find a tour that visits every city exactly once and returns to the start, as short as you can.

Distances follow TSPLIB `EUC_2D`: the distance between cities i and j is nint(√((x_i − x_j)² + (y_i − y_j)²)), the Euclidean distance rounded to the nearest integer. The verifier computes it exactly with integers: with s = dx² + dy² and r = ⌊√s⌋ (`math.isqrt`), the distance is r + 1 if s > r² + r and r otherwise. The length of a tour is the sum of its 100,000 edge lengths, an integer.

Known bounds: 5,757,084 ≤ optimum ≤ 5,757,191, a gap of 107.

The coordinates are embedded in `verify/verify.py` (zlib-compressed, base85-encoded, checked by sha256). The tests rebuild `mona-lisa100K.tsp` byte for byte from them and check the sha256 of the file published on the challenge page.

## Why it matters

The Mona Lisa instance is a standing TSP challenge, listed with its bounds on William Cook's TSP pages, where Cook offers a prize of 1,000 US dollars to the first person to find a tour shorter than 5,757,191. That tour was found by Nagata (2009) with a genetic algorithm; earlier tours of 5,757,199 to 5,757,204 came from Helsgaun's LKH and from Dong, Ernst, Jäger, Richter and Molitor (2009). The lower bound 5,757,084 was obtained with Concorde (Applegate, Bixby, Chvátal, Cook) in 2012 after many CPU-years of branch-and-cut.

A tour of length 5,757,190 or less is a new best-known tour for the instance. A tour of length 5,757,084 would be provably optimal and close the instance.

## Certificate

- File name `certificate.json`, shaped like `{"tour": [c1, c2, …, c100000]}`, with no other keys.
- The tour lists the 100,000 city numbers in visiting order. Cities are numbered 1 … 100000 as in the `NODE_COORD_SECTION` of `mona-lisa100K.tsp` (1-based, so `[0, 1, …, 99999]` is rejected). Each city appears exactly once; the tour closes from the last city back to the first.
- The score is the tour length under `EUC_2D`, an integer.
- The file is UTF-8 JSON, at most 2 MiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: the tour rotated so that city 1 comes first, then of the two directions the one whose second city has the smaller number. `canonical_hash` is the sha256 of the canonical JSON, so the same cycle written from another start or in the other direction hashes the same.

## Baseline

The tour of length 5,757,191 found by Nagata (2009), the best-known tour. It is the file `monalisa_5757191.tour` from Cook's Mona Lisa page (TSPLIB tour format, city numbers 1 … 100000), converted to this format in the same order; the verifier reproduces length 5,757,191 exactly.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p010-mona-lisa-tsp/verify/verify.py problems/p010-mona-lisa-tsp/baseline
```

Sources: [Mona Lisa TSP challenge page, with the prize offer and the record tour](https://www.math.uwaterloo.ca/tsp/data/ml/monalisa.html); [mona-lisa100K.tsp](https://www.math.uwaterloo.ca/tsp/data/ml/mona-lisa100K.tsp); [monalisa_5757191.tour](https://www.math.uwaterloo.ca/tsp/data/ml/tour/monalisa_5757191.tour); [TSPLIB 95, distance functions](http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/); [Concorde](https://www.math.uwaterloo.ca/tsp/concorde/index.html).
