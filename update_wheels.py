#!/usr/bin/env python3
"""Refresh wheels/ from all requirements/*.txt files.

Run this any time you add, change, or remove a Python dependency. Wipes the
existing wheels/ contents and re-downloads everything based on the current
requirements files — so the wheelhouse exactly matches what's declared, with
no leftovers from removed packages or stale versions.

Requires pip + network access to PyPI (or your internal mirror) on the machine
running this script. The pods themselves never reach PyPI — that's the point.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
WHEELS_DIR = REPO_ROOT / "wheels"
REQ_DIR = REPO_ROOT / "requirements"

# Must match pod.yaml's image. Update both together if the image changes.
PYTHON_VERSION = "3.11"
PLATFORM = "manylinux2014_x86_64"


def main():
    if not REQ_DIR.exists():
        sys.exit(f"error: {REQ_DIR} not found")

    req_files = sorted(REQ_DIR.glob("*.txt"))
    if not req_files:
        sys.exit(f"error: no .txt files in {REQ_DIR}")

    WHEELS_DIR.mkdir(exist_ok=True)
    for old in WHEELS_DIR.glob("*.whl"):
        old.unlink()

    print(f"Refreshing wheels/ from {len(req_files)} requirements file(s):")
    for f in req_files:
        print(f"  - {f.relative_to(REPO_ROOT)}")
    print()

    cmd = [
        sys.executable, "-m", "pip", "download",
        "--platform", PLATFORM,
        "--python-version", PYTHON_VERSION,
        "--only-binary=:all:",
        "-d", str(WHEELS_DIR),
    ]
    for f in req_files:
        cmd.extend(["-r", str(f)])

    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"error: pip download failed (exit {r.returncode})")

    wheels = sorted(WHEELS_DIR.glob("*.whl"))
    print(f"\n{len(wheels)} wheels now in wheels/. Commit wheels/ and requirements/ when done.")


if __name__ == "__main__":
    main()
