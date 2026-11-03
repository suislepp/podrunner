# podrunner

Runs a Python or SQL file in a fresh pod inside a k8s cluster, next to the database or service it uses. The file runs in the pod on its own, so closing your laptop doesn't stop it. The results come back to `output/<pod>/` and the pod is deleted.

## Requirements

- Python 3.11+ and `kubectl` on your machine, with kubectl pointed at the cluster (`KUBECONFIG`).
- Internet on your machine the first time a script's packages are used. They are downloaded there; the pod has no internet.
- In the namespace: permission to create, exec into, read logs of and delete pods, and to read Secrets and events.
- For SQL: a k8s Secret with the database's `DB_HOST`, `DB_USER`, `DB_PASSWORD` (and `DB_NAME`, `DB_PORT` if they aren't `postgres` and `5432`).

## Arguments

```
python run.py <file> -n <namespace> [--secret <name>] [-- <args for the script>]
python watch.py <pod> -n <namespace>
```

| | |
|---|---|
| `<file>` | a `.py`, `.sql` or `.sh` file |
| `-n` | the namespace to run in. Required. |
| `--secret` | a k8s Secret; each of its keys becomes an env var in the pod. Repeatable. |
| `-- ...` | everything after `--` goes to the script as its arguments |
| `--dry-run` | print the pod it would create, and stop |

## Scripts

| | |
|---|---|
| `run.py` | starts a job in a new pod, then follows it with `watch.py` |
| `watch.py` | shows a job's output live; when it ends, copies the results to `output/<pod>/` and deletes the pod |
| `scripts/test.py` | checks podrunner works in a cluster. `-- host:port` also checks the network to that address. |
| `scripts/test.sql` | checks the login to a database: user, database, version, replica or not |
| `scripts/template.py`, `scripts/template.sql` | starting points for your own jobs |
| `pod/` | the pod's definition and what goes into it. Nothing to run there. |

## Examples

**Python**

```bash
python run.py report.py -n orders --secret orders-db -- --day 2026-11-01
```

Runs `report.py` in a pod in namespace `orders`, with the Secret's keys as env vars and `--day 2026-11-01` as its argument. Packages it imports go in a block at its top:

```python
# /// script
# dependencies = ["requests", "psycopg[binary]"]
# ///
```

Comes back in `output/<pod>/`: `log.txt` with everything it printed, and every file it wrote with a relative path.

**SQL**

```bash
python run.py migration.sql -n orders --secret orders-db
```

Runs `migration.sql` against the database in the Secret, like `psql -v ON_ERROR_STOP=1`: each statement is saved as it runs, it stops at the first error, and `BEGIN ... COMMIT` makes a block all-or-nothing. Comes back in `output/<pod>/`: `log.txt`, and `result_<n>.csv` for each statement that returned rows.

**Either way:** Ctrl+C or a dropped connection only stops the watching; the job keeps running, and `run.py` prints the `watch.py` command to pick it up again. If the job fails, the pod is kept for 24 h so you can look inside.
