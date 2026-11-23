"""Extract the pinned target and its RH dependencies from a local upstream Git clone."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REV = "c592e91eb8f41bfd149227c09460fae0c17bf3c5"
TARGET = "Formalism.PolynomialDimension.MultinomialDepth.MonoCount"
HERE = Path(__file__).resolve().parent


def prepare(repo, work):
    modules = []

    def extract(module):
        if module in modules:
            return
        path = Path(*module.split(".")).with_suffix(".lean")
        source = subprocess.check_output(["git", "-C", repo, "show", f"{REV}:src/{path.as_posix()}"])
        for child in re.findall(rb"^(?:public )?import (\S+)", source, re.M):
            if not child.startswith(b"Mathlib"):
                extract(child.decode())
        out = work / ("original" if module == TARGET else "dependencies") / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(source)
        modules.append(module)

    extract(TARGET)
    (work / "modules.json").write_text(json.dumps(modules, indent=2) + "\n")
    expected = {
        "A": "6f16f1f08e1f6e723138f816136693418220c4a21ee5926c1239a86d43c18aaa",
        "B": "4a9039fab1e53e89bd09da314443111a8da310f3d5993b841f4c29f5bf1dbba8",
    }
    for arm, parent in [("A", "original"), ("B", "A")]:
        patch = HERE / f"{arm}.patch"
        path = Path(*TARGET.split(".")).with_suffix(".lean")
        dest = work / arm / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((work / parent / path).read_bytes())
        subprocess.run(["git", "apply", "--whitespace=error", str(patch)], cwd=work / arm, check=True)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != expected[arm]:
            raise RuntimeError(f"Arm {arm} failed its source digest check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    prepare(args.repo.resolve(), args.work.resolve())
