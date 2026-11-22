#!/usr/bin/env python3
"""Compare structural & abstraction-layer metrics between Mathlib and the
live kernel dependency cone of Alpoege's Lean 4 Riemann Hypothesis archive.

Reproduces `data/deep_causal_anatomy.json` and the `def : Prop` / docstring
comparison statistics.
"""

from __future__ import annotations

import argparse
import collections
import json
import lzma
import os
import re
import time
from pathlib import Path

RE_IMPORT = re.compile(
    r"^(?:public\s+|meta\s+|private\s+)*import\s+(?:all\s+)?([A-Za-z0-9_.']+)"
)
RE_DECL = re.compile(
    r"^(?:private\s+|protected\s+|noncomputable\s+|unsafe\s+|partial\s+|scoped\s+|local\s+)*"
    r"(theorem|lemma|def|abbrev|structure|class|inductive|instance|axiom|opaque)\s+([^\s:(\[{]+)"
)
RE_DEF_ANY = re.compile(r"^(?:private\s+|protected\s+|noncomputable\s+)*def\s+")
RE_DEF_PROP = re.compile(
    r"^(?:private\s+|protected\s+|noncomputable\s+)*def\s+\S[^\n]*:\s*Prop\s*:="
)
RE_DOC = re.compile(r"^/--")
RE_SIMP_ATTR = re.compile(r"@\[[^\]]*\bsimp\b|^attribute\s+\[[^\]]*\bsimp\b")
RE_EXT_ATTR = re.compile(r"@\[[^\]]*\bext\b|^attribute\s+\[[^\]]*\bext\b")
RE_HAVE = re.compile(r"^\s*have\b")
RE_CALC = re.compile(r"^\s*calc\b")
RE_DUMP_STRICT = re.compile(r"\binst_\d+|\.\{u_\d+|Eq\.\{")
RE_GLUE = re.compile(r"first\s*\|\s*exact\s*@")


def analyze_corpus(
    root_dir: Path,
    allowed_mods: set[str] | None = None,
    prefix: str = "",
    internal_prefix: str | None = None,
) -> dict:
    """Scan a Lean source tree and measure abstraction, automation, and graph reuse."""
    stats: collections.Counter[str] = collections.Counter()
    decl_kinds: collections.Counter[str] = collections.Counter()
    in_deg: collections.Counter[str] = collections.Counter()
    out_deg: collections.Counter[str] = collections.Counter()
    mod_lines: dict[str, int] = {}
    mod_is_stmt: set[str] = set()
    mod_is_glue: set[str] = set()
    mod_has_dump: set[str] = set()
    decl_name_counts: collections.Counter[str] = collections.Counter()
    decl_stem_counts: collections.Counter[str] = collections.Counter()
    file_decl_buckets: collections.Counter[str] = collections.Counter()
    proof_len_buckets: collections.Counter[str] = collections.Counter()
    mod_list: list[str] = []

    # First pass: collect universe of internal modules for exact in-degree accounting
    mod_files: list[tuple[str, Path]] = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if not fn.endswith(".lean"):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(root_dir).with_suffix("")
            mod = (prefix + "." if prefix else "") + ".".join(rel.parts)
            if allowed_mods is not None and mod not in allowed_mods:
                continue
            mod_files.append((mod, fp))
    universe = set(m for m, _ in mod_files)

    for mod, fp in mod_files:
        mod_list.append(mod)
        stats["files"] += 1
        if fp.name.endswith("Statement.lean"):
            mod_is_stmt.add(mod)
            stats["statement_files"] += 1

        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        n_lines = len(lines)
        mod_lines[mod] = n_lines
        stats["total_lines"] += n_lines

        if RE_GLUE.search(text):
            mod_is_glue.add(mod)
            stats["glue_files"] += 1
        if RE_DUMP_STRICT.search(text):
            mod_has_dump.add(mod)
            stats["dump_files_strict"] += 1

        n_decls = 0
        n_imp_internal = 0
        has_imp_mathlib_root = False
        cur_decl_kind: str | None = None
        cur_decl_start = 0

        for idx, line in enumerate(lines):
            s = line.strip()
            if not s:
                stats["blank_lines"] += 1
                continue
            if RE_DOC.match(line):
                stats["docstrings"] += 1
            if s.startswith("--") or s.startswith("/-"):
                stats["comment_lines"] += 1
                continue
            m_imp = RE_IMPORT.match(line)
            if m_imp:
                target = m_imp.group(1)
                if target == "Mathlib":
                    has_imp_mathlib_root = True
                if target in universe and (
                    internal_prefix is None or target.startswith(internal_prefix)
                ):
                    in_deg[target] += 1
                    n_imp_internal += 1
                continue

            if RE_SIMP_ATTR.search(line):
                stats["simp_attrs"] += 1
            if RE_EXT_ATTR.search(line):
                stats["ext_attrs"] += 1
            if RE_HAVE.match(line):
                stats["have_lines"] += 1
            if RE_CALC.match(line):
                stats["calc_lines"] += 1
            if RE_DEF_ANY.match(line):
                stats["def_lines"] += 1
                if RE_DEF_PROP.match(line):
                    stats["def_prop_lines"] += 1

            m_d = RE_DECL.match(line)
            if m_d:
                if cur_decl_kind in ("theorem", "lemma"):
                    _bucket_len(proof_len_buckets, idx - cur_decl_start)
                kind, name = m_d.group(1), m_d.group(2)
                cur_decl_kind = kind
                cur_decl_start = idx
                decl_kinds[kind] += 1
                n_decls += 1
                if kind in ("theorem", "lemma"):
                    decl_name_counts[name] += 1
                    stem = re.sub(
                        r"(_?\d+|'+|_aux\d*|_helper\d*|_step\d*|_part\d*|_case\d*)$",
                        "",
                        name,
                        flags=re.I,
                    )
                    decl_stem_counts[stem] += 1

        if cur_decl_kind in ("theorem", "lemma"):
            _bucket_len(proof_len_buckets, n_lines - cur_decl_start)

        out_deg[mod] = n_imp_internal
        if has_imp_mathlib_root:
            stats["import_mathlib_root"] += 1
        if n_decls == 0:
            file_decl_buckets["0"] += 1
        elif n_decls == 1:
            file_decl_buckets["1"] += 1
        elif n_decls <= 5:
            file_decl_buckets["2-5"] += 1
        elif n_decls <= 20:
            file_decl_buckets["6-20"] += 1
        else:
            file_decl_buckets["21+"] += 1

    non_stmt_mods = [m for m in mod_list if m not in mod_is_stmt and m not in mod_is_glue]
    lines_stmt = sum(mod_lines[m] for m in mod_list if m in mod_is_stmt or m in mod_is_glue)
    lines_dump_non_stmt = sum(mod_lines[m] for m in non_stmt_mods if m in mod_has_dump)
    lines_clean_non_stmt = sum(mod_lines[m] for m in non_stmt_mods if m not in mod_has_dump)

    numbered_stems = sorted(
        ((k, v) for k, v in decl_stem_counts.items() if v >= 3 and len(k) >= 6),
        key=lambda x: -x[1],
    )
    dup_exact_names = sorted(
        ((k, v) for k, v in decl_name_counts.items() if v >= 2),
        key=lambda x: -x[1],
    )

    return {
        "stats": dict(stats),
        "decl_kinds": dict(decl_kinds),
        "file_decl_buckets": dict(file_decl_buckets),
        "proof_len_buckets": dict(proof_len_buckets),
        "indeg_all": _indeg_summary(mod_list, in_deg),
        "indeg_non_stmt": _indeg_summary(non_stmt_mods, in_deg),
        "lines_breakdown": {
            "total": stats["total_lines"],
            "stmt_or_glue_files": lines_stmt,
            "non_stmt_with_dump_strict": lines_dump_non_stmt,
            "non_stmt_clean_strict": lines_clean_non_stmt,
        },
        "dup_exact_name_total_extra": sum(v - 1 for _, v in dup_exact_names),
        "top_dup_exact_names": dup_exact_names[:20],
        "multi_stem_groups_ge3": len(numbered_stems),
        "multi_stem_total_decls_ge3": sum(v for _, v in numbered_stems),
        "top_stems": numbered_stems[:20],
    }


