"""Reproduce the fixed rotation, heartbeats, equivalence checks, and kernel replays."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from prepare import HERE, TARGET, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="RH Git checkout containing the pinned commit")
    parser.add_argument("work", type=Path, help="fresh directory outside a Git checkout")
    args = parser.parse_args()
    work = args.work.resolve()
    if work.exists() and any(work.iterdir()):
        parser.error("choose an empty work directory so builds cannot reuse an earlier target")
    prepare(args.upstream.resolve(), work)
    version = subprocess.check_output(["lean", "--version"], text=True)
    if "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9" not in version:
        raise RuntimeError("this experiment requires the pinned Lean 4.36.0 release")

    def measure(arm, *opts):
        subprocess.run([sys.executable, HERE / "measure.py", arm, *opts], cwd=work, check=True)

    measure("dependencies")
    measure("original", "--trial", "warmup")
    arms = ["original", "A", "B"]
    for i in range(3):
        for arm in arms[i:] + arms[:i]:
            measure(arm, "--trial", str(i + 1))
    for arm in arms:
        measure(arm, "--heartbeats")
    for arm in arms:
        obj = work / ("objects-" + arm)
        if arm != "original":
            subprocess.run(["lean", "-j1", "--run", HERE.parents[1] / "oracle/OracleAudit.lean",
                            "--same", work / "objects-original", obj, TARGET], check=True)
        env = dict(os.environ, LEAN_NUM_THREADS="1", LEAN_PATH=str(obj) + os.pathsep + os.environ["LEAN_PATH"])
        subprocess.run(["leanchecker", "-v", TARGET], cwd=work, env=env, check=True)


if __name__ == "__main__":
    main()
