module

import Lean
import all Lean.Util.CollectAxioms

/-!
Compare independently compiled versions of the same module against identical imported dependencies.
The optional namespace-prefix mode checks a reference already compiled under a fresh namespace.
Compile and replay artifacts separately.

Read the exported object for coverage and the private object for kernel bodies. Inductive
metadata and recursor rules must match structurally. The audit loads both environments with
extension initialization disabled.
-/

open Lean

private def binders : Expr → List (Name × BinderInfo)
  | .forallE n _ body bi => (n.eraseMacroScopes, bi) :: binders body
  | _ => []

private def checkEq (env : Environment) (n : Name) (field : String) (a b : Expr) : IO Unit := do
  unless Kernel.isDefEq env {} a b matches .ok true do
    throw <| IO.userError s!"Kernel {field} mismatch: {n}"
  let (same, _, _) ← (Meta.withTransparency .all (Meta.isDefEq a b)).toIO
    { fileName := "<oracle>", fileMap := default } { env }
  unless same do throw <| IO.userError s!"Meta {field} mismatch: {n}"

private def auditPair (env : Environment) (a b : ConstantInfo) : IO Bool := do
  let c := b.name
  unless a.levelParams == b.levelParams && binders a.type == binders b.type do
    throw <| IO.userError s!"Universe or binder mismatch: {c}"
  checkEq env c "type" a.type b.type
  match a, b with
  | .thmInfo _, .thmInfo _ => return false
  | .defnInfo x, .defnInfo y =>
    unless x.hints == y.hints && x.safety == y.safety do
      throw <| IO.userError s!"Definition metadata mismatch: {c}"
    checkEq env c "value" x.value y.value
    return true
  | .opaqueInfo x, .opaqueInfo y =>
    unless x.isUnsafe == y.isUnsafe do throw <| IO.userError s!"Opaque safety mismatch: {c}"
    checkEq env c "opaque value" x.value y.value
    return false
  | .inductInfo _, .inductInfo _ | .ctorInfo _, .ctorInfo _ | .recInfo _, .recInfo _ =>
    unless a == b do throw <| IO.userError s!"Inductive family mismatch: {c}"
    return false
  | _, _ => throw <| IO.userError s!"Different or unsupported declaration kind: {c}"

/-- Dependencies whose meaning can affect conversion. Proof bodies are audited for axioms. -/
private def conversionDeps (a : ConstantInfo) : Array Name := Id.run do
  let deps := a.type.getUsedConstants
  match a with
  | .defnInfo v => return deps ++ v.value.getUsedConstants
  | .opaqueInfo v => return deps ++ v.value.getUsedConstants
  | .inductInfo v => return deps ++ v.all.toArray ++ v.ctors.toArray
  | .ctorInfo v => return deps.push v.induct
  | .recInfo v =>
    return v.rules.foldl (fun ds r => ds.push r.ctor ++ r.rhs.getUsedConstants) (deps ++ v.all.toArray)
  | _ => return deps

/-- Use Lean's kernel-body walk, sharing its dependency cache across roots. The callback
always misses, so extension-provided axiom summaries cannot influence the result. -/
private def axiomSets (env : Environment) (names : Array Name) : Array (Array Name) :=
  CollectAxioms.runM env <| names.mapM <| CollectAxioms.collectAndGet fun _ _ => none

private def exports (m : ModuleData) := (m.constNames.filter (!isPrivateName ·)).qsort Name.lt

private def info (env : Environment) (n : Name) : IO ConstantInfo := do
  let some i := env.checked.get.find? n | throw <| IO.userError s!"Missing declaration: {n}"
  return i

private def compareModules (refEnv env : Environment) (ref cand : ModuleData)
    (rename : Name → Name) (sameName : Bool) (modName : Name) : IO UInt32 := do
  unless ref.imports == cand.imports && ref.isModule == cand.isModule do
    throw <| IO.userError "Direct import mismatch"
  let names := exports ref
  let mapped := names.map rename
  let actual := exports cand
  unless mapped.qsort Name.lt == actual do
    throw <| IO.userError s!"Export mismatch; missing={mapped.filter (!actual.contains ·)}, added={actual.filter (!mapped.contains ·)}"
  let publicInfo := cand.constants.foldl (init := ({} : NameMap ConstantInfo))
    fun m c => m.insert c.name c
  for a in ref.constants do
    if isPrivateName a.name then continue
    let some b := publicInfo.find? (rename a.name) | throw <| IO.userError "Missing public entry"
    unless a.ctorIdx == b.ctorIdx do throw <| IO.userError s!"Public visibility mismatch: {b.name}"
  let refAx := axiomSets refEnv names
  let candAx := axiomSets env mapped
  let mut allAx : NameSet := {}
  let mut defs := 0
  let mut todo := #[]
  for n in names, m in mapped, expected in refAx, observed in candAx do
    for ax in observed do
      unless #[`propext, `Classical.choice, `Quot.sound].contains ax do
        throw <| IO.userError s!"Forbidden axiom {ax} in {m}"
      allAx := allAx.insert ax
    -- Test equality of types and values even when both expressions have the same head symbol.
    let a ← info refEnv n
    if ← auditPair env a (← info env m) then defs := defs + 1
    unless expected == observed do throw <| IO.userError s!"Axiom set mismatch for {m}"
    if sameName then
      todo := todo ++ conversionDeps a
  -- A reference expression may mention a private helper. Its original meaning must also
  -- be valid in the candidate environment. The imported dependency artifacts are shared.
  let mut seen := names.foldl (init := ({} : NameSet)) fun s n => s.insert n
  let some idx := refEnv.getModuleIdx? modName | throw <| IO.userError "Missing reference module"
  while let some n := todo.back? do
    todo := todo.pop
    if seen.contains n || refEnv.getModuleIdxFor? n != some idx then continue
    seen := seen.insert n
    let a ← info refEnv n
    discard <| auditPair env a (← info env n)
    todo := todo ++ conversionDeps a
  IO.println s!"ORACLE_AUDIT_PASSED exports={names.size} definitions={defs} axioms={allAx.toArray.qsort Name.lt}"
  return 0

public unsafe def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  match args with
  | ["--same", refRoot, candRoot, modStr] =>
    let base ← searchPathRef.get
    let modName := modStr.toName
    searchPathRef.set (System.FilePath.mk refRoot :: base)
    let (ref, _) ← readModuleData (modToFilePath refRoot modName "olean")
    withImportModules #[{module := modName}] {} fun refEnv => do
      searchPathRef.set (System.FilePath.mk candRoot :: base)
      let (cand, _) ← readModuleData (modToFilePath candRoot modName "olean")
      withImportModules #[{module := modName}] {} fun env =>
        compareModules refEnv env ref cand id true modName
  | [refStr, candStr, prefixStr] =>
    let r := refStr.toName
    let c := candStr.toName
    let ns := prefixStr.toName
    let (ref, _) ← readModuleData (← findOLean r)
    let (cand, _) ← readModuleData (← findOLean c)
    unless (exports ref).all ns.isPrefixOf do throw <| IO.userError "Unprefixed reference export"
    withImportModules #[{module := r}, {module := c}] {} fun env =>
      compareModules env env ref cand (·.replacePrefix ns .anonymous) false r
  | _ => throw <| IO.userError "usage: OracleAudit --same REF_ROOT CAND_ROOT MODULE, or REF_MODULE CAND_MODULE REF_NAMESPACE"
