"""Downloads the packages a script needs, built for the pod, into pod/wheels/<set>/. run.py calls this."""
import hashlib
import subprocess
import sys
from pathlib import Path

CACHE = Path(__file__).resolve().parent / "wheels"
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
MANYLINUX_UP_TO_GLIBC_2_28 = [f"manylinux_2_{m}_x86_64" for m in range(28, 4, -1)] + [
    "manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]


def wheels_for(deps):
    """A folder with wheels for these requirements plus a requirements.txt; downloads them the first time."""
    key = hashlib.sha256("\n".join(sorted(deps) + [PYTHON_VERSION]).encode()).hexdigest()[:12]
    folder = CACHE / key
    if (folder / "requirements.txt").exists():
        return folder

    print(f"==> Downloading packages for the pod: {', '.join(deps)}")
    folder.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "download", "-q", "--disable-pip-version-check",
           "--python-version", PYTHON_VERSION, "--only-binary=:all:", "-d", str(folder)]
    for tag in MANYLINUX_UP_TO_GLIBC_2_28:
        cmd += ["--platform", tag]
    if subprocess.run(cmd + deps).returncode != 0:
        sys.exit("error: pip download failed")
    (folder / "requirements.txt").write_text("\n".join(deps) + "\n")
    return folder
