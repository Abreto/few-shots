+++
login = "fancify"
builds_on = ["HeiGeAi/aes104-odc-resub"]
claimed_score = "103"
+++

## Approach

Starting from HeiGeAi's 104-gate circuit, retain its 18-gate inversion core but jointly change the surrounding field representation and the operand bases of the nine quadratic norm products. The resulting circuit has 33 AND, 64 XOR and 6 XNOR gates, totaling 103. Its output depth is 39; depth is not the scored metric.

A semilinear change of the two GF(16) input coordinates is combined with an independent basis choice in each rank-two product plane: (L,M), (L,L+M), or (L+M,M). Over Boolean inputs these choices preserve the quadratic polar part, with their linear differences charged in the norm offsets. An adjoint trace-pairing construction rewires the final products to reuse the same 18 precomputed linear factors and the existing inverse-norm factors. Exact linear synthesis of the outer maps, followed by synthesis of the coupled middle map, gives:

17 prelinear gates + 9 norm AND gates + 16 middle gates + 18 core gates + 18 final AND gates + 25 output gates = 103.

The saving requires optimizing the field change and the independent product-plane choices together. The official verifier returns score "103". A separately implemented scalar checker computes GF(2^8) inversion and the AES affine map directly and agrees on all 256 inputs. This is an upper bound, not a claim of optimality. The retained core and starting construction are credited to HeiGeAi/aes104-odc-resub and its antecedents.

## Dead ends

Local observability-based resubstitution from existing 104-gate circuits, including neutral changes and larger replacements, produced alternative 104-gate circuits but no reduction. Separate searches over field changes with fixed product-plane bases, and over product-plane choices at a fixed field representation, also failed in their documented restricted models. Those separate exclusions did not cover the successful joint family.

Early linear-network heuristics missed useful exact prelayer networks, so promising candidates were checked with exact small-helper synthesis and complete interface costs. Small inversion-core searches frequently timed out; those outcomes were not treated as impossibility proofs. A separate mixed-product construction also reached 103 gates, but this shot submits only the certificate retaining the published 18-gate core.
