-- template.sql: copy this to start a SQL job, rename it, keep what you need.
--
-- Run:  python run.py scripts/my-job.sql -n <namespace> --env PGHOST=<db-host> --env PGUSER=<user> --ask PGPASSWORD
--
-- The connection comes from Postgres's standard env vars: PGHOST, PGUSER,
-- PGPASSWORD, plus PGDATABASE (default: the user's name) and PGPORT (default 5432).
-- Give each with --env, --ask or --secret (README, Arguments).
-- Connection trouble: run test.sql, and test.py -- <db-host>:5432 for the network.
--
-- The whole file goes to Postgres as one query: it stops at the first error,
-- and nothing before the error is saved unless a COMMIT came before it.
--   BEGIN ... COMMIT    nothing is saved until COMMIT.
--   BEGIN ... ROLLBACK  everything runs and shows its results, nothing is saved.
-- VACUUM and CREATE INDEX CONCURRENTLY can't be in the file.
--
-- Output: each statement's status and rows are printed; they come back in
-- output/<pod>/log.txt.

BEGIN;

-- Where am I? Harmless, keep it or delete it.
SELECT current_user, current_database(), now();

-- Example change. RETURNING shows exactly which rows it touched.
-- UPDATE orders
-- SET status = 'cancelled'
-- WHERE status = 'pending' AND created_at < now() - interval '30 days'
-- RETURNING id, status;

-- Run it like this first: ROLLBACK undoes everything above.
-- When the output looks right, change ROLLBACK to COMMIT and run it again.
ROLLBACK;
