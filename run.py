#!/usr/bin/env python3
"""Start a .py, .sh or .sql file in a new pod, then follow it with watch.py.

  python run.py <file> -n NAMESPACE [--env NAME=value] [--ask NAME] [--secret NAME=secret/key]
                [--dry-run] [-- args for the script]
"""
import argparse
import ast
import getpass
import json
import os
import random
import re
import shlex
import string
import subprocess
import sys
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
DEPENDENCIES_LIST = r"(?ms)^dependencies\s*=\s*(\[.*?\])\s*$"


def dependencies(file):
    if file.suffix == ".sql":
        return SQL_DEPENDENCIES
    block = re.search(SCRIPT_BLOCK, file.read_text(encoding="utf-8")) if file.suffix == ".py" else None
    if not block:
        return []
    content = "".join(line[2:] if line.startswith("# ") else line[1:]
                      for line in block["content"].splitlines(keepends=True))
    found = re.search(DEPENDENCIES_LIST, content)
    return ast.literal_eval(found[1]) if found else []


def env_entries(envs, secrets):
    entries = []
    for e in envs:
        name, eq, value = e.partition("=")
        if not (name and eq):
            sys.exit(f"error: --env {e} should look like NAME=value")
        entries.append(f"        - name: {json.dumps(name)}\n"
                       f"          value: {json.dumps(value)}")
    for s in secrets:
        name, _, ref = s.partition("=")
        secret, _, key = ref.partition("/")
        if not (name and secret and key):
            sys.exit(f"error: --secret {s} should look like NAME=secret-name/key")
        entries.append(f"        - name: {json.dumps(name)}\n"
                       f"          valueFrom:\n"
                       f"            secretKeyRef:\n"
                       f"              name: {json.dumps(secret)}\n"
                       f"              key: {json.dumps(key)}")
    return "\n".join(entries)


def main():
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    p = argparse.ArgumentParser(description="Start a .py, .sh or .sql file in a new pod, then follow it with watch.py.")
    p.add_argument("file")
    p.add_argument("-n", "--namespace", required=True)
    p.add_argument("--env", action="append", default=[], metavar="NAME=value",
                   help="an env var with a value you type; repeatable")
    p.add_argument("--ask", action="append", default=[], metavar="NAME",
                   help="an env var whose value you're asked for, hidden, when the run starts; repeatable")
    p.add_argument("--secret", action="append", default=[], metavar="NAME=secret/key",
                   help="an env var taken from a key of an existing k8s Secret; repeatable")
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
    manifest = ((REPO / "pod" / "pod.yaml").read_text()
                .replace("__POD_NAME__", pod)
                .replace("__OWNER__", user)
                .replace("__ENV__", env_entries(a.env, a.secret))
                .replace("__COMMAND__", command))
    deps = dependencies(file)
    if a.dry_run:
        print(manifest)
        print(f"# packages: {', '.join(deps) or 'none'}")
        print(f"# asked when it runs: {', '.join(a.ask) or 'nothing'}")
        return 0

    asked = {name: getpass.getpass(f"{name}: ") for name in a.ask}
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
        if asked:
            kubectl(ns, "exec", "-i", pod, "--", "sh", "-c", "umask 077; cat > /tmp/env", text=True,
                    input="".join(f"export {name}={shlex.quote(value)}\n" for name, value in asked.items()))
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
    print(f"    To follow it again later: python watch.py {pod} -n {ns}")
    return watch(pod, ns)


if __name__ == "__main__":
    sys.exit(main())
