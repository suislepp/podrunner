# podrunner

Runs a Python script, shell script or SQL file in a fresh pod inside a k8s cluster, next to the databases and services it talks to. The script runs in the pod on its own, so a long job keeps going when your laptop sleeps or loses the connection. What the script prints and the files it writes come back to your machine, and the pod is deleted afterwards.

## Use

```bash
python run.py migration.sql -n orders --secret orders-db
```

That is a whole run:
1. Creates a pod in your current kubectl cluster, in namespace `orders`.
2. Installs the packages the file needs (see [Packages](#packages)), copies `migration.sql` in and starts it.
3. Shows its output live until it finishes.
4. Copies the pod's `/work` to `output/<pod>/` and deletes the pod.

Stop watching any time (Ctrl+C, closed laptop, dropped VPN): the script keeps running. Pick it up again with the command it prints:

```bash
python watch.py podrunner-ergo-x7k2qa -n orders
```

| run.py | |
|---|---|
| `<file>` | a `.py`, `.sh` or `.sql` file |
| `-n NAMESPACE` | required: where the pod runs. Typed every time on purpose, so a run never lands in a namespace by default. `watch.py` needs it too. |
| `--secret NAME` | a k8s Secret; each of its keys becomes an env var. Repeatable. |
| `--dry-run` | print the pod manifest and stop |
| `-- ...` | everything after goes to the script as its arguments |

Another cluster: point `KUBECONFIG` at its kubeconfig first (`export KUBECONFIG=~/.kube/config-prod`, PowerShell `$env:KUBECONFIG="..."`). run.py prints the cluster and namespace it uses before it starts.

## SQL files

A `.sql` file runs against the database named in its Secret: `DB_HOST`, `DB_USER`, `DB_PASSWORD`, plus `DB_NAME` and `DB_PORT` if they are not `postgres` and `5432`. It runs like `psql -v ON_ERROR_STOP=1 -f`:

- Statement by statement, each saved as it runs, unless the file wraps statements in `BEGIN ... COMMIT`.
- It stops at the first error. Statements before it are saved, except any inside a `BEGIN` that had not reached `COMMIT`.
- Rows a statement returns are printed and saved to `result_<n>.csv`, `n` being the statement's number in the output.
- psql's backslash commands (`\copy`, `\set`, `\i`) don't work.

## What comes back

`output/<pod>/` gets everything in the pod's `/work` when the script ends: the script itself, `log.txt` with everything it printed, and every file it wrote into its working directory. Files written elsewhere in the pod stay there.

## When it ends

- **Success**: the files come back, the pod is deleted.
- **The script fails**: the files come back, the pod is kept so you can look inside. The commands to look in or delete it are printed.
- **You never come back**: after the script ends the pod keeps `/work` for 24 h, so `watch.py` can still collect it, then stops. Your stopped pods are deleted the next time you use `run.py`.
- **Setup fails** (image, Secret, packages): the pod's events are printed and the pod is deleted. Nothing was run.

## Scripts

Copy a template to start a job of your own.

| Script | What it is for |
|---|---|
| `test.py` | First run in a new cluster: args and secrets arrive, files come back. `-- host:port ...` also checks that each address resolves and answers, e.g. `-- postgres.internal:5432`. |
| `test.sql` | Can the pod log in to the database: shows the user, database, Postgres version and whether it's a replica. Changes nothing. |
| `template.py` | Starting point for a Python job, including how to reach Postgres from Python. |
| `template.sql` | Starting point for a SQL job. Runs as a preview (`BEGIN ... ROLLBACK`) until you change it to `COMMIT`. |

## Packages

The pod has no internet, so `run.py` downloads packages on your machine and installs them in the pod. Each job gets only what it needs:

- **A `.py` file** lists what it imports from outside the standard library in a block at its top, in Python's standard format for this ([PEP 723](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)):
  ```python
  # /// script
  # dependencies = ["requests", "psycopg[binary]"]
  # ///
  ```
  No block means no packages. If one is missing, the log says `ModuleNotFoundError: No module named '...'`: add it to the block.
- **A `.sql` file** always gets `psycopg` and `sqlparse`, which `pod/sql_runner.py` needs.
- **A `.sh` file** gets none.

Downloads are kept in `pod/wheels/`, one folder per package list, so the same list is only downloaded once. Your machine needs internet that first time. `pod/wheels/` is not committed; delete it any time to download fresh versions.

If you change the Python version of the image in `pod/pod.yaml`, change `PYTHON_VERSION` in `pod/wheels.py` to match.

## Layout

```
run.py            start a job
watch.py          follow a job, collect results, delete the pod
pod/
  pod.yaml          the pod's definition: image, resources, its start-up steps
  sql_runner.py     runs .sql files inside the pod
  wheels.py         downloads packages for the pod (run.py calls it)
  wheels/           the download cache, not committed
scripts/          tests and templates
output/           results, not committed
```

## Setting up a Secret

Key names become env var names as they are:

```bash
kubectl -n orders create secret generic orders-db \
  --from-literal=DB_HOST=postgres.internal \
  --from-literal=DB_USER=svc_debug \
  --from-literal=DB_PASSWORD=<value>
```

## Troubleshooting

- **Setup failed**: the events printed above it say why: image pull, a Secret that doesn't exist, no permission.
- **`pip install` fails with "no matching distribution"**: check `PYTHON_VERSION` in `pod/wheels.py` matches the image (`test.py` prints the image's version), then delete `pod/wheels/` so the packages download again.
- **The script can't reach a database or service**: `test.py -- host:port` says whether it's DNS or a blocked port. `test.sql` with the database's Secret shows whether the login works; Postgres's own message says why not, e.g. `password authentication failed for user "x"`.

## Requirements

- **Your machine**: Python 3.11+ with pip, `kubectl` with access to the cluster, internet the first time a package list is used.
- **Cluster**: permission in the namespace to create, exec into, read logs of and delete pods, read Secrets and events.
- **Image** (`pod/pod.yaml`, default `python:3.11-slim`): needs `bash`, `tar` and `timeout`. Resources are set in `pod/pod.yaml` too.
