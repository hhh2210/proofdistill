"""Serial Lean 4.36 measurements. Run from the prepared directory with LEAN_PATH set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

FLAGS = ["-j1", "--tstack=400000", "-DautoImplicit=false", "-DrelaxedAutoImplicit=false",
         "-DmaxSynthPendingDepth=3", "-Dpp.unicode.fun=true", "-DmaxHeartbeats=4000000"]
DECL = re.compile(r"^(?:/--(?:(?!-/)[\s\S])*?-/\n)?(?:(?:private|noncomputable) )*(?:theorem|lemma|def|instance) ", re.M)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=["dependencies", "original", "A", "B"])
    parser.add_argument("--heartbeats", action="store_true")
    parser.add_argument("--trial", default="1")
    args = parser.parse_args()
    root = Path.cwd()
    modules = json.loads((root / "modules.json").read_text())
    env = dict(os.environ, LEAN_NUM_THREADS="1", LEAN_PATH=os.pathsep.join(
        [str(root / "obj"), os.environ["LEAN_PATH"]]))
    targets = modules[:-1] if args.arm == "dependencies" else modules[-1:]
    objects = root / "obj"
    if args.arm != "dependencies":
        objects = root / ("objects-" + args.arm)
        if not objects.exists():
            shutil.copytree(root / "obj", objects)
        env["LEAN_PATH"] = os.pathsep.join([str(objects), os.environ["LEAN_PATH"]])
    for module in targets:
        path = Path(*module.split(".")).with_suffix(".lean")
        source_dir = root / args.arm
        source = (source_dir / path).read_bytes()
        obj = objects / path.with_suffix(".olean")
        obj.parent.mkdir(exist_ok=True, parents=True)
        ilean = obj.with_suffix(".ilean")
        flags = [*FLAGS, "--root=."]
        if args.arm in {"A", "B"}:
            flags.append("-DwarningAsError=true")
        if args.heartbeats:
            text = source.decode()
            wrapped, count = DECL.subn(lambda m: "#count_heartbeats in\n" + m.group(), text)
            source_dir = root / "heartbeat" / args.arm
            (source_dir / path).parent.mkdir(exist_ok=True, parents=True)
            (source_dir / path).write_text(wrapped, encoding="utf-8", newline="\n")
        else:
            flags += ["-o", str(obj), "-i", str(ilean)]
        start = time.perf_counter()
        p = subprocess.run(["lean", *flags, str(path)], env=env, cwd=source_dir,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        seconds = time.perf_counter() - start
        output = p.stdout.decode("utf-8", errors="replace")
        print(output if p.returncode else f"{module} ({seconds:.2f}s)", flush=True)
        result_dir = root / "results" / args.arm
        result_dir.mkdir(parents=True, exist_ok=True)
        key = module.split(".")[-1] + ("-hb" if args.heartbeats else "") + "-" + args.trial
        (result_dir / (key + ".log")).write_bytes(p.stdout)
        p.check_returncode()
        row = dict(module=module, arm=args.arm, trial=args.trial, seconds=round(seconds, 3),
                   source_sha256=hashlib.sha256(source).hexdigest(), warnings=output.count("warning:"))
        if args.heartbeats:
            beats = [int(n) for n in re.findall(r"Used (\d+) heartbeats", output)]
            if len(beats) != count or not beats:
                raise RuntimeError(f"expected {count} command counts, got {len(beats)}")
            row.update(declarations=count, heartbeats=sum(beats))
        else:
            row.update(ilean_bytes=ilean.stat().st_size)
        print(json.dumps(row), flush=True)
        (result_dir / (key + ".json")).write_text(json.dumps(row, indent=2) + "\n")


if __name__ == "__main__":
    main()
