#!/usr/bin/env python3
"""Follow a podrunner pod until its script finishes, copy the pod's /work to output/<pod>/, delete the pod.

  python watch.py <pod> -n NAMESPACE
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
FINISHED = "podrunner: finished, exit code "


def kubectl_cmd(ns, *args):
    return ["kubectl", *(["-n", ns] if ns else []), *args]


def kubectl(ns, *args, check=True, **kw):
    try:
        r = subprocess.run(kubectl_cmd(ns, *args), **kw)
    except FileNotFoundError:
        sys.exit("error: kubectl not found, install it or add it to PATH")
    if check and r.returncode != 0:
        sys.exit(f"error: kubectl {args[0]} failed")
    return r


def watch(pod, ns):
    again = f"python watch.py {pod} -n {ns}"
    print(f"==> Following {pod}. Ctrl+C stops following, not the script.")
    exit_code = None
    tail = "-1"
    while exit_code is None:
        logs = subprocess.Popen(kubectl_cmd(ns, "logs", "-f", f"--tail={tail}", pod), stdout=subprocess.PIPE, text=True)
        try:
            for line in logs.stdout:
                print(line, end="")
                if line.startswith(FINISHED):
                    exit_code = int(line[len(FINISHED):])
                    break
        except KeyboardInterrupt:
            logs.terminate()
            print(f"\n==> Stopped following. The script keeps running in the pod. Follow it again: {again}")
            return 1
        logs.terminate()
        if exit_code is None:
            phase = kubectl(ns, "get", "pod", pod, "-o", "jsonpath={.status.phase}",
                            capture_output=True, text=True, check=False).stdout
            if phase != "Running":
                print(f"==> {pod} is {phase or 'gone'}, nothing left to follow.")
                return 1
            print("==> Log stream dropped, reconnecting (the last lines may repeat).")
            tail = "5"

    print(f"==> Copying the pod's /work (the script, log.txt, files it wrote) to output/{pod}/")
    (REPO / "output").mkdir(exist_ok=True)
    r = kubectl(ns, "cp", f"{pod}:/work", f"output/{pod}", cwd=REPO, check=False)
    if r.returncode != 0 or not (REPO / "output" / pod / "log.txt").exists():
        print("==> Copying /work failed.")
        exit_code = exit_code or 1

    if exit_code == 0:
        print(f"==> Deleting {pod}")
        kubectl(ns, "delete", "pod", pod, "--wait=false")
        print("\nDone.")
    else:
        print(f"\n==> Not deleting {pod} (exit code {exit_code}). It stops by itself 24 h after the script ended.")
        print(f"    Look inside: kubectl -n {ns} exec -it {pod} -- bash")
        print(f"    Copy /work again: {again}")
        print(f"    Delete now:  kubectl -n {ns} delete pod {pod}")
    return exit_code


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Follow a podrunner pod, copy its /work back, delete the pod.")
    p.add_argument("pod")
    p.add_argument("-n", "--namespace", required=True)
    a = p.parse_args()
    sys.exit(watch(a.pod, a.namespace))
