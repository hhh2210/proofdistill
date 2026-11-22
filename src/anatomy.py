"""First-principles empirical anatomy of the 17.37M-line Alpöge Lean 4 RH archive.

Aligned against the exact kernel dependency cone of `riemannHypothesis`
(cut-modules.txt.xz from vincitamore/riemann-lean-account).
Computes mutually exclusive line budgets, mechanistic bloat signatures,
in-cone duplication metrics, Pareto directory concentration, and
stratified depth-0 candidates for ProofDistill-Bench.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import re
import time

ARCHIVE_SRC = Path("/Volumes/Work/scratch-data/20261121-alpoge-rh/source/lean/src")
MODULES_GZ = Path("/Volumes/Work/scratch-data/20261121-alpoge-rh/port/replay/tracker/modules.jsonl.gz")
CUT_MODULES_XZ = Path("/Volumes/Work/scratch-data/20261121-alpoge-rh/cone/cut-modules.txt.xz")
OUT_DIR = Path("/Users/larry_1/Research/proofdistill/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DECL_START_RE = re.compile(
    rb"^(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+|scoped\s+|local\s+)*"
    rb"(theorem|lemma|def|abbrev|structure|class|instance|inductive)\b"
)
BOILER_RE = re.compile(
    rb"^(?:open\b|namespace\b|end\b|section\b|variable\b|set_option\b|attribute\b|universe\b|local\s+notation|scoped\s+notation|notation\b|macro\b|elab\b|#)"
)
THM_BLOCK_RE = re.compile(
    rb"^(?:private )?(?:theorem|lemma) ([A-Za-z_][A-Za-z_0-9']*(?:\.[A-Za-z_][A-Za-z_0-9']*)*)"
    rb"(?=[ \t:({\[]|\.\{)([^\n]*(?:\n(?:[ \t][^\n]*)?)*)",
    re.M,
)
WS_RE = re.compile(rb"\s+")
BINDER_GROUP_RE = re.compile(r"([({])([A-Za-z_][A-Za-z0-9_']*(?:\s+[A-Za-z_][A-Za-z0-9_']*)*)\s*:")
IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_']*)\b")
LEAN_KW = frozenset({
    "Type", "Prop", "Sort", "fun", "forall", "let", "in", "by", "have", "show",
    "if", "then", "else", "match", "with", "where", "do", "return", "true", "false",
    "Nat", "Int", "Real", "Complex", "Rat", "Fin", "Set", "Finset", "Filter",
    "Function", "Matrix", "Polynomial", "Submodule", "Ideal", "Ring", "Field",
    "CommRing", "Module", "Algebra", "Group", "AddGroup", "Continuous", "Measurable",
})

EXPLICIT_DUMP_RE = re.compile(rb"\binst_\d+\b|\bEq\.\{|\.\{u_\d+|_root_\.[A-Z]")
HEARTBEAT_OPT_RE = re.compile(rb"set_option\s+maxHeartbeats\s+(\d+)")
# Coarse tactic counters (line-initial after whitespace)
TACTIC_PATTERNS = {
    "have": re.compile(rb"^[ \t]+(?:have|haveI)\b", re.M),
    "let": re.compile(rb"^[ \t]+(?:let|letI|set)\b", re.M),
    "rw": re.compile(rb"^[ \t]+(?:rw|rwa|erw)\b", re.M),
    "simp": re.compile(rb"^[ \t]+(?:simp|simpa|simp_all|dsimp)\b", re.M),
    "exact": re.compile(rb"^[ \t]+(?:exact|refine|apply)\b", re.M),
    "calc": re.compile(rb"^[ \t]+calc\b", re.M),
    "linear_arith": re.compile(rb"^[ \t]+(?:omega|linarith|nlinarith|positivity|ring|ring_nf|field_simp|norm_num)\b", re.M),
    "aesop_grind": re.compile(rb"^[ \t]+(?:aesop|grind|tauto|decide|trivial)\b", re.M),
    "intro_rcases": re.compile(rb"^[ \t]+(?:intro|rintro|rcases|obtain|cases|induction)\b", re.M),
}


def load_cone_modules() -> set:
    cone = set()
    with lzma.open(CUT_MODULES_XZ, "rt") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # Handle either "ModuleName" or "ModuleName count ..."
            tok = s.split()[0]
            cone.add(tok)
    return cone


def alpha_norm_header(header_str: str) -> str:
    depth = 0
    colon_pos = -1
    for i, ch in enumerate(header_str):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            if i + 1 < len(header_str) and header_str[i + 1] == "=":
                continue
            colon_pos = i
            break
    if colon_pos < 0:
        return header_str
    binders_part = header_str[:colon_pos]
    mapping = {}
    for m in BINDER_GROUP_RE.finditer(binders_part):
        for nm in m.group(2).split():
            if nm not in mapping and nm not in LEAN_KW and len(nm) <= 16:
                mapping[nm] = f"${len(mapping)}"
    if not mapping:
        return header_str

    def repl(m):
        w = m.group(1)
        if m.start() > 0 and header_str[m.start() - 1] == ".":
            return w
        return mapping.get(w, w)

    return IDENT_RE.sub(repl, header_str)


def main():
    t0 = time.monotonic()
    cone_mods = load_cone_modules()
    print(f"Loaded {len(cone_mods)} cone modules.")

    # Totals split by in-cone vs dead-module
    macro = {
        "in_cone": Counter(),
        "dead_module": Counter(),
    }
    line_budget = {
        "in_cone": Counter(),
        "dead_module": Counter(),
    }
    tactics = {
        "in_cone": Counter(),
        "dead_module": Counter(),
    }
    by_root = defaultdict(lambda: Counter())
    by_dom3 = defaultdict(lambda: Counter())
    by_dom4 = defaultdict(lambda: Counter())

    # Fragmentation histograms (in-cone)
    decls_per_file_hist = Counter()
    lines_per_file_hist = Counter()
    wrapper_like_files = 0
    wrapper_like_lines = 0

    # Explicit dump stats
    explicit_dump_files = Counter()
    explicit_dump_lines = Counter()
    long_lines_200 = Counter()
    long_lines_500 = Counter()
    max_hb_files = Counter()
    max_hb_values = Counter()

    # In-cone duplication (exact, header, alpha) + per-domain duplication
    in_cone_exact = Counter()
    in_cone_hdr = Counter()
    in_cone_alpha = Counter()
    in_cone_alpha_lines = Counter()
    in_cone_alpha_dom = {}
    in_cone_alpha_sample = {}

    # Family suffix patterns (e.g. Statement, Proof, Cpt, numbered)
    suffix_stats = Counter()
    ns_prefix_stats = Counter()

    # ProofDistill candidate pool (in-cone, depth 0, >= 300 lines, excluding 3 known)
    EXCLUDED = {"M115085", "M115707", "M115552"}
    candidates_d0 = []

    with gzip.open(MODULES_GZ, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            mod = row["module"]
            rel = mod.replace(".", "/") + ".lean"
            path = ARCHIVE_SRC / rel
            if not path.is_file():
                continue
            raw = path.read_bytes()
            in_cone = mod in cone_mods
            bucket = "in_cone" if in_cone else "dead_module"

            lines = raw.splitlines()
            n_lines = len(lines)
            n_bytes = len(raw)
            depth = row.get("depth", -1)
            n_imports_idx = len(row.get("imports", []))

            macro[bucket]["files"] += 1
            macro[bucket]["lines"] += n_lines
            macro[bucket]["bytes"] += n_bytes

            parts = mod.split(".")
            root = parts[0]
            dom3 = ".".join(parts[:3]) if len(parts) >= 3 else mod
            dom4 = ".".join(parts[:4]) if len(parts) >= 4 else dom3

            # Per-line mutually exclusive budget classification
            mode = "preamble"  # preamble | def | thm_hdr | thm_proof
            n_thms = 0
            n_defs = 0
            n_pub_decls = 0
            n_imp_lines = 0
            n_proof_lines = 0
            n_dump_lines_file = 0

            for ln in lines:
                s = ln.strip()
                if not s:
                    line_budget[bucket]["blank"] += 1
                    continue
                if len(ln) >= 200:
                    long_lines_200[bucket] += 1
                if len(ln) >= 500:
                    long_lines_500[bucket] += 1
                if EXPLICIT_DUMP_RE.search(ln):
                    n_dump_lines_file += 1

                if ln.startswith(b"import "):
                    line_budget[bucket]["import"] += 1
                    n_imp_lines += 1
                    mode = "preamble"
                    continue

                if not ln.startswith((b" ", b"\t")):
                    if BOILER_RE.match(ln):
                        line_budget[bucket]["boilerplate"] += 1
                        mode = "preamble"
                        continue
                    dm = DECL_START_RE.match(ln)
                    if dm:
                        kind = dm.group(1)
                        is_priv = b"private " in ln[:dm.start(1)]
                        if not is_priv:
                            n_pub_decls += 1
                        if kind in (b"theorem", b"lemma"):
                            n_thms += 1
                            if b":= by" in ln or b":=" in ln:
                                line_budget[bucket]["thm_header"] += 1
                                mode = "thm_proof"
                            else:
                                line_budget[bucket]["thm_header"] += 1
                                mode = "thm_hdr"
                        else:
                            n_defs += 1
                            line_budget[bucket]["def_decl"] += 1
                            mode = "def"
                        continue

                # Continuation line
                if mode == "thm_hdr":
                    line_budget[bucket]["thm_header"] += 1
                    if b":= by" in ln or b":=" in ln:
                        mode = "thm_proof"
                elif mode == "thm_proof":
                    line_budget[bucket]["thm_proof"] += 1
                    n_proof_lines += 1
                elif mode == "def":
                    line_budget[bucket]["def_decl"] += 1
                else:
                    line_budget[bucket]["other"] += 1

            macro[bucket]["theorems"] += n_thms
            macro[bucket]["defs"] += n_defs

            if n_dump_lines_file > 0:
                explicit_dump_files[bucket] += 1
                explicit_dump_lines[bucket] += n_dump_lines_file

            for hm in HEARTBEAT_OPT_RE.finditer(raw):
                max_hb_files[bucket] += 1
                val = int(hm.group(1))
                if val >= 1000000:
                    max_hb_values["ge_1M"] += 1
                elif val >= 400000:
                    max_hb_values["400k_1M"] += 1
                else:
                    max_hb_values["lt_400k"] += 1
                break

            for tname, tre in TACTIC_PATTERNS.items():
                c = len(tre.findall(raw))
                if c:
                    tactics[bucket][tname] += c

            if in_cone:
                by_root[root]["files"] += 1
                by_root[root]["lines"] += n_lines
                by_root[root]["imp_lines"] += n_imp_lines
                by_root[root]["proof_lines"] += n_proof_lines
                by_root[root]["dump_lines"] += n_dump_lines_file
                by_root[root]["theorems"] += n_thms
                by_root[root]["defs"] += n_defs

                by_dom3[dom3]["files"] += 1
                by_dom3[dom3]["lines"] += n_lines
                by_dom3[dom3]["imp_lines"] += n_imp_lines
                by_dom3[dom3]["proof_lines"] += n_proof_lines
                by_dom3[dom3]["dump_lines"] += n_dump_lines_file
                by_dom3[dom3]["theorems"] += n_thms

                by_dom4[dom4]["files"] += 1
                by_dom4[dom4]["lines"] += n_lines
                by_dom4[dom4]["proof_lines"] += n_proof_lines
                by_dom4[dom4]["dump_lines"] += n_dump_lines_file

                tot_d = n_thms + n_defs
                if tot_d == 0:
                    decls_per_file_hist["0"] += 1
                elif tot_d == 1:
                    decls_per_file_hist["1"] += 1
                elif tot_d <= 3:
                    decls_per_file_hist["2-3"] += 1
                elif tot_d <= 10:
                    decls_per_file_hist["4-10"] += 1
                else:
                    decls_per_file_hist["11+"] += 1

                if n_lines <= 25:
                    lines_per_file_hist["1-25"] += 1
                elif n_lines <= 60:
                    lines_per_file_hist["26-60"] += 1
                elif n_lines <= 150:
                    lines_per_file_hist["61-150"] += 1
                elif n_lines <= 500:
                    lines_per_file_hist["151-500"] += 1
                else:
                    lines_per_file_hist["501+"] += 1

                if n_lines <= 20 and n_proof_lines <= 3 and tot_d <= 2:
                    wrapper_like_files += 1
                    wrapper_like_lines += n_lines

                # Naming / structural markers
                leaf = parts[-1]
                if leaf.endswith("Statement"):
                    suffix_stats["*Statement_files"] += 1
                    suffix_stats["*Statement_lines"] += n_lines
                if "Cpt" in leaf:
                    suffix_stats["*Cpt*_files"] += 1
                    suffix_stats["*Cpt*_lines"] += n_lines
                if re.search(r"\d+$", leaf):
                    suffix_stats["*DigitSuffix_files"] += 1
                    suffix_stats["*DigitSuffix_lines"] += n_lines
                if b"UpperTheory.Reformulated" in raw:
                    ns_prefix_stats["UpperTheory.Reformulated_files"] += 1
                    ns_prefix_stats["UpperTheory.Reformulated_lines"] += n_lines
                if b"GlobalTheory." in raw:
                    ns_prefix_stats["GlobalTheory_files"] += 1

                # In-cone theorem duplication
                for m in THM_BLOCK_RE.finditer(raw):
                    blk = m.group(2).strip()
                    idx_by = blk.find(b":= by")
                    if idx_by < 0:
                        continue
                    hdr = WS_RE.sub(b" ", blk[:idx_by].strip())
                    prf = blk[idx_by + 5:]
                    pl = prf.count(b"\n") + 1
                    in_cone_exact[hashlib.sha256(blk).digest()] += 1
                    hkey = hashlib.sha256(hdr).digest()
                    in_cone_hdr[hkey] += 1
                    anorm = alpha_norm_header(hdr.decode("utf-8", "replace"))
                    akey = hashlib.sha256(anorm.encode("utf-8")).digest()
                    in_cone_alpha[akey] += 1
                    in_cone_alpha_lines[akey] += pl
                    if akey not in in_cone_alpha_sample:
                        in_cone_alpha_sample[akey] = (row["id"], dom3, m.group(1).decode("utf-8", "replace"), hdr.decode("utf-8", "replace")[:160])

                # ProofDistill depth-0 candidate pool
                if depth == 0 and n_lines >= 300 and row["id"] not in EXCLUDED:
                    # Normalized token count (rough lexer token count)
                    norm_tokens = len(re.findall(rb"[A-Za-z0-9_']+|[^\sA-Za-z0-9_']", raw))
                    candidates_d0.append({
                        "id": row["id"],
                        "module": mod,
                        "domain3": dom3,
                        "lines": n_lines,
                        "norm_tokens": norm_tokens,
                        "theorems": n_thms,
                        "defs": n_defs,
                        "pub_decls": n_pub_decls,
                        "dump_lines": n_dump_lines_file,
                        "source_sha256": row["source_sha256"],
                    })

    elapsed = round(time.monotonic() - t0, 2)

    # Summarize in-cone duplication
    ic_exact_g = sum(1 for c in in_cone_exact.values() if c >= 2)
    ic_exact_x = sum(c - 1 for c in in_cone_exact.values() if c >= 2)
    ic_hdr_g = sum(1 for c in in_cone_hdr.values() if c >= 2)
    ic_hdr_x = sum(c - 1 for c in in_cone_hdr.values() if c >= 2)
    ic_alpha_g = sum(1 for c in in_cone_alpha.values() if c >= 2)
    ic_alpha_x = sum(c - 1 for c in in_cone_alpha.values() if c >= 2)
    ic_alpha_red_lines = sum(
        int((in_cone_alpha_lines[k] / c) * (c - 1))
        for k, c in in_cone_alpha.items()
        if c >= 2
    )

    # Top in-cone alpha clone clusters (filter out trivial short headers like `: Statement`)
    top_ic_clones = []
    for k, c in in_cone_alpha.items():
        if c < 4:
            continue
        tid, d3, nm, hdr_s = in_cone_alpha_sample[k]
        if len(hdr_s) < 35:
            continue
        avg_l = in_cone_alpha_lines[k] / c
        saved = int((c - 1) * avg_l)
        top_ic_clones.append((saved, c, round(avg_l, 1), tid, d3, nm, hdr_s))
    top_ic_clones.sort(reverse=True)

    # Top Pareto domains
    top_dom3 = sorted(
        ((v["lines"], k, dict(v)) for k, v in by_dom3.items()),
        reverse=True,
    )[:25]
    top_dom4 = sorted(
        ((v["lines"], k, dict(v)) for k, v in by_dom4.items()),
        reverse=True,
    )[:25]

    report = {
        "elapsed_seconds": elapsed,
        "macro": {k: dict(v) for k, v in macro.items()},
        "line_budget": {k: dict(v) for k, v in line_budget.items()},
        "tactics": {k: dict(v) for k, v in tactics.items()},
        "fragmentation_in_cone": {
            "decls_per_file": dict(decls_per_file_hist),
            "lines_per_file": dict(lines_per_file_hist),
            "wrapper_like_files": wrapper_like_files,
            "wrapper_like_lines": wrapper_like_lines,
        },
        "explicit_dumps": {
            "files_with_dump_markers": dict(explicit_dump_files),
            "lines_with_dump_markers": dict(explicit_dump_lines),
            "long_lines_ge_200": dict(long_lines_200),
            "long_lines_ge_500": dict(long_lines_500),
            "maxHeartbeats_files": dict(max_hb_files),
            "maxHeartbeats_buckets": dict(max_hb_values),
        },
        "naming_patterns_in_cone": {
            "suffixes": dict(suffix_stats),
            "namespaces": dict(ns_prefix_stats),
        },
        "in_cone_duplication": {
            "exact_groups": ic_exact_g,
            "exact_extra": ic_exact_x,
            "header_groups": ic_hdr_g,
            "header_extra": ic_hdr_x,
            "alpha_groups": ic_alpha_g,
            "alpha_extra": ic_alpha_x,
            "alpha_est_redundant_proof_lines": ic_alpha_red_lines,
            "top_20_nontrivial_clones": [
                {"saved_lines": s, "occ": c, "avg_lines": al, "task": tid, "domain3": d3, "name": nm, "header": hs}
                for s, c, al, tid, d3, nm, hs in top_ic_clones[:20]
            ],
        },
        "by_root_in_cone": {k: dict(v) for k, v in sorted(by_root.items(), key=lambda x: -x[1]["lines"])},
        "top_25_dom3_in_cone": [{"domain": k, **v} for _, k, v in top_dom3],
        "top_25_dom4_in_cone": [{"domain": k, **v} for _, k, v in top_dom4],
        "proofdistill_d0_in_cone_ge300_count": len(candidates_d0),
    }

    (OUT_DIR / "anatomy_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    candidates_d0.sort(key=lambda x: -x["lines"])
    (OUT_DIR / "proofdistill_d0_pool.json").write_text(json.dumps(candidates_d0, indent=2, ensure_ascii=False))
    print(f"Anatomy complete in {elapsed}s -> {OUT_DIR / 'anatomy_report.json'}")


if __name__ == "__main__":
    main()
