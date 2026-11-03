# podrunner

Runs a Python or SQL file in a fresh pod inside a k8s cluster, next to the database or service it uses. The file runs in the pod on its own, so closing your laptop doesn't stop it. The results come back to `output/<pod>/` and the pod is deleted.

## Requirements

- Python 3.9+
- `kubectl`, with a kubeconfig for the cluster
- For SQL: the connection as Postgres's standard env vars `PGHOST`, `PGUSER`, `PGPASSWORD` (plus `PGDATABASE`, default the user's name, and `PGPORT`, default 5432), given with the flags below

## Arguments

```
python run.py <file> -n <namespace> [--env NAME=value] [--ask NAME] [--secret NAME=secret/key] [-- <args for the script>]
python watch.py <pod> -n <namespace>
```

| | |
|---|---|
| `<file>` | a `.py`, `.sql` or `.sh` file |
| `-n` | the namespace to run in. Required. |
| `--env NAME=value` | an env var with a value you type, e.g. `--env PGHOST=orders-pg` |
| `--ask NAME` | an env var whose value you're asked for when the run starts, without it showing. Not saved in your shell history or in the pod's definition. For passwords. |
| `--secret NAME=secret/key` | an env var taken from a key of an existing k8s Secret, e.g. `--secret PGPASSWORD=orders-db/password` |
| `-- ...` | everything after `--` goes to the script as its arguments |
| `--dry-run` | print the pod it would create, and stop |

`--env`, `--ask` and `--secret` can each be given several times.

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
python run.py report.py -n orders --env API_URL=http://orders-api --secret API_TOKEN=orders-api/token -- --day 2026-11-01
```

Runs `report.py` in a pod in namespace `orders`, with `API_URL` and `API_TOKEN` as env vars (the token from the key `token` of the Secret `orders-api`) and `--day 2026-11-01` as its argument. Packages it imports go in a block at its top:

```python
# /// script
# dependencies = ["requests", "psycopg[binary]"]
# ///
```

Comes back in `output/<pod>/`: `log.txt` with everything it printed, and every file it wrote with a relative path.

**SQL**

```bash
python run.py migration.sql -n orders --env PGHOST=orders-pg --env PGUSER=admin --ask PGPASSWORD
```

Asks for the password, then runs `migration.sql` against `orders-pg` as `admin`, like `psql -v ON_ERROR_STOP=1`: each statement is saved as it runs, it stops at the first error, and `BEGIN ... COMMIT` makes a block all-or-nothing. Comes back in `output/<pod>/`: `log.txt`, and `result_<n>.csv` for each statement that returned rows.

**Either way:** Ctrl+C or a dropped connection only stops the watching; the job keeps running, and `run.py` prints the `watch.py` command to pick it up again. If the job fails, the pod is kept for 24 h so you can look inside.
