#!/usr/bin/env python3
"""Spin up a pod, install deps from local wheels/, run a script, copy back artifacts."""

import argparse
import os
import random
import string
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def parse_args():
    argv = sys.argv[1:]
    if "--" in argv:
        i = argv.index("--")
        outer, inner = argv[:i], argv[i + 1:]
    else:
        outer, inner = argv, []

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kubeconfig", required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--script", help="Path to .py or .sh; omit for interactive shell")
    p.add_argument("--requirements", action="append", default=[], help="requirements.txt path; repeatable")
    p.add_argument("--secret", action="append", default=[], help="k8s Secret name (envFrom); repeatable")
    p.add_argument("--output", action="append", default=[],
                   help="Path under /work to copy back; repeatable")
    p.add_argument("--keep", action="store_true", help="Don't delete pod on success")
    p.add_argument("--dry-run", action="store_true", help="Print manifest and exit")
    a = p.parse_args(outer)
    a.inner_args = inner
    return a


def render_manifest(pod_name, namespace, owner, secrets):
    template = (REPO_ROOT / "pod.yaml").read_text()
    if secrets:
        block = ["      envFrom:"]
        for s in secrets:
            block.append("        - secretRef:")
            block.append(f"            name: {s}")
        env_from = "\n".join(block)
    else:
        env_from = ""
    return (template
            .replace("__POD_NAME__", pod_name)
            .replace("__NAMESPACE__", namespace)
            .replace("__OWNER__", owner)
            .replace("__ENV_FROM__", env_from))


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    a = parse_args()

    script = None
    interpreter = None
    if a.script:
        script = Path(a.script).resolve()
        if not script.exists():
            fail(f"script not found: {script}")
        if script.suffix not in (".py", ".sh"):
            fail(f"script must be .py or .sh, got {script.suffix}")
        interpreter = "python" if script.suffix == ".py" else "bash"

    requirements = []
    for path_str in a.requirements:
        path = Path(path_str).resolve()
        if not path.exists():
            fail(f"requirements file not found: {path}")
        requirements.append(path)
    wheels_dir = REPO_ROOT / "wheels"

    user_raw = (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown").lower()
    user = "".join(c if c.isalnum() else "-" for c in user_raw)[:20].strip("-") or "unknown"
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    pod_name = f"podrunner-{user}-{suffix}"

    manifest = render_manifest(pod_name, a.namespace, user, a.secret)

    if a.dry_run:
        print(manifest)
        return 0

    if requirements and not wheels_dir.exists():
        fail(f"wheels/ not found at {wheels_dir}")

    def k(args, err=None, **kw):
        r = subprocess.run(
            ["kubectl", f"--kubeconfig={a.kubeconfig}", f"--namespace={a.namespace}"] + args,
            **kw,
        )
        if err and r.returncode != 0:
            fail(err)
        return r

    pod_created = False
    success = False
    script_exit = 1

    try:
        print(f"==> Creating pod {pod_name} in {a.namespace}")
        k(["apply", "-f", "-"], err="kubectl apply failed", input=manifest, text=True)
        pod_created = True

        print(f"==> Waiting for pod ready")
        k(["wait", "--for=condition=Ready", f"pod/{pod_name}", "--timeout=300s"],
          err="pod did not become ready")

        k(["exec", pod_name, "--", "which", "tar"],
          err="image is missing 'tar' — kubectl cp won't work",
          capture_output=True, text=True)

        if requirements:
            print(f"==> Copying wheels")
            k(["cp", str(wheels_dir), f"{pod_name}:/"], err="failed to copy wheels/ to pod")
            for req in requirements:
                print(f"==> Installing {req.name}")
                dest = f"/work/{req.name}"
                k(["cp", str(req), f"{pod_name}:{dest}"], err=f"failed to copy {req.name}")
                k(["exec", pod_name, "--", "pip", "install",
                   "--no-index", "--find-links=/wheels", "-r", dest],
                  err=f"pip install failed for {req.name}")

        if script:
            script_dest = f"/work/{script.name}"
            print(f"==> Copying {script.name}")
            k(["cp", str(script), f"{pod_name}:{script_dest}"], err="failed to copy script")

            print(f"==> Running: {interpreter} {script.name} {' '.join(a.inner_args)}")
            print("-" * 60)
            r = k(["exec", pod_name, "--", interpreter, script_dest] + a.inner_args)
        else:
            print(f"==> Opening interactive shell. Type 'exit' or Ctrl+D to leave.")
            print("-" * 60)
            r = k(["exec", "-it", pod_name, "--", "bash"])
        print("-" * 60)
        script_exit = r.returncode
        success = (script_exit == 0)

        if a.output:
            local_base = REPO_ROOT / "output" / pod_name
            local_base.mkdir(parents=True, exist_ok=True)
            for out_path in a.output:
                src = out_path if out_path.startswith("/") else f"/work/{out_path}"
                dst = local_base / out_path.lstrip("/")
                dst.parent.mkdir(parents=True, exist_ok=True)
                print(f"==> Copying back {src} -> {dst}")
                r = k(["cp", f"{pod_name}:{src}", str(dst)])
                if r.returncode != 0:
                    print(f"warning: failed to copy back {src}")

        if success and not a.keep:
            print(f"==> Deleting pod {pod_name}")
            k(["delete", "pod", pod_name, "--wait=false"])
            pod_created = False

    finally:
        if pod_created and not success:
            print(f"\nPod kept alive for inspection.")
            print(f"  Inspect: kubectl --kubeconfig={a.kubeconfig} -n {a.namespace} exec -it {pod_name} -- bash")
            print(f"  Delete:  kubectl --kubeconfig={a.kubeconfig} -n {a.namespace} delete pod {pod_name}")

    if success:
        print("\nDone.")

    return 0 if success else script_exit


if __name__ == "__main__":
    sys.exit(main())
