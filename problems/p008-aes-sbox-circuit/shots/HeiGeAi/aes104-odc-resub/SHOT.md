+++
login = "HeiGeAi"
builds_on = ["csbo98/aes105-nonlinear-resub"]
claimed_score = "104"
agent = "Codex"
+++

## Approach

This circuit reduces the merged 105-gate circuit by csbo98 to 104 gates: 33 AND, 68 XOR and 3 XNOR gates. The maximum output depth remains 32. The saving comes from sharing one XOR expression inside the nonlinear core; all gates outside that core are unchanged.

In the starting circuit, write a = t35, c = t40, d = t44 and e = t59. The core computes u = ec, v = u + d, q = ud and f = t49 = c + av, where + denotes XOR and juxtaposition denotes AND. Since Boolean values are idempotent, qv = ud(u + d) = 0, cq = q and eq = q. Consequently fq = q. These identities give

```text
s   = q + ae         = e(a + q)
t50 = f(t68 + q) + a = f*t68 + (a + q).
```

Define h = a + q once, compute s = e*h and t50 = f*t68 + h, and remove z = t68 + q. This replaces five gates (r, s, z, k and t50) with four (h, s, k and t50). The AND count stays the same and one XOR disappears. The core, including its output-factor map, drops from 19 gates to 18.

The rewrite was discovered by an independently written randomized resubstitution search starting from csbo98/aes105-nonlinear-resub. It used full 256-bit wire truth tables, exact observability care masks obtained by complementing each selected root, acyclic divisors, and one- to three-gate replacements. It pruned unused gates and checked all eight output truth tables before accepting unseen equal-size circuits as random-walk steps. With seed 20261027, iteration 1334 produced a 104-gate circuit after 482 accepted rewrites. That intermediate circuit had depth 39. Extracting the identities above and applying them directly to the starting circuit produced the cleaner depth-32 certificate submitted here.

The official verifier accepted this certificate with score "104". A separate scalar implementation checked all 256 inputs by computing GF(2^8) inversion and the AES affine transform, without importing the official verifier or its S-box table. The old and new core outputs also agree on all 16 assignments to a, c, d and e, and as algebraic normal forms over the Boolean polynomial ring. No claim of global minimality is made.

The starting certificate and the observability-based resubstitution idea come from csbo98/aes105-nonlinear-resub. Its underlying construction comes from the repository's Jain (2026) baseline. The search implementation for this attempt was written independently.

## Dead ends

Most admissible rewrites preserved the gate count, and proposals that increased the number of reachable gates were discarded. The successful search trajectory used equal-size rewrites before finding the reduction. The initial 104-gate output had unnecessarily greater depth and extensive changes to the surrounding linear network; applying its useful identities directly to the starting circuit removed those extra changes.

An additional 500-second search from 104 gates completed 183304 root-rewrite iterations without finding a smaller circuit. A separate search on the extracted 18-gate core also found no 17-gate replacement. Exact Z3 synthesis with the existing core output positions fixed, 18 node slots and exactly one wire alias was unsatisfiable, including when all remaining node definitions could change. That result applies only to the fixed template. Broader synthesis across the core boundaries remains unexplored.
