#!/usr/bin/env python3
"""Start a .py, .sh or .sql file in a new pod, then follow it with watch.py.

  python run.py <file> -n NAMESPACE [--secret NAME] [--dry-run] [-- args for the script]
"""
import argparse
import os
import random
import re
import shlex
import string
import subprocess
import sys
import tomllib
from pathlib import Path

from pod.wheels import wheels_for
from watch import kubectl, watch

REPO = Path(__file__).resolve().parent
COMMANDS = {
    ".py": ["python"],
    ".sh": ["bash"],
    ".sql": ["python", "/tmp/sql_runner.py"],
}
SQL_DEPENDENCIES = ["psycopg[binary]", "sqlparse"]
SCRIPT_BLOCK = r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$"


def dependencies(file):
    if file.suffix == ".sql":
        return SQL_DEPENDENCIES
    block = re.search(SCRIPT_BLOCK, file.read_text(encoding="utf-8")) if file.suffix == ".py" else None
    if not block:
        return []
    toml = "".join(line[2:] if line.startswith("# ") else line[1:]
                   for line in block["content"].splitlines(keepends=True))
    return tomllib.loads(toml).get("dependencies", [])


def main():
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    p = argparse.ArgumentParser(description="Start a .py, .sh or .sql file in a new pod, then follow it with watch.py.")
    p.add_argument("file")
    p.add_argument("-n", "--namespace", required=True)
    p.add_argument("--secret", action="append", default=[],
                   help="k8s Secret whose keys become env vars, e.g. a database's DB_HOST, DB_USER, DB_PASSWORD; repeatable")
    p.add_argument("--dry-run", action="store_true", help="print the pod manifest and stop")
    a = p.parse_args(argv[:split])
    ns = a.namespace

    file = Path(a.file).resolve()
    if not file.is_file() or file.suffix not in COMMANDS:
        sys.exit(f"error: {a.file} is not a .py, .sh or .sql file")

    user = (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown").lower()
    user = "".join(c if c.isalnum() else "-" for c in user)[:20].strip("-") or "unknown"
    pod = f"podrunner-{user}-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    command = shlex.join(COMMANDS[file.suffix] + [f"/work/{file.name}"] + argv[split + 1:])
    secrets = "".join(f"\n        - secretRef:\n            name: {s}" for s in a.secret)
    manifest = ((REPO / "pod" / "pod.yaml").read_text()
                .replace("__POD_NAME__", pod)
                .replace("__OWNER__", user)
                .replace("__ENV_FROM__", f"      envFrom:{secrets}" if secrets else "")
                .replace("__COMMAND__", command))
    deps = dependencies(file)
    if a.dry_run:
        print(manifest)
        print(f"# packages: {', '.join(deps) or 'none'}")
        return 0

    wheels = wheels_for(deps) if deps else None
    context = kubectl(None, "config", "current-context", capture_output=True, text=True).stdout.strip()
    print(f"==> Cluster {context}, namespace {ns}")

    kubectl(ns, "delete", "pod", "-l", f"app=podrunner,owner={user}",
            "--field-selector=status.phase!=Running,status.phase!=Pending",
            check=False, stderr=subprocess.DEVNULL)

    print(f"==> Creating pod {pod}")
    kubectl(ns, "apply", "-f", "-", input=manifest, text=True)
    try:
        kubectl(ns, "wait", "--for=condition=Ready", f"pod/{pod}", "--timeout=300s")
        if wheels:
            print(f"==> Installing {', '.join(deps)}")
            kubectl(ns, "cp", wheels.name, f"{pod}:/tmp/wheels", cwd=wheels.parent)
            kubectl(ns, "exec", pod, "--", "pip", "install", "-q", "--root-user-action=ignore",
                    "--disable-pip-version-check", "--no-index", "--find-links=/tmp/wheels",
                    "-r", "/tmp/wheels/requirements.txt")
        if file.suffix == ".sql":
            kubectl(ns, "cp", "sql_runner.py", f"{pod}:/tmp/sql_runner.py", cwd=REPO / "pod")
        print(f"==> Copying {file.name}")
        kubectl(ns, "cp", file.name, f"{pod}:/work/{file.name}", cwd=file.parent)
        kubectl(ns, "exec", pod, "--", "touch", "/tmp/ready")
    except SystemExit:
        print("==> Setup failed. The pod's events:")
        kubectl(ns, "get", "events", f"--field-selector=involvedObject.name={pod}", check=False)
        print(f"==> Deleting {pod}, nothing was run.")
        kubectl(ns, "delete", "pod", pod, "--wait=false", check=False)
        raise

    print(f"==> Started: {command}")
    print("    It runs in the pod on its own: closing the laptop or losing the connection doesn't stop it.")
    return watch(pod, ns)


if __name__ == "__main__":
    sys.exit(main())
