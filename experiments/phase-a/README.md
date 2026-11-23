# Phase A · Splitting the variables of a polynomial

Four private lemmas made the argument about disjoint variable sets reusable in `MonoCount.lean`. On the whole module, Arm B added nine lines and 173 normalized tokens over local simplification alone. It saved 756 elaboration heartbeats (0.45%). The source and editor artifact both grew. This case does not meet the RH submission threshold.

## Results

| Pinned Windows build | Upstream | A · local simplification | B · shared lemmas |
|---|---:|---:|---:|
| Raw lines | 1,878 | 1,873 | 1,882 |
| Comment-stripped tokens | 28,806 | 29,299 | 29,472 |
| Source bytes | 100,508 | 102,006 | 102,422 |
| `.ilean` bytes | 323,859 | 328,328 | 334,087 |
| Median `-j1` compile, seconds | 40.774 | 40.894 | 48.432 |
| Three compile times, seconds | 40.774, 49.518, 40.390 | 50.083, 40.894, 37.747 | 41.908, 50.813, 48.432 |
| Sum of declaration heartbeats | 167,754 | 168,158 | 167,402 |
| Warnings | 87 | 0 | 0 |

The primary comparison is B versus A. Both compiled with warnings promoted to errors. The upstream control used the same project options with warnings recorded. Removing those 87 warnings accounts for some of the difference between upstream and either arm. In particular, several exported theorems have unused instance parameters. Spelling out the existing telescope retained the original binder order and visibility, at a cost in tokens. All versions have the same 15 existing `set_option` directives. [Measurements](measurements.json)

## Module and interventions

At the pinned upstream revision, `MonoCount` has one direct RH import, 15 transitive RH dependencies, 228 lines starting with `have` after indentation (121 per thousand lines), and zero lines matching the dump detector in `src/anatomy.py`. Its multivariate polynomials have two complementary sets of variables. The file uses `IsF` and `IsL` to describe polynomials supported on either side. The proofs of compatibility with the Lie algebra action repeatedly split monomials into these two factors. [Pinned Lean source](https://github.com/leanprover-community/riemann-hypothesis/blob/c592e91eb8f41bfd149227c09460fae0c17bf3c5/src/Formalism/PolynomialDimension/MultinomialDepth/MonoCount.lean)

- **Arm A** keeps the definitions and proposition interfaces. It simplifies local proofs of membership in a filtered list, projection of an exponent onto either side of the partition, and support of a monomial. It includes the warning fixes shared by both arms. [Upstream to A](A.patch)
- **Arm B** starts from A and adds four private theorems. One describes how the exponent of a product splits, one establishes support for a scalar monomial, and one characterizes support on the zero locus of a nonnegative weight. The fourth proves that two linear maps agreeing on products from complementary variable sets agree everywhere. The proofs for the slice and extension operators both use it. Only this additional step is charged to B. [A to B](B.patch)

The support and operator proofs were selected by inspection before timing. This is one hand-edited module with a matched local baseline. It measures the four abstractions together. It does not estimate how much of the archive can be compressed, the effect of each lemma individually, or the best possible refactor of this module.

## Controls and verification

The experiment pins RH `c592e91eb8f41bfd149227c09460fae0c17bf3c5`, Mathlib `fc4f59e577feb1a4956671bc04ac18aaaf8cd842`, and Lean 4.36.0 `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`. All nine timed runs used the same Windows host and SSD, a fresh Lean process, the canonical module name, the same compiled dependencies and `-j1`. After an upstream warm-up the orders were upstream/A/B, A/B/upstream, and B/upstream/A. Timings include import loading and artifact writes. The host was shared. One other Lean-related process was present at five of the nine launches. The measured ranges overlap, so these medians do not establish a speed difference.

Heartbeats were measured in separate builds. Each run wrapped every source declaration with Mathlib's `#count_heartbeats in`, which elaborates the declaration synchronously and reports raw heartbeats divided by 1,000, rounded down. The reported total sums 121 commands in upstream and A, and 125 in B. This measures declaration elaboration and excludes process start, import loading, and output writes. [Measurement runner](measure.py)

Both candidate objects passed two-sided export comparison against the unedited upstream object under the same module name. Each has 152 public declarations. Kernel and meta definitional equality held on every public type and all 24 definition values. The audit also checked direct imports, export kinds, universe parameters, binder names and visibility, definition safety and reducibility hints, and matching transitive axiom sets for each export. Their union was `propext`, `Classical.choice`, and `Quot.sound`. All three target objects passed kernel replay. [Oracle and fixtures](../../oracle/README.md) · [Verification records](verification.json)

For the downstream check we identified all four direct importers in the pinned tree. Their combined closure has 561 RH modules. We restored 506 unaffected module archives from the SHA-256-verified Lean 4.36 baseline after verifying the source blobs against its Git revision, and used our own builds for the target and its 15 dependencies. On macOS we rebuilt all 39 affected descendants in topological order. On Windows we then used those intermediate objects with the Windows-built target and its 15 dependencies, and compiled all four unedited direct callers from source. The unchanged `CountingStatementReduction` emitted 68 warnings. Replacing the target object with the upstream build produced byte-identical diagnostics in a separate control.

The collision check covered 137 open PRs at selection time. We ignored the nine specified repository-wide PRs and compared the exact target path against the merge-base-to-head Git tree diff for all 128 others, including #262. An earlier candidate, `LatticeSumBounds`, was discarded because #221 already rewrites its row estimates. [Snapshot with commit pairs](collision.tsv) · [PR #221](https://github.com/leanprover-community/riemann-hypothesis/pull/221)

## Reproduce

Use Python 3.11+, Git, and the pinned Lean, with Mathlib and its package libraries on `LEAN_PATH`. The upstream checkout must contain the pinned revision. The runner extracts the common dependencies and three target sources into a fresh directory. It verifies the patched source hashes before compiling. Run the following from ProofDistill.

```sh
python oracle/test_oracle.py /path/to/fixture-work
python experiments/phase-a/run.py /path/to/riemann-hypothesis /path/to/fresh-work
```

`src/lexer_metrics.py` supplies the token counts. The source snapshot and patch order above fix the comparison. The full RH build, Comparator and CI are outside this single-module experiment.

To repeat the direct-importer check with the upstream build system, use a disposable RH checkout at the pin, restore its ordinary build cache, and place the regenerated B file at `src/Formalism/PolynomialDimension/MultinomialDepth/MonoCount.lean`. Build the four direct clients there.

```sh
lake build Formalism.ThetaLogCoordinates.TraceIsometryWeights.HasLatBasis \
  Formalism.ThetaLogCoordinates.PartnerMeanCoordinates.TheoremMCB \
  Formalism.ThetaLogCoordinates.FockResolutionOnto.FockMonomialProofs.GramBoundUnconditionalOfSat \
  Formalism.SharpRestriction.GrowthBounds.CountingStatementReduction
```

Made with Codex. The measurements and checks above were run on the resulting sources.
