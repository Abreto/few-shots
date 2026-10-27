# p002 · Rank of 5×5 matrix multiplication

<!-- few-shots:header -->
| key | value |
| --- | --- |
| id | `p002` |
| metric | 乘法次数 / multiplications |
| direction | `min` (lower is better) |
| baseline | `93` |
| epsilon | `1` (`absolute`) |
| verifier | `python3 problems/p002-matrix-multiplication-5x5/verify/verify.py <shot_dir>` |
<!-- /few-shots:header -->

How few multiplications does a bilinear algorithm need to multiply two 5×5 matrices with rational coefficients?

## Problem

Let A and B be 5×5 matrices and C = AB, so c_ik = Σ_j a_ij b_jk. The entries may come from any ring that contains Q, including blocks of larger matrices: a bilinear algorithm never multiplies two entries of A or two entries of B, and never reorders a product. A bilinear algorithm with r multiplications chooses rational 5×5 matrices U_t, V_t, W_t for t = 1, …, r, forms the r products

m_t = (Σ_ij U_t[i][j] a_ij) · (Σ_jk V_t[j][k] b_jk),

and reads off c_ik = Σ_t W_t[k][i] m_t. Note the transpose on W: this is the standard cyclic form of the matrix multiplication tensor ⟨5,5,5⟩, in which the three factors play symmetric roles. In tensor language the condition is

Σ_t U_t ⊗ V_t ⊗ W_t = Σ_{i,j,k} E_ij ⊗ E_jk ⊗ E_ki,

where E_ij is the matrix with a single 1 in row i, column j. Equivalently, for every i1, j1, j2, k2, k3, i3:

Σ_t U_t[i1][j1] · V_t[j2][k2] · W_t[k3][i3] = 1 if i1 = i3, j1 = j2 and k2 = k3, and 0 otherwise.

The smallest such r is the rank of ⟨5,5,5⟩ over Q. Find a decomposition with as few terms as you can. The schoolbook algorithm uses 125 terms.

## Why it matters

A decomposition of ⟨n,n,n⟩ with r terms, applied recursively to block matrices, multiplies N×N matrices with O(N^(log_n r)) arithmetic operations. Strassen's 7 products for 2×2 matrices give exponent log_2 7 ≈ 2.8074. For 5×5, rank 93 gives log_5 93 ≈ 2.8163. A decomposition with r ≤ 91 would give at most log_5 91 ≈ 2.8028 < log_2 7, so recursion on that one scheme would beat Strassen's exponent; r = 92 would not (log_5 92 ≈ 2.8095).

The rank of ⟨5,5,5⟩ is not known. The upper bound went from 97 (Kauers and Moosbauer, 2023) to 93 (Moosbauer and Poole, 2025). The general lower bound 5/2·n² − 3n (Bläser, 1999) gives only 48 for n = 5. Decompositions that hold only over the field with two elements do not count. Each term removed is a new entry for 5×5×5 in Sedoglavic's catalogue of fast matrix multiplication algorithms.

## Certificate

- File name `certificate.json`, shaped like `{"terms": [[U1, V1, W1], [U2, V2, W2], …]}`, with no other keys.
- Each of U, V, W is a 5×5 matrix written as a list of 5 rows, each a list of 5 entries. Indices in the formulas above are 1-based: U[i][j] is entry j of row i.
- Each entry is a JSON integer or a string `"p/q"` with ASCII decimal integers p and q, for example `-3`, `"1/2"` or `"-7/4"`. Floats are not allowed. |p| ≤ 10^9, 1 ≤ q ≤ 10^9, and the least common multiple of all denominators in the file is at most 10^18.
- No factor matrix is zero. At most 125 terms.
- Σ_t U_t ⊗ V_t ⊗ W_t equals the tensor above exactly. The verifier multiplies every entry by the common denominator D and compares the integer sum with D³ times the target, so it never uses floating point. An invalid certificate is reported with the number of wrong coefficients and the first one.
- The score is the number of terms r.
- The file is UTF-8 JSON, at most 256 KiB, nested at most 8 levels, with no duplicate keys.
- Canonical form: in each term, U and V are divided by their first nonzero entry in row-major order and W is multiplied by the same two numbers, so the term itself is unchanged; entries are written as reduced fractions (integers when the denominator is 1); then the terms are sorted. `canonical_hash` is the sha256 of the canonical JSON, so reordering terms, rescaling factors within a term, and writing `"2/4"` for `"1/2"` do not change it. Other symmetries of the tensor, such as the cyclic shift of U, V, W or a change of basis, give different certificates.

## Baseline

93 terms with integer coefficients in {−2, −1, 0, 1, 2}. Up to the signs of the factors within a term, the set of terms is invariant under the cyclic shift (U, V, W) → (W, U, V): 30 orbits of three terms and 3 fixed terms. This is the scheme of Moosbauer and Poole (2025), found over the field with two elements and lifted to Z by Hensel lifting. It is the current upper bound in Sedoglavic's catalogue.

The certificate is the file `schemes/555m93_lifted.txt` from the authors' repository, converted term by term to this format with no change of convention: each line `(Σ α a_ij) (Σ β b_jk) (Σ γ c_ki)` becomes U = α, V = β, W = γ, and the three lines written as `-(…)` have their sign placed on U. The certificate is `baseline/certificate.json`. To reproduce:

```bash
python3 problems/p002-matrix-multiplication-5x5/verify/verify.py problems/p002-matrix-multiplication-5x5/baseline
```

Sources: [J. Moosbauer, M. Poole, arXiv:2502.04514](https://arxiv.org/abs/2502.04514); [the 93-term scheme](https://github.com/jakobmoosbauer/symmetric-flips/blob/main/schemes/555m93_lifted.txt); [A. Sedoglavic, catalogue entry for 5×5×5](https://fmm.univ-lille.fr/5x5x5.html); [M. Kauers, J. Moosbauer, arXiv:2212.01175](https://arxiv.org/abs/2212.01175); [M. Bläser, FOCS 1999](https://doi.org/10.1109/SFFCS.1999.814576).
