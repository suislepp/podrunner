#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""template.py: copy this to start a Python job, rename it, keep what you need.

Run:
  python run.py scripts/my-job.py -n <namespace> --secret <secret-name> -- --day 2026-11-01

  --secret   each key in the Secret becomes an env var
  after --   passed to this script as its own arguments

How it runs in the pod:
- Packages: list what the script imports from outside the standard library in
  the block at the top, e.g. dependencies = ["requests", "psycopg[binary]"].
  run.py downloads them on your machine and installs them in the pod.
  The pod itself has no internet.
- The working directory is /work. Everything left there when the script ends,
  plus log.txt with everything it printed, comes back to output/<pod>/.
- print() shows up live in your terminal.
- A non-zero exit code, or an uncaught exception, counts as a failure:
  the pod is kept so you can look inside.
- Postgres from Python: add "psycopg[binary]" to the block, pass the database's
  Secret with --secret, then:
    import psycopg
    conn = psycopg.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], dbname=os.environ.get("DB_NAME", "postgres"))
  Nothing is saved until conn.commit().
"""
import argparse
import csv
import os
import sys


def main():
    # Arguments: whatever comes after "--" on the podrunner command line.
    p = argparse.ArgumentParser()
    p.add_argument("--day", help="example argument")
    args = p.parse_args()

    # Secrets: os.environ["NAME"] fails loudly if the key is missing, which is
    # what you want for anything required. .get() gives a default instead.
    api_url = os.environ.get("API_URL", "http://example.internal")  # example only

    # The work.
    print(f"running for day={args.day}, api={api_url}")
    rows = [("example", 1), ("rows", 2)]

    # A failure: print why and return non-zero, so podrunner keeps the pod.
    if not rows:
        print("error: nothing to write", file=sys.stderr)
        return 1

    # Output: write into the current directory (/work); it comes back by itself.
    with open("result.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "value"])
        w.writerows(rows)
    print(f"wrote result.csv ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
