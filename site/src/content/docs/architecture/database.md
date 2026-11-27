---
title: Database
description: SQLite in development and tests, PostgreSQL in production, and the SQLAlchemy Core conventions that keep behavior the same on both engines.
sidebar:
  order: 3
sourceHash: fdbc27256435e00ddf66c9d32f2156a946f0040d6f93e3afa06e0d4902bd1c6e
---

The portal uses two database engines, chosen per environment: SQLite in development and local tests, with no extra dependency, and PostgreSQL in production. Data access is written once, in SQLAlchemy Core, to run the same on both.

## Engine selection

The choice depends on a single variable:

| Situation | Engine | Where the data lives |
|---|---|---|
| `WCUI_DATABASE_URL` missing or empty | SQLite | File at `WCUI_DB_PATH` (default `/data/webcontainerui.db`) |
| `WCUI_DATABASE_URL` set | PostgreSQL | Database pointed to by the URL, in the format `postgresql+psycopg://user:password@host:5432/database` |

No other configuration or code change is needed.

## SQLite in development

Each SQLite connection is opened with `journal_mode = WAL`, a `busy_timeout` of 5 seconds and `foreign_keys` on. In the development composition, the file lives on the `wcui_db_dev` volume.

## PostgreSQL in production

The production composition itself provides the database:

- image `postgres:17-alpine`, database and user `wcui`;
- password in `WCUI_POSTGRES_PASSWORD`; the connection URL is assembled in [`docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml);
- on the internal network `wcui_net` only, with no port published on the host;
- data on the named volume `wcui_pg_data`, which survives container recreation;
- readiness check with `pg_isready`; the portal only starts after the database reports healthy.

:::note
Production starts with an empty database. There is no automatic migration from an existing SQLite database to PostgreSQL.
:::

Procedures for backup and for returning to a previous version are in [Backup and restore](/operations/backup-and-restore/) and [Rollback](/operations/rollback/).

## Data access

Everything goes through SQLAlchemy Core, in [`backend/app/db.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/db.py), with explicit SQL and named parameters. There is no ORM.

### Schema and migrations

The schema lives in a single `MetaData` and is created with `create_all`. Since `create_all` does not alter existing tables, migrations are idempotent and done through `Inspector`: when a column is missing, the portal runs `ALTER TABLE ADD COLUMN`. No migration depends on `PRAGMA`.

The result is that starting against an empty database creates the full schema, and restarting on an already migrated database is a no-op.

:::caution
In production, take a backup with `pg_dump` before updating to a version that changes the schema.
:::

### Connections

The connections exposed to the services are `DbConnection`, a wrapper in which:

- `execute` takes SQL in `text()` with named parameters in the `:name` format;
- result rows are accessible by column name;
- inserts that need the generated identifier use `RETURNING id`.

### Timestamps

Timestamps are naive `DateTime` values in UTC, stored with second precision on both engines. Since `text()` carries no type information, a date column comes back as `str` on SQLite and as `datetime` on PostgreSQL. For that reason:

- binds use `format_ts` or `ts_param`;
- when consuming a date column, the code normalizes it with `as_datetime` or `format_ts`.

### Booleans

Columns such as `is_admin`, `enabled` and `harden_desktop` are `Boolean`. Comparisons are made by parameter (`= :flag`), never with the literal `= 1`, which is not portable across the engines.

## Tests

| Suite | Command | Database |
|---|---|---|
| Default | `pytest` | SQLite; does not require Docker |
| e2e | `pytest -m e2e` | Starts an ephemeral PostgreSQL in Docker |

The e2e suite validates bootstrap, login, users, the instance lifecycle and metrics against PostgreSQL, covering what is dialect-specific. The full commands are in [Development](/reference/development/).

## Formal reference

The behavior contract is in the [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md) spec.
