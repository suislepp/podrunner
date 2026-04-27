# podrunner

Spin up a fresh pod in your k8s cluster, install Python deps from local `wheels/`, run a script, copy back artifacts. For prod environments where pods can't reach PyPI.

## Requirements

- **Local**: Python 3.8+, `kubectl`, and a kubeconfig with network access to your cluster's API server.
- **Cluster**: permission in your target namespace to create / exec / delete pods and read referenced Secrets.
- **Container image**: must include `bash` and `tar`. The default `python:3.11-slim` has both.
- **For adding new packages**: pip on a machine that can reach PyPI or your internal mirror — only needed when populating `wheels/`. The pods themselves never reach PyPI, that's the point.

## Quickstart

Run all commands from the repo root.

```bash
python3 podrunner.py \
  --kubeconfig ~/.kube/config-prod \
  --namespace debug-tools \
  --script scripts/hello.py
```

With deps, secrets, and an output artifact:

```bash
python3 podrunner.py \
  --kubeconfig ~/.kube/config-prod \
  --namespace debug-tools \
  --script scripts/query_postgres.py \
  --requirements requirements/python_postgres.txt \
  --secret postgres-creds \
  --output results.csv \
  -- "SELECT count(*) FROM orders"
```

Pass args to the inner script after `--`:

```bash
python3 podrunner.py --kubeconfig ... --namespace ... --script scripts/query.py \
  -- --env=prod --query="SELECT count(*) FROM orders"
```

Preview the rendered pod manifest without creating anything:

```bash
python3 podrunner.py ... --dry-run
```

Interactive shell (omit `--script`, get dropped into `bash` in the pod):

```bash
python3 podrunner.py \
  --kubeconfig ~/.kube/config-prod \
  --namespace debug-tools \
  --requirements requirements/python_postgres.txt \
  --secret postgres-creds
```

Type `exit` or Ctrl+D when done — same cleanup behavior as a script (delete on success, keep on failure, `--keep` to override).

## Repo layout

```
podrunner.py       # orchestrator
pod.yaml           # pod manifest template (edit to change image/resources)
README.md
wheels/            # committed .whl files
requirements/      # requirements files (e.g. python_postgres.txt)
scripts/           # python/shell scripts to run inside the pod
output/            # artifacts copied back from the pod — add to .gitignore
```

## Arguments

| Flag | Required | Description |
|---|---|---|
| `--kubeconfig` | yes | Path to your kubeconfig file |
| `--namespace` | yes | Namespace to launch the pod in |
| `--script` | no | Path to a `.py` or `.sh` script. **Omit for interactive shell** (drops you into `bash` in the pod). |
| `--requirements` | no | Path to a requirements file. Repeatable. |
| `--secret` | no | Name of a k8s Secret in the namespace. All keys become env vars via `envFrom`. Repeatable. |
| `--output` | no | Path inside the pod to copy back. Relative paths are under `/work`. Repeatable. |
| `--keep` | no | Don't delete the pod after a successful run |
| `--dry-run` | no | Print the rendered manifest and exit |
| `--` | no | Everything after is passed verbatim to the inner script |

## Adding a new package

The pod runs Linux x86_64 with Python 3.11. You **must** download wheels with matching flags or `pip install` will fail in the pod with "no matching distribution":

```bash
pip download \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --only-binary=:all: \
  -r requirements/<requirements-file>.txt \
  -d wheels/
```

Then commit both `wheels/` and the new file in `requirements/`. `pip download` pulls transitive deps too, so you don't need to chase them by hand.

For a single package without a requirements file:

```bash
pip download --platform manylinux2014_x86_64 --python-version 3.11 \
  --only-binary=:all: <package>==<version> -d wheels/
```

## Setting up secrets

`--secret <name>` mounts every key in the named k8s Secret as an env var via `envFrom`. **Key names in the Secret become env var names verbatim** — there is no remapping. If your script reads `os.environ["DB_PASSWORD"]`, the Secret must have a key called `DB_PASSWORD`.

Create secrets in Rancher (or with kubectl) before running:

```bash
kubectl --kubeconfig=... -n debug-tools create secret generic postgres-creds \
  --from-literal=DB_HOST=postgres.internal \
  --from-literal=DB_USER=svc_debug \
  --from-literal=DB_PASSWORD=<value>
```

## Output

The script's working directory inside the pod is `/work`. Anything it writes there can be copied back.

- `--output results.csv` → copies `/work/results.csv` to `output/<pod-name>/results.csv`
- `--output logs/` → copies the directory `/work/logs/`
- `--output /var/log/syslog` → absolute path, taken as-is

Output paths are copied back whether the script succeeded or failed (you usually want logs from a failed run). On failure they may not exist; you'll see a `warning: failed to copy back ...` and the run continues.

## Lifecycle

- **Success**: pod deleted, output copied back. `--keep` to override. (For interactive mode, success = bash exited cleanly via `exit` / Ctrl+D.)
- **Failure**: pod left alive for inspection. The tool prints exact `kubectl exec` and `kubectl delete` commands.

To bulk-clean orphaned pods you've left behind:

```bash
kubectl --kubeconfig=... -n <namespace> delete pod -l app=podrunner,owner=$USER
```

To list everyone's pods:

```bash
kubectl --kubeconfig=... -n <namespace> get pod -l app=podrunner
```

## Configuration

Edit `pod.yaml` to change:
- Container image (default `python:3.11-slim`)
- Resource requests/limits
- Anything else about the pod spec

The orchestrator only substitutes `__POD_NAME__`, `__NAMESPACE__`, `__OWNER__`, `__ENV_FROM__`. Everything else lives in the yaml as-is.

If you change the Python version in the image, re-download all wheels with the matching `--python-version`.

## Troubleshooting

- **"image is missing 'tar' — kubectl cp won't work"**: pick an image that includes `tar`. Most Python images do.
- **"pod did not become ready" after 5 minutes**: usually an image pull failure. Run `kubectl describe pod <pod-name>` to see why. Common causes: missing pull secret, wrong tag, network policy blocking the registry.
- **`pip install` fails with "no matching distribution"**: `wheels/` doesn't contain a wheel for linux x86_64 / Python 3.11. Re-download deps with the flags in [Adding a new package](#adding-a-new-package).
- **Script can't find files via `--output`**: paths are resolved under `/work`. Either write to `/work` from your script or pass an absolute path to `--output`.
