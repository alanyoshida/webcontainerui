---
title: Rollback
description: What survives tearing the composition down, how to roll back the database, the data plane and schema migrations, and the limitations of the deployment verification.
sidebar:
  order: 4
sourceHash: 70f598846c718fdb9adb2736b4c6fc9c1ed5c0925bba17162ad27c50d23fd0ee
---

This page describes how to go back after an update: what is preserved when the composition is torn down, how to roll back the database and the session data plane, and how to undo a schema migration. At the end are the known limitations of the verification of the deployment artifacts.

## What survives `docker compose down`

Tearing the composition down deletes nothing. The volumes below are named and survive `docker compose down`:

| Volume | Contents |
|---|---|
| `wcui_pg_data` | Production PostgreSQL database |
| `wcui_db` (production) or `wcui_db_dev` (development) | The portal's `/data`: uploaded covers and the SQLite file |
| `caddy_data`, `caddy_config` | Caddy certificates and state |
| `caddy_routes` | Session routes published by the portal |
| one volume per user desktop | Each user's data in each image |

:::danger
`docker compose down -v` deletes the volumes declared in the composition, including the database. Do not use `-v` in production without a verified backup.
:::

## Database

The production database has no data migration from SQLite: the PostgreSQL installation starts fresh. PostgreSQL backups are the recovery path — see [Backup and restore](/operations/backup-and-restore/).

### Before a schema migration in production

Before applying any update that changes the schema, take the logical backup:

```bash
docker compose exec -T postgres pg_dump -U wcui wcui > wcui-$(date +%F).sql
```

To roll back a migration that has already been applied, return the code to the previous version and restore this backup with the portal stopped, following the restore procedure.

### Going back to the previous version, with SQLite

The SQLite file in the `wcui_db` volume is never touched by the PostgreSQL version. To go back to the previous version, return to the previous image (or commit), or remove the `postgres` service from the composition and the `WCUI_DATABASE_URL` variable from the portal. Without that variable, the portal goes back to using the SQLite at `WCUI_DB_PATH`.

Data created in PostgreSQL after the update is not carried back to SQLite.

### SQLite database: copying and restoring the file

Where the database is SQLite — the development composition or a deploy of a version that predates PostgreSQL — the database is a single file, so copying it is trivial and rolling back is just a matter of restoring it. Before applying any schema migration, copy the file:

```bash
docker compose cp portal:/data/webcontainerui.db ./webcontainerui.db.backup
```

To roll back a migration that has already been applied, stop the portal, restore the backup into the volume and bring it up again:

```bash
docker compose stop portal
docker compose cp ./webcontainerui.db.backup portal:/data/webcontainerui.db
docker compose up -d portal
```

In the development composition, add `-f docker-compose.dev.yml` to each command.

:::note
SQLite runs in WAL mode. For a consistent copy, stop the portal before copying the file, or also copy the `-wal` and `-shm` files that sit next to it.
:::

## Session data plane

The data plane keeps no state beyond the route snippets in the `caddy_routes` volume. To go back to serving all sessions through the portal, restore the previous `Caddyfile` (or remove the volume and restart Caddy). The instances and the user volumes do not change.

The portal's in-process session proxy remains registered in production, shadowed by the edge routing; it is what takes over when the per-instance routes no longer exist in Caddy. With `WCUI_CADDY_ROUTES_DIR` empty, the portal also stops publishing routes. See [Session data plane](/architecture/session-data-plane/).

## The `wcui_net` network

Rolling back to a composition with a different network definition recreates `wcui_net`, which disconnects the instance containers attached to it. Plan the rollback with the same maintenance window as the update; the portal reconciles instance state during its own startup.

## Limitations of this verification

The deployment artifacts were written in a development environment without access to the Docker daemon (permission error on the socket). What could be validated in that environment:

- `docker compose config` on both compositions: correct syntax and variable interpolation, with no contact with the daemon.
- `caddy validate --config Caddyfile`, with the official binary downloaded only for this check: `Valid configuration`.
- The `Dockerfile` was reviewed by inspection. The front-end build stage, the installation of the Python package and the copy of the build to the directory pointed to by `frontend_dist` in `app/config.py` were checked manually, but `docker build` itself did not run in that environment.

Run the build in an environment with Docker available before the first real deploy, from the repository root:

```bash
docker build -t webcontainerui -f Dockerfile .
```

Next, run the [Post-deploy checklist](/operations/post-deploy-checklist/) in the target environment.