def _bucket_len(counter: collections.Counter[str], plen: int) -> None:
    if plen <= 5:
        counter["1-5"] += 1
    elif plen <= 20:
        counter["6-20"] += 1
    elif plen <= 50:
        counter["21-50"] += 1
    elif plen <= 150:
        counter["51-150"] += 1
    elif plen <= 500:
        counter["151-500"] += 1
    else:
        counter["500+"] += 1


def _indeg_summary(mods: list[str], in_deg: collections.Counter[str]) -> dict:
    c: collections.Counter[str] = collections.Counter()
    vals = []
    for m in mods:
        d = in_deg.get(m, 0)
        vals.append(d)
        if d == 0:
            c["0"] += 1
        elif d == 1:
            c["1"] += 1
        elif d == 2:
            c["2"] += 1
        elif d <= 5:
            c["3-5"] += 1
        elif d <= 20:
            c["6-20"] += 1
        else:
            c["21+"] += 1
    vals.sort()
    n = len(vals) or 1
    return {
        "count": len(vals),
        "buckets": dict(c),
        "pct_eq_1": round(100 * c["1"] / n, 2),
        "pct_le_1": round(100 * (c["0"] + c["1"]) / n, 2),
        "pct_le_2": round(100 * (c["0"] + c["1"] + c["2"]) / n, 2),
        "median": vals[n // 2],
        "p90": vals[int(n * 0.9)],
        "p99": vals[int(n * 0.99)],
        "mean": round(sum(vals) / n, 2),
        "max": vals[-1] if vals else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rh-src", type=Path, required=True, help="Path to lean/src of RH archive")
    ap.add_argument("--cone", type=Path, required=True, help="Path to cut-modules.txt.xz")
    ap.add_argument("--mathlib", type=Path, required=True, help="Path to Mathlib/ directory")
    ap.add_argument("--out", type=Path, required=True, help="Output JSON path")
    args = ap.parse_args()

    with lzma.open(args.cone, "rt") as f:
        cone_mods = {line.strip() for line in f if line.strip()}

    t0 = time.time()
    ml = analyze_corpus(args.mathlib, allowed_mods=None, prefix="Mathlib", internal_prefix="Mathlib.")
    t1 = time.time()
    rh = analyze_corpus(args.rh_src, allowed_mods=cone_mods, prefix="", internal_prefix=None)
    t2 = time.time()

    payload = {
        "timing_sec": {"mathlib": round(t1 - t0, 1), "rh_in_cone": round(t2 - t1, 1)},
        "mathlib": ml,
        "rh_in_cone": rh,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.out} (Mathlib {t1 - t0:.1f}s, RH {t2 - t1:.1f}s)")


if __name__ == "__main__":
    main()
