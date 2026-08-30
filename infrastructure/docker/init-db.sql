-- Runs automatically on first Postgres container start (mounted into
-- /docker-entrypoint-initdb.d/). Table creation itself is handled by
-- apps/api/database.py::init_db() at API startup for this MVP (see the
-- comment there about swapping to Alembic migrations for a real
-- production deployment) — this script only needs to ensure the
-- database/role exist, which the official postgres image's
-- POSTGRES_DB/POSTGRES_USER env vars already do. Kept as an explicit
-- file so future migrations/extensions have an obvious home.

-- Placeholder for future extensions, e.g.:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
SELECT 1;
