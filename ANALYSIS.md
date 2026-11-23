# Why a Multi-Agent LLM Proof Bloats to 17.37M Lines (and Why Mechanical Cleanups Leave >94% Behind)

*Perspective note: written from an LLM-systems engineering angle by someone who knows a bit of math, not a research number theorist. Every statistic below comes from an exact, reproducible full-corpus scan of all `147,489` kernel-live modules in the released Riemann Hypothesis archive (`alpo.ge`) contrasted side-by-side against all `8,712` modules in Mathlib (`v4.36`), implemented in [`src/compare_mathlib.py`](src/compare_mathlib.py) and [`src/anatomy.py`](src/anatomy.py).*

---

## 1. The Puzzle: What Survives After Every Mechanical Cleanup?

Following Levent Alpöge's 17,374,215-line, 175,187-file Lean 4 formalization of the Riemann Hypothesis and Dirichlet GRH — and the Lean FRO / Mathlib Initiative certification — contributors on [`leanprover-community/riemann-hypothesis`](https://github.com/leanprover-community/riemann-hypothesis) quickly shipped impressive mechanical and targeted cleanups (dead-module pruning in #45 and #66, thin `*Statement.lean` wrapper collapsing in #58/#61/#120, `maxHeartbeats` removal in #79/#134, explicit typeclass-dump rewriting in #57/#60/#65/#62/#150, and semantic reuse such as #68 and #94/`8071ca2be8`).

