#!/usr/bin/env python3
"""Runs a .sql file in the pod the way `psql -v ON_ERROR_STOP=1 -f` would: statement by statement,
each saved as it runs unless the file wraps it in BEGIN ... COMMIT, stopping at the first error.
Rows a statement returns are printed and saved to result_<n>.csv. run.py copies this into the pod.
Connects with Postgres's standard env vars: PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGPORT."""
import csv
import sys
from pathlib import Path

import psycopg
import sqlparse

file = Path(sys.argv[1])
statements = [s for s in sqlparse.split(file.read_text(encoding="utf-8"))
              if sqlparse.format(s, strip_comments=True).strip()]

try:
    conn = psycopg.connect(connect_timeout=10, autocommit=True)
except psycopg.OperationalError as e:
    sys.exit(f"error: could not connect: {e}")
conn.add_notice_handler(lambda d: print(f"    {d.severity}: {d.message_primary}"))
print(f"connected to {conn.info.host} as {conn.info.user}, database {conn.info.dbname}, "
      f"running {len(statements)} statements from {file.name}")

with conn.cursor() as cur:
    for n, statement in enumerate(statements, 1):
        print(f"[{n}] {sqlparse.format(statement, strip_comments=True).strip().splitlines()[0][:100]}")
        try:
            cur.execute(statement)
        except psycopg.Error as e:
            print(f"error: {e}")
            print(f"Stopped at statement {n}. Statements before it are saved, "
                  "except any inside a BEGIN that had not reached COMMIT.")
            sys.exit(1)
        print(f"    {cur.statusmessage}")
        if cur.description:
            columns = [d.name for d in cur.description]
            rows = cur.fetchall()
            with open(f"result_{n}.csv", "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows([columns, *rows])
            print("    " + " | ".join(columns))
            for row in rows[:20]:
                print("    " + " | ".join(str(v) for v in row))
            print(f"    ({len(rows)} rows, saved to result_{n}.csv)")
conn.close()
