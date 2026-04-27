#!/usr/bin/env python3
"""Run a SQL query against postgres. Usage: query_postgres.py <sql>

Reads connection params from env vars (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME).
DB_NAME defaults to 'postgres' if unset.

For SELECT queries: writes results to results.csv (in the pod's /work dir),
streams progress to stdout as it runs. Use --output results.csv to copy back.

For DML/DDL: commits and prints affected rowcount.
"""
import csv
import os
import sys

import psycopg

if len(sys.argv) < 2:
    sys.exit("usage: query_postgres.py <sql>")

sql = sys.argv[1]
print(f"connecting to {os.environ['DB_HOST']}...")

conn = psycopg.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dbname=os.environ.get("DB_NAME", "postgres"),
)

print(f"running query...")
with conn.cursor() as cur:
    cur.execute(sql)
    if cur.description:
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
        print(f"{len(rows)} rows returned")
        with open("results.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"wrote results.csv")
    else:
        conn.commit()
        print(f"affected {cur.rowcount} rows")

conn.close()
