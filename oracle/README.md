# Module equivalence checks

`OracleAudit.lean` compares two independently compiled versions of one module. Put the reference and candidate objects in separate roots and supply identical imported dependencies. Use the pinned Lean executable, compile both sources, and run `leanchecker` separately for kernel replay.

```sh
lean -j1 --run OracleAudit.lean --same /path/to/reference /path/to/candidate Example.Module
```

The audit reads the public export names and declaration kinds from each module's exported object. For each public declaration it checks universe parameters, telescope binder names and visibility, and both kernel and meta definitional equality of the type. For definitions it also checks the reducibility hint, safety, and value. It follows reference-local constants used by those expressions, including private definitions. It compares each export's transitive axiom set and requires that it be a subset of `propext`, `Classical.choice`, and `Quot.sound`.

The comparison uses Lean's kernel-body axiom collector with the lookup of precomputed axiom summaries disabled. Its two import environments load with `loadExts := false`. This tests declaration equivalence. A changed tactic, notation, or global simp attribute can still affect clients, so the experiment also builds downstream source. The older `ReferenceModule CandidateModule ReferenceNamespace` invocation remains available for namespaced fixtures.

## Fixtures

With Lean 4.36.0 on `PATH` and its pinned Mathlib library and package directories on `LEAN_PATH`, run the following from the repository root. Use a work directory on the build volume.

```sh
python oracle/test_oracle.py /path/to/work
```

The positive fixture is the complete RH module proving that a spanning set of functions contains a basis. The refactor supplies the span bound directly to `Module.Basis.mk`. The runner first tests the unedited source as a control. Four separately compiled candidates exercise an admitted proof, a changed proposition, a changed numerical definition, and a missing theorem. Each test requires the specific diagnostic for its intended failure. [Pinned upstream source](https://github.com/leanprover-community/riemann-hypothesis/blob/c592e91eb8f41bfd149227c09460fae0c17bf3c5/src/Formalism/LocalToGlobal/ProjectiveLattices/ArchimedeanQuadraticData/ExistsBasisIn.lean) · [Windows receipt](windows-4.36.json)