Yet if we do exact line accounting over the `147,489` kernel-live modules (`15,218,364` lines, aligned via `vincitamore`'s exact kernel dependency cone):

| Layer in Live Kernel Cone (`147,489` files) | Live Lines | Share of Live Cone |
|---|---:|---:|
| `*Statement.lean` & `first \| exact @...` glue files | `691,632` | `4.54%` |
| Strict explicit machine-dump files (`inst_\d+` / `.{u_\d+` / `Eq.{`, `717` files) | `114,282` | `0.75%` |
| `maxHeartbeats` override lines | `~76,000` | `~0.50%` |
| **Remaining clean, non-wrapper, non-dump live code** | **`14,412,450`** | **`94.70%`** |

*(Module bundling such as #63/#120 dramatically cuts file count and Lake process-startup overhead, while leaving the underlying proof lines largely unchanged.)*

So the deeper LLM-systems question is not *"why are there dead files or wrapper scripts?"* — it is: **why do 14.4 million lines of clean, live, non-wrapper Lean code remain after stripping surface orchestrator exhaust?**

---

## 2. Exact Side-by-Side Comparison: Human Mathlib vs. AI RH Live Cone

Scanning all `8,712` modules in Mathlib (`v4.36`) alongside all `147,489` live modules in the RH kernel cone exposes four order-of-magnitude structural gaps ([`data/deep_causal_anatomy.json`](data/deep_causal_anatomy.json)):

| Structural Metric (Exact Full-Corpus Scan) | Human Mathlib (`8,712` files) | AI RH Live Cone (`147,489` files) | Gap / System Signal |
|---|---:|---:|---|
| Total lines (avg lines / file) | `2,368,060` (`272` L/file) | `15,218,364` (`103` L/file) | `6.4x` lines, `16.9x` files |
| `class` declarations | **`2,019`** | **`33`** | **`393x` lower density per line** |
| `structure` vs. `instance` | `1,833` / `11,111` (**`6.06`** inst/struct) | **`6,836`** / `3,915` (**`0.57`** inst/struct) | **`3.7x` more structs, `10.6x` fewer instances/struct** |
| `@[simp]` density (`simp / thms`) | `51,114` (**`27.84%`**) | `5,973` (**`0.83%`**) | **`33.7x` lower automation density** |
| `@[ext]` attributes | `1,396` | `104` | **`86.3x` lower density per line** |
| `def ... : Prop :=` contract ratio | `3.29%` (`1,073 / 32,565`) | **`37.07%`** (`65,028 / 175,424`) | **`11.3x` frozen handoff contracts** |
| `have` density (per 1k lines) | `17.1` (`40,574`) | **`124.3`** (`1,891,600`) | **`7.3x` manual step-by-step chaining** |
| Theorems > 50 lines | `1,013` (`0.55%`) | **`45,941`** (`6.36%`) | **`11.5x` share (`45x` count)** |
| Single-caller modules (`in-degree = 1`) | `29.81%` (median `2`) | `61.35%` (**`56.13%`** excl. `*Statement`/glue, median `1`) | Tree-shaped consumption vs. Mathlib DAG |

![Why mechanical cleanups leave >94% of the 15.22M-line AI RH proof behind](figures/fig1_mathlib_vs_rh.png)

*(Note: the released RH archive contains `0` comment lines and `0` `/--` docstrings vs. Mathlib's `77,649`, likely stripped or omitted during release packaging rather than reflecting proof mechanics.)*

---

## 3. Three Distinct Layers (Why It Is Not All "AI Slop")

To stay honest about the actual mathematics in the archive, the 17.37M lines separate cleanly into **three distinct layers**:

1. **Layer 1 — Orchestrator & Elaborator Exhaust (~18% of raw archive: 12.4% dead modules + ~5.8% live wrappers/dumps/heartbeats):** Mechanical byproducts of parallel worker dispatch and explicit term dumping. Existing cleanup PRs target this layer effectively.
2. **Layer 2 — The "Theory-less, Contract-Frozen" Abstraction Tax (LLM-Systems Root Cause):**
   - **Bare-Structure Tax (`6,836` structs, `33` classes, `0.83%` `@[simp]`):** Human Mathlib compiles domain laws into `class` + `instance` + `@[simp]`/`@[ext]` rules so Lean's elaborator and `simp`/`aesop` collapse routine steps automatically. When parallel LLM workers invent `6,836` ad-hoc `structure`s without equipping them with `instance`s or `@[simp]` lemmas, Lean's automation literally has no rules to fire on — driving `1,891,600` manual `have` lines (`7.3x` Mathlib's density) and leaving `aesop`/`grind`/`tauto`/`decide` at `0.01%` combined tactic share.
   - **Contract-Frozen Parallelism (`65,028` `def : Prop` interfaces, `56.1%` single-caller modules):** To run stateless LLM workers in parallel, subgoal interfaces are frozen *before* proofs are discovered (e.g., chains of `def ThinAE : Prop := ExIntervalLt → ExCut → ...` and anonymous `.2.2.2.1` conjunction tuples). Once frozen, downstream workers cannot back-propagate cleaner abstractions upstream, so sibling subtrees re-prove the same building blocks independently (`142,021` duplicate theorem names such as `exists_lift` 377x, `decomp` 202x, `transport` 113x; `54,149` alpha-equivalent theorem clone groups totaling ~`940k` redundant proof lines).
3. **Layer 3 — Genuine Frontier Mathematics Missing from Mathlib:** Inspecting long zero-dump modules such as `Formalism/HermitianCurvature/HermitianCurvatureProofs/StationaryPhaseModel.lean` (`B_step`, Hörmander-style non-stationary phase integration by parts) shows that a real mathematical core is simply absent from Mathlib today and requires substantial code even when written idiomatically.

### A Natural Within-Corpus Experiment

Comparing two zero-dump files inside the **very same RH archive** isolates the Bare-Structure Tax cleanly:

| File (both 0-dump, same archive) | Lines | `class` / `instance` | `@[simp]` / `@[ext]` | `have` count (`per 1k`) | Longest thm |
|---|---:|---:|---:|---:|---:|
| `Development/.../Foundations/MemUnitaryGroupIffIsIsometry.lean` | `923` | `1` / `6` (`4` structs) | **`54`** / **`3`** | **`3`** (`3.2/1k`) | `31 L` |
| `Formalism/.../StationaryPhaseModel.lean` | `3,321` | `0` / `0` (`1` struct, `23` defs) | **`0`** / **`0`** | **`641`** (`193/1k`, **60x**) | `126 L` |

In the rare module where the model actually built a Mathlib-style API layer (`class` + `instance` + `@[simp]` + `@[ext]`), proof ergonomics immediately matched human Mathlib.

---

## 4. Two Engineering Directions Beyond Surface Workarounds

![From Wake-Only parallel proving to Theory-Lifting and Wake-Sleep consolidation](figures/fig2_wake_sleep_architecture.png)

Deterministic cleanup scripts and interface-frozen single-file tactic golfing (as well as single-repo compression benchmarks such as ETH Zurich's [LeanLean](https://leanleanbench.com) when internal module interfaces stay locked) inevitably run into an **Abstraction Ceiling**: you cannot collapse 6,836 unequipped structures and 65,028 frozen `def : Prop` handoffs one file at a time.

From an LLM-systems perspective, two complementary mechanisms directly address the root cause:

1. **Post-Hoc *Theory-Lifting* over Connected Subtrees:**
   Lock *only* the top-level exported theorems of a connected subtree (checked via `Lean.Kernel.isDefEq` + transitive axioms ⊆ `{propext, Classical.choice, Quot.sound}`, see [`oracle/OracleAudit.lean`](oracle/OracleAudit.lean)), and perform three cross-module passes:
   - **Retroactive API Synthesis:** Synthesize missing `instance` + `@[simp]` + `@[ext]` bundles for high-fan-in custom `structure`s, then let `simp`/`grind`/`fun_prop` collapse downstream `have` chains.
   - **Contract Melting:** Inline intermediate `def ... : Prop :=` handoff wrappers and `.2.2.2.1` tuple projections back into parameterized mathematical theorems.
   - **Cross-Branch Anti-Unification:** Cluster `in-degree = 1` sibling subtrees by type skeleton to surface shared lemmas and abstractions (systematizing manual wins like PR #68 `-9,010L` and PR #94 `-1,703L`).
2. **Generation-Time *Wake–Sleep Library-First Synthesis*:**
   Current multi-agent provers are pure **Wake** (top-down subgoal expansion until `lake build` exits 0). Inserting a periodic **Sleep Consolidation Gate** — pausing depth expansion to enforce Mathlib-like library invariants (`instance/struct`, `@[simp]` density, median module fan-in, `have/1k`) and lift recurring concepts into shared abstractions before spawning deeper workers — attacks the bloat before it is emitted.
