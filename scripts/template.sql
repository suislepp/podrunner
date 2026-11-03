-- template.sql: copy this to start a SQL job, rename it, keep what you need.
--
-- Run:  python run.py scripts/my-job.sql -n <namespace> --secret <db-secret>
--
-- The Secret needs DB_HOST, DB_USER, DB_PASSWORD, plus DB_NAME and DB_PORT if
-- they aren't postgres and 5432. Connection trouble: run test.sql, and
-- test.py -- <db-host>:5432 for the network.
--
-- It runs like `psql -v ON_ERROR_STOP=1 -f`: statement by statement, each one
-- saved as it runs, stopping at the first error.
--   BEGIN ... COMMIT    nothing is saved until COMMIT; an error before it saves none of it.
--   BEGIN ... ROLLBACK  everything runs and shows its results, nothing is saved.
-- VACUUM and CREATE INDEX CONCURRENTLY can't go between BEGIN and COMMIT.
--
-- Output: each statement's result is printed, and the rows of every statement
-- that returns rows go to result_<n>.csv (n is its number in the output).
-- Both come back to output/<pod>/, with log.txt.

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
