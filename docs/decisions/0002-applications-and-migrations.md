# 0002 — Applications table, status state machine, versioned migrations

- Status: Accepted
- Date: 2026-11-11

## Context
Issue #10 adds application tracking (status, notes, dates per job). This is the first schema
change after real data exists (`data/jobpilot.db`), so we need a safe way to evolve the schema.

## Decision
- **Separate `applications` table** keyed by `job_id` (FK to `jobs.id`): status, notes, applied_at,
  updated_at. A job with no row is implicitly `new`.
- **Light state machine** in `models.ALLOWED` / `tracker.change_status`: forward moves, rejected from
  active stages, and one step back to undo mistakes. The DB adds a `CHECK` constraint on status.
- **Versioned migrations**: an ordered `MIGRATIONS` tuple in `db.py`; `PRAGMA user_version` stores
  the applied version; `init_db()` applies pending ones, each in its own transaction.
  Old migrations are never edited.

## Alternatives considered
- Status/notes columns on `jobs`: fewer joins, but it mixes source data with personal data.
- A status-history table: a full timeline; deferred until stats need it (it can be added as a new migration).
- Free status changes: simpler, but allows nonsense like new → offer.
- Alembic/SQLAlchemy migrations: powerful, but an extra framework for a single-user SQLite app.

## Consequences
- Every app start runs `init_db()`, so databases upgrade themselves.
- New schema changes = append a migration + a test that upgrades an old DB.
