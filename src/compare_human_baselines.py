#!/usr/bin/env python3
"""Run the exact same structural & abstraction-layer analyzer (`compare_mathlib.analyze_corpus`)
across 5 flagship Lean 4 research formalizations (`FLT`, `Carleson`, `PrimeNumberTheoremAnd`,
`SphereEversion`, `PFR`) — including within-repo split of `PrimeNumberTheoremAnd` (Core vs IEANTN),
zero-AI-mention Pure Human aggregate (`Carleson + SphereEversion + PFR`), and Human-Curated aggregate
(`+ FLT`) — and compare them side-by-side with Mathlib v4.36 and the Alpöge RH live cone.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from compare_mathlib import analyze_corpus  # noqa: E402

RE_AI_MENTION = re.compile(
    r"\b(claude|anthropic|codex|chatgpt|gpt-4|gpt-5|openai|aristotle|harmonic|llm-generated|ai-generated|copilot|gemini)\b",
    re.I,
)


def count_ai_mentions(root_dir: Path, allowed_mods: set[str] | None = None, prefix: str = "") -> dict:
    """Count .lean files mentioning common LLM/AI coding tools in comments/prose."""
    total_files = 0
    ai_files = 0
    samples: list[str] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if not fn.endswith(".lean"):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(root_dir).with_suffix("")
            mod = (prefix + "." if prefix else "") + ".".join(rel.parts)
            if allowed_mods is not None and mod not in allowed_mods:
                continue
            total_files += 1
            txt = fp.read_text(encoding="utf-8", errors="ignore")
            if RE_AI_MENTION.search(txt):
                ai_files += 1
                if len(samples) < 5:
                    samples.append(str(fp.relative_to(root_dir)))
    return {"files_checked": total_files, "files_with_ai_mention": ai_files, "sample_files": samples}


def git_meta(repo_dir: Path) -> dict:
    try:
        rev = subprocess.check_output(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], text=True).strip()
        date = subprocess.check_output(["git", "-C", str(repo_dir), "show", "-s", "--format=%cs", "HEAD"], text=True).strip()
        remote = subprocess.check_output(["git", "-C", str(repo_dir), "remote", "get-url", "origin"], text=True).strip()
        return {"commit": rev, "date": date, "remote": remote}
    except Exception:
        return {}


def pool_results(raw_list: list[dict]) -> dict:
    pooled: dict = {
        "stats": {},
        "decl_kinds": {},
        "proof_len_buckets": {},
        "indeg_non_stmt": {},
    }
    for k in (
        "files", "total_lines", "import_mathlib_root", "simp_attrs", "ext_attrs",
        "def_lines", "def_prop_lines", "have_lines", "docstrings",
    ):
        pooled["stats"][k] = sum(r["stats"].get(k, 0) for r in raw_list)
    for k in ("class", "structure", "instance", "theorem", "lemma", "def"):
        pooled["decl_kinds"][k] = sum(r["decl_kinds"].get(k, 0) for r in raw_list)
    for k in ("1-5", "6-20", "21-50", "51-150", "151-500", "500+"):
        pooled["proof_len_buckets"][k] = sum(r["proof_len_buckets"].get(k, 0) for r in raw_list)
    tot_f = sum(r["indeg_non_stmt"]["count"] for r in raw_list)
    eq1 = sum(r["indeg_non_stmt"]["buckets"].get("1", 0) for r in raw_list)
    le1 = sum(
        r["indeg_non_stmt"]["buckets"].get("0", 0) + r["indeg_non_stmt"]["buckets"].get("1", 0)
        for r in raw_list
    )
    medians = sorted(r["indeg_non_stmt"]["median"] for r in raw_list)
    pooled["indeg_non_stmt"] = {
        "count": tot_f,
        "pct_eq_1": round(100.0 * eq1 / max(1, tot_f), 2),
        "pct_le_1": round(100.0 * le1 / max(1, tot_f), 2),
        "median": medians[len(medians) // 2],
    }
    return pooled


def summarize(name: str, d: dict, category: str = "", ai_mentions: dict | None = None) -> dict:
    s = d["stats"]
    dk = d["decl_kinds"]
    lines = max(1, s["total_lines"])
    files = max(1, s["files"])
    thms = dk.get("theorem", 0) + dk.get("lemma", 0)
    structs = dk.get("structure", 0)
    insts = dk.get("instance", 0)
    classes = dk.get("class", 0)
    defs = s.get("def_lines", 0)
    def_props = s.get("def_prop_lines", 0)
    simps = s.get("simp_attrs", 0)
    exts = s.get("ext_attrs", 0)
    haves = s.get("have_lines", 0)
    plb = d["proof_len_buckets"]
    long50 = plb.get("51-150", 0) + plb.get("151-500", 0) + plb.get("500+", 0)
    indeg = d["indeg_non_stmt"]
    row = {
        "name": name,
        "category": category,
        "files": files,
        "lines": lines,
        "avg_lines_per_file": round(lines / files, 1),
        "import_mathlib_root_pct": round(100.0 * s.get("import_mathlib_root", 0) / files, 2),
        "classes": classes,
        "class_per_1m_lines": round(classes / (lines / 1e6), 1),
        "structures": structs,
        "instances": insts,
        "inst_per_struct": round(insts / structs, 2) if structs else None,
        "theorems": thms,
        "simp_attrs": simps,
        "simp_pct_of_thms": round(100.0 * simps / max(1, thms), 2),
        "ext_attrs": exts,
        "ext_per_1m_lines": round(exts / (lines / 1e6), 1),
        "def_lines": defs,
        "def_prop_lines": def_props,
        "def_prop_pct": round(100.0 * def_props / max(1, defs), 2),
        "have_lines": haves,
        "have_per_1k_lines": round(haves / (lines / 1e3), 1),
        "long50_count": long50,
        "long50_pct_of_thms": round(100.0 * long50 / max(1, thms), 2),
        "indeg_eq_1_pct": indeg["pct_eq_1"],
        "indeg_le_1_pct": indeg["pct_le_1"],
        "indeg_median": indeg["median"],
        "docstrings": s.get("docstrings", 0),
        "docstrings_per_1k_lines": round(s.get("docstrings", 0) / (lines / 1e3), 1),
    }
    if ai_mentions is not None:
        row["ai_mention_files"] = ai_mentions["files_with_ai_mention"]
    return row


def main() -> None:
    base = Path("/Volumes/Work/scratch-data/20261121-alpoge-rh/human-baselines")
    targets = [
        ("Carleson", base / "carleson", base / "carleson" / "Carleson", "Carleson", "pure_human"),
        ("SphereEversion", base / "sphere-eversion", base / "sphere-eversion" / "SphereEversion", "SphereEversion", "pure_human"),
        ("PFR", base / "pfr", base / "pfr" / "PFR", "PFR", "pure_human"),
        ("FLT", base / "FLT", base / "FLT" / "FLT", "FLT", "human_curated_with_ai"),
        ("PrimeNumberTheoremAnd", base / "PrimeNumberTheoremAnd", base / "PrimeNumberTheoremAnd" / "PrimeNumberTheoremAnd", "PrimeNumberTheoremAnd", "hybrid_total"),
    ]

    raw_results = {}
    repo_meta = {}
    ai_scans = {}
    summaries_by_name = {}

    for label, repo_dir, src_dir, prefix, cat in targets:
        if not src_dir.exists():
            raise SystemExit(f"Missing baseline dir: {src_dir}")
        res = analyze_corpus(src_dir, allowed_mods=None, prefix=prefix, internal_prefix=prefix + ".")
        ai = count_ai_mentions(src_dir, prefix=prefix)
        raw_results[label] = res
        repo_meta[label] = git_meta(repo_dir)
        ai_scans[label] = ai
        summaries_by_name[label] = summarize(label, res, category=cat, ai_mentions=ai)

    # Within-repo PNT+ split: Core (excl. SecondaryDefinitions/IEANTN) vs IEANTN (2026 heavy AI PRs)
    pnt_src = base / "PrimeNumberTheoremAnd" / "PrimeNumberTheoremAnd"
    all_pnt_mods: set[str] = set()
    ieantn_mods: set[str] = set()
    core_pnt_mods: set[str] = set()
    for dirpath, _, filenames in os.walk(pnt_src):
        for fn in filenames:
            if not fn.endswith(".lean"):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(pnt_src).with_suffix("")
            mod = "PrimeNumberTheoremAnd." + ".".join(rel.parts)
            all_pnt_mods.add(mod)
            if "IEANTN" in rel.parts:
                ieantn_mods.add(mod)
            else:
                core_pnt_mods.add(mod)

    pnt_core_res = analyze_corpus(pnt_src, allowed_mods=core_pnt_mods, prefix="PrimeNumberTheoremAnd", internal_prefix="PrimeNumberTheoremAnd.")
    pnt_ieantn_res = analyze_corpus(pnt_src, allowed_mods=ieantn_mods, prefix="PrimeNumberTheoremAnd", internal_prefix="PrimeNumberTheoremAnd.")
    pnt_core_ai = count_ai_mentions(pnt_src, allowed_mods=core_pnt_mods, prefix="PrimeNumberTheoremAnd")
    pnt_ieantn_ai = count_ai_mentions(pnt_src, allowed_mods=ieantn_mods, prefix="PrimeNumberTheoremAnd")

    raw_results["PNT+ Core (excl. IEANTN)"] = pnt_core_res
    raw_results["PNT+/IEANTN (2026 AI PRs)"] = pnt_ieantn_res
    ai_scans["PNT+ Core (excl. IEANTN)"] = pnt_core_ai
    ai_scans["PNT+/IEANTN (2026 AI PRs)"] = pnt_ieantn_ai

    pure_human_3 = pool_results([raw_results["Carleson"], raw_results["SphereEversion"], raw_results["PFR"]])
    human_curated_4 = pool_results([raw_results["Carleson"], raw_results["SphereEversion"], raw_results["PFR"], raw_results["FLT"]])
    human_pooled_5 = pool_results([raw_results[t[0]] for t in targets])

    # Check c592e91eb8 (post-#150 Lean 4.36 main) quick stats for import Mathlib sanity check
    rh_repo = Path("/Volumes/Work/scratch-data/20261121-alpoge-rh/official-refactor/rh-main")
    rh_436_check = {}
    if (rh_repo / ".git").exists():
        pin = "c592e91eb8f41bfd149227c09460fae0c17bf3c5"
        src_list = subprocess.check_output(["git", "-C", str(rh_repo), "ls-tree", "-r", "--name-only", pin, "src"], text=True).splitlines()
        n_lean = sum(1 for l in src_list if l.endswith(".lean"))
        imp_ml = subprocess.check_output(["git", "-C", str(rh_repo), "grep", "-l", "import Mathlib$", pin, "--", "src"], text=True).splitlines()
        rh_436_check = {
            "commit": pin,
            "lean_files_in_src": n_lean,
            "import_mathlib_root_files": len(imp_ml),
            "import_mathlib_root_pct": round(100.0 * len(imp_ml) / max(1, n_lean), 2),
        }

    existing = json.loads((ROOT / "data" / "deep_causal_anatomy.json").read_text())
    all_rows = [
        summarize("Mathlib v4.36 (StdLib)", existing["mathlib"], category="stdlib"),
        summaries_by_name["Carleson"],
        summaries_by_name["SphereEversion"],
        summaries_by_name["PFR"],
        summarize("Pure Human Research (3 repos)", pure_human_3, category="aggregate_pure_human",
                  ai_mentions={"files_with_ai_mention": 0}),
        summaries_by_name["FLT"],
        summarize("Human-Curated Research (4 repos)", human_curated_4, category="aggregate_human_curated",
                  ai_mentions={"files_with_ai_mention": ai_scans["FLT"]["files_with_ai_mention"]}),
        summarize("PNT+ Core (excl. IEANTN)", pnt_core_res, category="analytic_nt_human", ai_mentions=pnt_core_ai),
        summarize("PNT+/IEANTN (2026 AI PRs)", pnt_ieantn_res, category="ai_single_agent_prs", ai_mentions=pnt_ieantn_ai),
        summaries_by_name["PrimeNumberTheoremAnd"],
        summarize("Research Pooled (all 5 repos)", human_pooled_5, category="aggregate_all_5"),
        summarize("Alpöge RH Live Cone (AI)", existing["rh_in_cone"], category="ai_parallel_orchestrator"),
    ]

    out = {
        "repo_metadata": repo_meta,
        "ai_mention_scans": ai_scans,
        "rh_v436_main_check": rh_436_check,
        "summary_table": all_rows,
        "human_baselines_raw": raw_results,
    }
    out_path = ROOT / "data" / "three_way_comparison.json"
    out_path.write_text(json.dumps(out, indent=2))

    hdr = f"{'Corpus':34s} | {'Files':>6s} | {'Lines':>9s} | {'L/f':>5s} | {'cls/M':>6s} | {'ins/s':>5s} | {'simp%':>6s} | {'ext/M':>6s} | {'d:P%':>6s} | {'hv/1k':>6s} | {'>50%':>5s} | {'in=1%':>6s} | {'impML%':>6s} | {'AI?':>3s}"
    print(hdr)
    print("-" * len(hdr))
    for r in all_rows:
        ins = f"{r['inst_per_struct']:.2f}" if r["inst_per_struct"] is not None else "  n/a"
        ai_s = str(r["ai_mention_files"]) if "ai_mention_files" in r else "-"
        print(
            f"{r['name']:34s} | {r['files']:6d} | {r['lines']:9d} | {r['avg_lines_per_file']:5.0f} | "
            f"{r['class_per_1m_lines']:6.1f} | {ins:>5s} | {r['simp_pct_of_thms']:5.2f}% | "
            f"{r['ext_per_1m_lines']:6.1f} | {r['def_prop_pct']:5.2f}% | {r['have_per_1k_lines']:6.1f} | "
            f"{r['long50_pct_of_thms']:4.2f}% | {r['indeg_eq_1_pct']:5.1f}% | {r['import_mathlib_root_pct']:5.1f}% | {ai_s:>3s}"
        )
    if rh_436_check:
        print(f"\nPost-#150 RH v4.36 main ({rh_436_check['commit'][:10]}): {rh_436_check['import_mathlib_root_files']:,} / {rh_436_check['lean_files_in_src']:,} ({rh_436_check['import_mathlib_root_pct']}%) import root Mathlib.")


if __name__ == "__main__":
    main()
