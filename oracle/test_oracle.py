"""Run with Lean 4.36 and its pinned Mathlib in LEAN_PATH. Uses a fresh build directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
HEADER = "module\n@[expose] public section\nstructure Point where\n  x : Nat\n"
BODY = "def weight : Nat := 7\ntheorem stable (n : Nat) : n = n := rfl\n"
CASES = {
    "sorry": (BODY.replace(":= rfl", ":= by sorry"), "Forbidden axiom sorryAx"),
    "type": (BODY.replace("n = n", "n ≤ n").replace(":= rfl", ":= Nat.le_refl n"), "Kernel type mismatch"),
    "value": (BODY.replace(":= 7", ":= 8"), "Kernel value mismatch"),
    "missing": (BODY.split("theorem")[0], "Export mismatch; missing=#[stable]"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work) as temp:
        root = Path(temp).resolve()
        env = dict(os.environ, LEAN_NUM_THREADS="1",
                   LEAN_PATH=os.pathsep.join([temp, os.environ.get("LEAN_PATH", "")]))

        def run(argv, reason=None):
            p = subprocess.run(argv, cwd=root, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, encoding="utf-8")
            if reason is None and p.returncode:
                raise RuntimeError(p.stdout)
            if reason and (p.returncode == 0 or reason not in p.stdout):
                raise RuntimeError(f"expected rejection for {reason}: {p.stdout}")
            return p.stdout.strip()

        def build(folder, name, source, allow_sorry=False):
            location = root / folder
            location.mkdir(exist_ok=True)
            (location / (name + ".lean")).write_text(source, encoding="utf-8", newline="\n")
            flags = [] if allow_sorry else ["-DwarningAsError=true"]
            run(["lean", "-j1", *flags, "--root=" + folder, "-o", str(location / (name + ".olean")),
                 str(location / (name + ".lean"))])

        def audit(module, reason=None):
            return run(["lean", "-j1", "--run", str(HERE / "OracleAudit.lean"),
                        "--same", str(root / "reference"), str(root / "candidate"), module], reason)

        receipt = dict(lean=run(["lean", "--version"]), oracle_sha256=hashlib.sha256(
            (HERE / "OracleAudit.lean").read_bytes()).hexdigest(), cases={})
        build("reference", "Sample", HEADER + BODY)
        for key, (src, reason) in CASES.items():
            build("candidate", "Sample", HEADER + src, key == "sorry")
            receipt["cases"][key] = audit("Sample", reason)
        # Full, depth-zero module at RH c592e91eb8, including its original binder names.
        src = (HERE / "fixtures/ExistsBasisIn.lean").read_text(encoding="utf-8")
        build("reference", "ExistsBasisIn", src)
        build("candidate", "ExistsBasisIn", src)
        receipt["reference_control"] = audit("ExistsBasisIn")
        old = src[src.index("  have htop"):src.index("  let e")]
        new = src.replace(old, "  let B := Module.Basis.mk hli (by rw [Subtype.range_coe, hspan, hS])\n")
        assert new != src
        build("candidate", "ExistsBasisIn", new)
        receipt["cases"]["real_refactor"] = audit("ExistsBasisIn")
        env["LEAN_PATH"] = str(root / "candidate") + os.pathsep + env["LEAN_PATH"]
        receipt["kernel_replay"] = run(["leanchecker", "-v", "ExistsBasisIn"])
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
