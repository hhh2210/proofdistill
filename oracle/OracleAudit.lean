import Lean

/-!
# ProofDistill Generic Kernel-Level Module Equivalence Oracle

Loads a reference module (`refMod`, containing the published archive declarations
under prefix `refPrefix`) and a candidate compressed module (`candMod`) as pure data
via `withImportModules` (`loadExts := false`), so candidate code cannot execute
initializers or override elaborators/commands.

Verifies all 4 benchmark gates:
  1. Complete two-sided public declaration coverage (no omitted public decls)
  2. Identical declaration kind, universe `levelParams`, and binder `(Name × BinderInfo)` list
  3. Kernel definitional equality (`Kernel.isDefEq`) on types (all decls) and values (`defnInfo`)
  4. Raw kernel transitive axiom walk strictly ⊆ {propext, Classical.choice, Quot.sound}
-/
open Lean

def extractBinders : Expr → List (Name × BinderInfo)
  | .forallE n _ body bi => (n.eraseMacroScopes, bi) :: extractBinders body
  | _ => []

def stripPrefix (pfx name : Name) : Option Name :=
  let rec go : List Name → List Name → Option (List Name)
    | [], rest => some rest
    | p :: ps, n :: ns => if p == n then go ps ns else none
    | _, [] => none
  let pComps := pfx.components
  let nComps := name.components
  (go pComps nComps).map fun comps =>
    comps.foldl (fun acc c => match c with
      | .str _ s => Name.str acc s
      | .num _ k => Name.num acc k
      | .anonymous => acc) .anonymous

def publicDeclsInModule (env : Environment) (modName : Name) : IO (Array Name) := do
  let some idx := env.getModuleIdx? modName
    | throw <| IO.userError s!"Missing module in environment: {modName}"
  let mut out : Array Name := #[]
  for n in env.header.moduleData[idx]!.constNames do
    unless n.isInternalDetail || isPrivateName n do
      out := out.push n
  return out

def rawAxioms (env : Environment) (roots : Array Name) : Except String (Array Name × Nat) := do
  let mut seen : Std.HashSet Name := {}
  let mut axioms : NameSet := {}
  let mut todo := roots
  while !todo.isEmpty do
    let name := todo.back!
    todo := todo.pop
    if seen.contains name then continue
    seen := seen.insert name
    let some info := env.checked.get.find? name
      | throw s!"Unknown proof dependency: {name}"
    if info matches .axiomInfo _ then axioms := axioms.insert name
    todo := todo ++ info.type.getUsedConstants
    if let some value := info.value? (allowOpaque := true) then
      todo := todo ++ value.getUsedConstants
    if let .inductInfo value := info then
      todo := todo ++ value.ctors.toArray
  return (axioms.toArray.qsort Name.lt, seen.size)

def sameKind (a b : ConstantInfo) : Bool :=
  match a, b with
  | .thmInfo _, .thmInfo _ => true
  | .defnInfo _, .defnInfo _ => true
  | .opaqueInfo _, .opaqueInfo _ => true
  | .inductInfo _, .inductInfo _ => true
  | .ctorInfo _, .ctorInfo _ => true
  | .recInfo _, .recInfo _ => true
  | _, _ => false

def auditOnePair (env : Environment) (refName candName : Name) : IO Unit := do
  let some refInfo := env.checked.get.find? refName
    | throw <| IO.userError s!"Missing reference constant: {refName}"
  let some candInfo := env.checked.get.find? candName
    | throw <| IO.userError s!"Missing candidate constant: {candName}"
  unless sameKind refInfo candInfo do
    throw <| IO.userError s!"Declaration kind mismatch for {candName}"
  unless refInfo.levelParams == candInfo.levelParams do
    throw <| IO.userError s!"Universe parameter mismatch for {candName}: {refInfo.levelParams} vs {candInfo.levelParams}"
  unless extractBinders refInfo.type == extractBinders candInfo.type do
    throw <| IO.userError s!"Binder mismatch for {candName}: {repr (extractBinders refInfo.type)} vs {repr (extractBinders candInfo.type)}"
  match Kernel.isDefEq env {} refInfo.type candInfo.type with
  | .ok true => pure ()
  | _ => throw <| IO.userError s!"Type isDefEq failed for {candName}"
  if let (.defnInfo rDef, .defnInfo cDef) := (refInfo, candInfo) then
    match Kernel.isDefEq env {} rDef.value cDef.value with
    | .ok true => pure ()
    | _ => throw <| IO.userError s!"Definition value isDefEq failed for {candName}"

unsafe def main (args : List String) : IO UInt32 := do
  let (refMod, candMod, refPrefix) ← match args with
    | [r, c, p] => pure (r.toName, c.toName, p.toName)
    | _ => throw <| IO.userError "usage: OracleAudit <RefModule> <CandModule> <RefNamespacePrefix>"
  initSearchPath (← findSysroot)
  withImportModules #[{module := refMod}, {module := candMod}] {} fun env => do
    let refDecls ← publicDeclsInModule env refMod
    let candDecls ← publicDeclsInModule env candMod
    let mut pairs : Array (Name × Name) := #[]
    for rn in refDecls do
      let some cn := stripPrefix refPrefix rn
        | throw <| IO.userError s!"Reference decl {rn} does not start with prefix {refPrefix}"
      pairs := pairs.push (rn, cn)
    -- Two-sided public declaration coverage check
    let candSet : Std.HashSet Name := candDecls.foldl (fun s n => s.insert n) {}
    let pairCandSet : Std.HashSet Name := pairs.foldl (fun s p => s.insert p.2) {}
    for (_, cn) in pairs do
      unless candSet.contains cn do
        throw <| IO.userError s!"Candidate omitted public declaration: {cn}"
    for cn in candDecls do
      unless pairCandSet.contains cn do
        throw <| IO.userError s!"Candidate added unexpected public declaration: {cn}"
    -- Pairwise kernel equality + binder/universe checks
    for (rn, cn) in pairs do
      auditOnePair env rn cn
    -- Raw kernel transitive axiom walk on all candidate public declarations
    let (axioms, visited) ← match rawAxioms env (pairs.map Prod.snd) with
      | .ok r => pure r
      | .error e => throw <| IO.userError e
    let allowed : Array Name := #[`propext, `Classical.choice, `Quot.sound]
    for ax in axioms do
      unless allowed.contains ax do
        throw <| IO.userError s!"Forbidden axiom {ax}"
    IO.println s!"ORACLE_AUDIT_PASSED {pairs.size} public_decls; raw_axioms={axioms}; visited={visited}"
    return 0
