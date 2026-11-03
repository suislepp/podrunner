"""Downloads the packages a script needs, built for the pod, into pod/wheels/<set>/. run.py calls this.

pip picks dependencies for the machine it runs on, so afterwards this checks
them for the pod and downloads whatever pip skipped.
"""
import email.parser
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
except ImportError:
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.utils import canonicalize_name

CACHE = Path(__file__).resolve().parent / "wheels"

# Must match pod.yaml's image. Update both together if the image changes.
PYTHON_VERSION = "3.11"

POD = {
    "sys_platform": "linux",
    "platform_system": "Linux",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "python_version": PYTHON_VERSION,
    "python_full_version": PYTHON_VERSION + ".0",
}
MANYLINUX_UP_TO_GLIBC_2_28 = [f"manylinux_2_{m}_x86_64" for m in range(28, 4, -1)] + [
    "manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]


def applies_in_pod(marker, extras=()):
    return marker is None or any(marker.evaluate({**POD, "extra": e}) for e in ["", *extras])


def missing_in_pod(folder, deps):
    deps_of = {}
    for whl in folder.glob("*.whl"):
        with zipfile.ZipFile(whl) as z:
            meta = next(n for n in z.namelist() if re.fullmatch(r"[^/]+\.dist-info/METADATA", n))
            msg = email.parser.HeaderParser().parsestr(z.read(meta).decode())
        deps_of[canonicalize_name(msg["Name"])] = msg.get_all("Requires-Dist") or []

    todo = [r for r in map(Requirement, deps) if applies_in_pod(r.marker)]
    missing, seen = set(), set()
    while todo:
        req = todo.pop()
        name = canonicalize_name(req.name)
        if (name, frozenset(req.extras)) in seen:
            continue
        seen.add((name, frozenset(req.extras)))
        if name not in deps_of:
            req.marker = None
            missing.add(str(req))
            continue
        todo += [d for d in map(Requirement, deps_of[name]) if applies_in_pod(d.marker, req.extras)]
    return missing


def pip_download(folder, requirements):
    for old in folder.glob("*.whl"):
        old.unlink()
    cmd = [sys.executable, "-m", "pip", "download", "-q", "--disable-pip-version-check",
           "--python-version", PYTHON_VERSION, "--only-binary=:all:", "-d", str(folder)]
    for tag in MANYLINUX_UP_TO_GLIBC_2_28:
        cmd += ["--platform", tag]
    if subprocess.run(cmd + requirements).returncode != 0:
        sys.exit("error: pip download failed")


def wheels_for(deps):
    """A folder with wheels for these requirements plus a requirements.txt; downloads them the first time."""
    key = hashlib.sha256("\n".join(sorted(deps) + [PYTHON_VERSION]).encode()).hexdigest()[:12]
    folder = CACHE / key
    if (folder / "requirements.txt").exists():
        return folder

    print(f"==> Downloading packages for the pod: {', '.join(deps)}")
    folder.mkdir(parents=True, exist_ok=True)
    extra = set()
    while True:
        pip_download(folder, deps + sorted(extra))
        missing = missing_in_pod(folder, deps)
        if not missing:
            break
        if missing <= extra:
            sys.exit(f"error: pip didn't download {', '.join(sorted(missing))}")
        print(f"    pip skipped what the pod needs: {', '.join(sorted(missing - extra))}. Downloading again with them.")
        extra |= missing
    (folder / "requirements.txt").write_text("\n".join(deps) + "\n")
    return folder
