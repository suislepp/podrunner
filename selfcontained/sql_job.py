"""
python -m pip download --python-version 3.13 --platform manylinux2014_x86_64 --only-binary=:all: -d wheels "psycopg[binary]"
kubectl -n NS apply -f sqljob.yaml
kubectl -n NS wait --for=condition=Ready pod/sqljob --timeout=5m
kubectl -n NS cp wheels sqljob:/tmp/wheels
kubectl -n NS exec sqljob -- pip install -q --no-index --find-links /tmp/wheels "psycopg[binary]"
kubectl -n NS cp sql_job.py sqljob:/sql_job.py
kubectl -n NS exec sqljob -- touch /ready
kubectl -n NS logs -f sqljob
kubectl -n NS logs sqljob > log.txt
kubectl -n NS delete pod sqljob
"""
import os

import psycopg

CONNECTION = dict(
    host=os.environ["host"],
    port=os.environ["port"],
    dbname=os.environ["dbname"],
    user=os.environ["username"],
    password=os.environ["password"],
)

STATEMENTS = [
    """
    SELECT current_user, current_database(), now();
    """,
    """
    UPDATE orders
    SET status = 'cancelled'
    WHERE status = 'pending' AND created_at < now() - interval '30 days'
    RETURNING id, status;
    """,
]


def connect():
    conn = psycopg.connect(**CONNECTION, autocommit=True)
    conn.add_notice_handler(print_notice)
    return conn


def print_notice(notice):
    print(f"{notice.severity}: {notice.message_primary}")


def print_result(cursor):
    print(cursor.statusmessage)
    if cursor.description:
        print(" | ".join(column.name for column in cursor.description))
        for row in cursor:
            print(" | ".join(str(value) for value in row))


def main():
    with connect() as conn:
        for number, statement in enumerate(STATEMENTS, 1):
            print(f"--- statement {number}")
            for result in conn.execute(statement).results():
                print_result(result)
    print("done")


main()
