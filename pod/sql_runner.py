#!/usr/bin/env python3
"""Runs a .sql file in the pod. The whole file goes to Postgres as one query: it stops at the first
error, and nothing before the error is saved unless a COMMIT came before it. Each statement's status
and rows are printed. run.py copies this into the pod.
Connects with Postgres's standard env vars: PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGPORT."""
import sys

import psycopg

with psycopg.connect(autocommit=True) as conn:
    conn.add_notice_handler(lambda d: print(f"{d.severity}: {d.message_primary}"))
    for cur in conn.execute(open(sys.argv[1]).read()).results():
        print(cur.statusmessage)
        if cur.description:
            print(" | ".join(d.name for d in cur.description))
            for row in cur:
                print(" | ".join(str(v) for v in row))
