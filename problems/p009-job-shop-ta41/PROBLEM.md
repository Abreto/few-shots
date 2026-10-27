# p009 · Job-shop scheduling, Taillard ta41

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p009` |
| metric | 完工时间 / makespan |
| direction | `min` (lower is better) |
| baseline | `2006` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p009-job-shop-ta41/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How quickly can the 30 jobs of Taillard's job-shop instance ta41 be finished on its 20 machines?

## Problem

In the job-shop problem each job is a fixed sequence of operations, one on each machine, and each operation has a processing time. A machine processes one operation at a time, an operation runs without interruption, and a job's operations run in their given order. The makespan of a schedule is the time at which the last operation finishes.

Instance ta41 (Taillard, 1993) has 30 jobs and 20 machines; every job visits every machine once, and the 600 processing times are integers from 1 to 99 (31,279 in total). Find a schedule with the smallest makespan you can. Known bounds: 1915 ≤ optimum ≤ 2006.

The instance is embedded in `verify/verify.py` in the usual two-integers-per-operation format: the first line is `30 20`, then line j + 2 lists job j's operations in route order as `machine duration` pairs. Machines are numbered 0 … 19 and jobs 0 … 29; Taillard's machine k + 1 is machine k here, and his job j + 1 is job j. This is the file `instances/ta41` of the JSPLIB repository, and the tests regenerate it from the seeds Taillard published for ta41 (time seed 1841414609, machine seed 1357882888).

## Why it matters

Taillard's 80 instances are the standard benchmark set for the job-shop problem, and best-known upper and lower bounds for each are tracked in public tables. Most of them are solved; ta41 is not, and it has the largest gap between the bounds among the 30 × 20 instances ta41 – ta50. Its best-known makespan of 2006 is credited to Shylo and Pardalos (2008). The lower bound went from 1912 (Heinz, Hanzálek and Vilím, 2024) to 1915 (Coupvent des Graviers, Kobrosly, Guettier and Cazenave, 2025).

A valid schedule with makespan 2005 or less is a new best-known upper bound for ta41 in these tables. A schedule with makespan 1915 would be provably optimal and close the instance.

## Certificate

- File name `certificate.json`, shaped like `{"machines": [o0, o1, …, o19]}`, with no other keys.
- Entry k is the processing order on machine k: a list of the 30 job numbers 0 … 29, each exactly once, first job first.
- The machine orders, together with the job routes, must be consistent, that is, the disjunctive graph (job arcs plus machine arcs) has no cycle. Otherwise the certificate is invalid.
- Every operation starts as soon as both its job predecessor and its machine predecessor have finished (the semi-active schedule of the given orders). The score is the resulting makespan, an integer.
- The file is UTF-8 JSON, at most 64 KiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: the machine orders themselves, since they determine the schedule. `canonical_hash` is the sha256 of the canonical JSON, so formatting does not change it.

## Baseline

A schedule with makespan 2006, the best-known upper bound for ta41. The machine orders are the solution sequence published for ta41 on optimizizer.com (20 machine orders of 30 jobs, numbered from 0), converted to this format without change of order; the verifier reproduces makespan 2006 exactly.

The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p009-job-shop-ta41/verify/verify.py problems/p009-job-shop-ta41/baseline
```

Sources: [Taillard, Benchmarks for basic scheduling problems, EJOR 1993](https://doi.org/10.1016/0377-2217(93)90182-M); [Taillard's instance page](http://mistic.heig-vd.ch/taillard/problemes.dir/ordonnancement.dir/ordonnancement.html); [JSPLIB, instances/ta41](https://github.com/tamy0612/JSPLIB/blob/master/instances/ta41); [bounds for the Taillard instances](https://optimizizer.com/TA.php); [the 2006 solution](https://optimizizer.com/solution.php?name=ta41&UB=2006&problemclass=ta); [Coupvent des Graviers, Kobrosly, Guettier and Cazenave, arXiv:2504.16106, Table 14](https://arxiv.org/abs/2504.16106); [Heinz, Hanzálek and Vilím, SSRN 4938242](https://doi.org/10.2139/ssrn.4938242).
