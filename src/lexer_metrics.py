"""Deterministic Lean 4 source metrics and static hygiene checks for ProofDistill-Bench."""
import re
from pathlib import Path

FORBIDDEN_RE = re.compile(
    r"\b(sorry|admit|axiom|native_decide|implemented_by|extern|unsafe|skipKernelTC)\b"
    r"|@\[[^\]]*\b(implemented_by|extern)\b"
    r"|set_option\s+debug\."
)

TOKEN_RE = re.compile(
    r'"(?:\\.|[^"\\])*"'          # string literals
    r"|[A-Za-z_][A-Za-z0-9_'.]*"  # identifiers / dotted names
    r"|\d+(?:\.\d+)?"             # numeric literals
    r"|:=|=>|->|→|←|↔|≤|≥|≠|∀|∃|λ|⟨|⟩|·|\.\.|[^\sA-Za-z0-9_]"
)


def strip_lean_comments(text: str) -> str:
    """Strip Lean 4 nested /- ... -/ block comments and -- line comments, preserving strings."""
    out = []
    i = 0
    n = len(text)
    block_depth = 0
    in_str = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(nxt)
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
        elif block_depth > 0:
            if ch == "/" and nxt == "-":
                block_depth += 1
                i += 2
            elif ch == "-" and nxt == "/":
                block_depth -= 1
                i += 2
            else:
                if ch == "\n":
                    out.append("\n")
                i += 1
        else:
            if ch == '"':
                in_str = True
                out.append(ch)
                i += 1
            elif ch == "/" and nxt == "-":
                block_depth = 1
                i += 2
            elif ch == "-" and nxt == "-":
                while i < n and text[i] != "\n":
                    i += 1
            else:
                out.append(ch)
                i += 1
    return "".join(out)


def analyze_source(text: str) -> dict:
    cleaned = strip_lean_comments(text)
    lines = text.splitlines()
    nonblank_code_lines = [ln for ln in cleaned.splitlines() if ln.strip()]
    tokens = TOKEN_RE.findall(cleaned)
    forbidden = sorted(set(m.group(0) for m in FORBIDDEN_RE.finditer(cleaned)))
    return {
        "raw_lines": len(lines),
        "code_lines": len(nonblank_code_lines),
        "norm_tokens": len(tokens),
        "chars_no_comments": sum(len(ln.strip()) for ln in nonblank_code_lines),
        "forbidden_hits": forbidden,
    }


def check_file(path: Path) -> dict:
    return analyze_source(path.read_text(encoding="utf-8"))
