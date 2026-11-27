---
title: Local trial
description: How to bring the portal up on your own machine with one command, with no domain, no TLS and no Caddy.
sidebar:
  order: 2
sourceHash: a3b1baefb426782abe6dd8e0d099a23581b298995b837faa0c62696d21802d8e
---

The development composition brings the whole portal up on your own machine, with no domain, no TLS and no Caddy. It is the shortest path to evaluating the product before a production installation.

## Prerequisites

- Docker with the Docker Compose v2 plugin.
- A clone of the repository.

You do not need Node or Python installed: the image is built from the [`Dockerfile`](https://github.com/alanyoshida/webcontainerui/blob/main/Dockerfile) at the repository root, which compiles the front end in a stage of its own.

## Bring it up

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

The full application (front end and API) responds at `http://127.0.0.1:8000`. Sign in with the development credentials:

| Field | Value |
|---|---|
| Email | `admin@local.test` |
| Password | `senha-admin-dev-123456` |

:::caution
These credentials and the encryption key for SSH identities are fixed and public in [`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml). They are for local testing only. The portal listens only on `127.0.0.1`, so it is not exposed to the network; do not change that port mapping to publish it.
:::

## What happens on first startup

At startup, the portal:

1. builds the agent base image and then the five coding agent images, waiting for each build;
2. registers the four default desktop entries and starts downloading them in the background;
3. assigns a default cover to each catalog entry.

Because of the first step, the first startup takes longer than later ones: the portal only starts responding after the agent builds finish. On later startups, only what changed is rebuilt. The desktop images are several gigabytes in size and show download progress in the admin panel; only a ready image can be used to create an instance.

## What the composition creates

| Resource | Name | Purpose |
|---|---|---|
| Service | `portal` | FastAPI serving the front end, the API and session forwarding |
| Port | `127.0.0.1:8000` | Single point of access, restricted to the local host |
| Network | `wcui_net_dev` | Internal network where the portal and the instances live |
| Volume | `wcui_db_dev` | SQLite database at `/data/webcontainerui.db` and uploaded covers |

The Docker socket (`/var/run/docker.sock`) is mounted into the portal, which uses it to create the instance containers. The warning in [Trust surface](/security/trust-surface/) applies here too.

## Why it works without TLS

The Selkies client, used by the webtop images, requires a *secure context* for the WebCodecs API to work. The browser already treats `http://localhost` and `http://127.0.0.1` as a secure context, so TLS is not needed in this scenario. Any other address requires HTTPS, which the [production installation](/getting-started/installation/) provides with Caddy.

Without Caddy, the portal process itself delivers the sessions, through the in-process proxy described in [Session data plane](/architecture/session-data-plane/).

## Tear down

To tear down while preserving the database:

```bash
cd deploy && docker compose -f docker-compose.dev.yml down
```

To also delete the database volume:

```bash
cd deploy && docker compose -f docker-compose.dev.yml down -v
```

:::note
The instance containers and the users' file volumes are created by the portal directly in Docker, outside the composition. `down` does not remove them; delete the instances through the portal before tearing down, or remove them manually afterwards.
:::

## Next steps

To develop the front end with hot reload and run the test suites, see [Development](/reference/development/).
