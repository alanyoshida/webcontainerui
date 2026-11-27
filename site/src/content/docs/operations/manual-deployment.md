---
title: Manual deployment
description: Step-by-step startup order of the production composition, the role of each service, and startup in development.
sidebar:
  order: 1
sourceHash: 8188b2a35540cb363e57eca44d43641afbc3d6cf162f38dc0c4b0e7eff6a81ec
---

This page describes how to bring the portal up manually in production: the prerequisites, the order of the commands, what each service in the composition does, and how to diagnose the session data plane. The fast path is the [`install.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/install.sh) script at the repository root, which automates everything described here (prerequisite checks, configuration gathering, secret generation and bringing the composition up) and is covered in [Installation](/getting-started/installation/). The manual version is useful for understanding what the script does or for running it step by step.

:::danger
The portal mounts the Docker socket, which is equivalent to root access on the host. Read [Trust surface](/security/trust-surface/) before exposing the portal beyond your own machine.
:::

## Prerequisites

- Docker Engine with the Compose v2 plugin (`docker compose version` must respond) and a user able to talk to the daemon (`docker info`).
- A public domain whose DNS already points to the host. Caddy requests a Let's Encrypt certificate for that domain on the first startup.
- Ports `80` and `443` on the host free and reachable from outside. They are the only ports the composition publishes.
- Disk space and bandwidth for the first deploy: the catalog's desktop images add up to several GB.
- `python3` to generate the secrets (optional: `openssl` works as an alternative, see [Environment variables](/operations/environment-variables/)).

## Startup order in production

Set the six required variables and bring the composition up from the `deploy/` directory:

```bash
cd deploy
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="uma senha com pelo menos 12 caracteres"
export WCUI_SSH_KEY_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export WCUI_DATA_PLANE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export WCUI_POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d --build
```

:::caution
The commands above generate new secrets on every run. In a real deploy, generate each value only once and store it in `deploy/.env` (template in [`deploy/.env.example`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/.env.example)), which `docker compose` reads automatically and git ignores. Changing `WCUI_SSH_KEY_ENCRYPTION_KEY` after first use makes it impossible to decrypt the SSH keys already encrypted in the database, and changing `WCUI_POSTGRES_PASSWORD` after the database volume has been initialized makes the portal fail to authenticate against PostgreSQL.
:::

The composition refuses to start if any required variable is missing: `docker compose` fails early with a clear message, instead of the portal crashing at startup. The description of every variable, required or optional, is in [Environment variables](/operations/environment-variables/).

### What happens during startup

1. The composition creates the `wcui_net` network and the named volumes automatically.
2. `postgres` starts and begins answering the healthcheck (`pg_isready`).
3. `portal` only starts once the database is healthy. During its own startup it applies the schema and provisions the first administrator from `WCUI_ADMIN_EMAIL` and `WCUI_ADMIN_PASSWORD` (contract in the [`user-management`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/user-management/spec.md) spec).
4. `caddy` depends on `portal` already being up before it starts accepting external traffic.

The catalog is also provisioned at portal startup: the 5 coding agents (built locally) and the 4 desktop entries — Webtop XFCE, Ubuntu KDE, Alpine MATE and VS Code — start being built and pulled in the background. The desktop images add up to several GB of disk and network on the first deploy. Entries that already exist in the catalog are never duplicated or overwritten by provisioning: state, edited limits, disabling and a manual cover set by the administrator take precedence. Details in [Agent images](/architecture/agent-images/).

### After startup

Sign in with `WCUI_ADMIN_EMAIL` and `WCUI_ADMIN_PASSWORD`, register any additional images you want in the catalog, create groups and users, and grant access. For a user to see any image, it must be granted to a group the user belongs to.

Each image is pulled in the background. Follow its state in the "Catálogo" (Catalog) tab of the admin panel before expecting a user to be able to start an instance of it.

Next, run the [Post-deploy checklist](/operations/post-deploy-checklist/).

### Updating an existing deploy

:::caution
The `wcui_net` subnet is pinned by IPAM in the composition, and Docker does not apply new IPAM to a network that already exists. When updating a deploy that predates this pinning, `docker compose up -d` recreates the network, which disconnects the instance containers attached to it. Plan a maintenance window, as for any update that recreates a network. The portal reconciles instance state during its own startup.
:::

Production starts with an empty PostgreSQL database: there is no automatic migration from the SQLite used by earlier versions. Before updating a deploy that still used SQLite, stop the running instances. The `wcui_db` volume remains mounted in the portal, intact, to allow a [Rollback](/operations/rollback/). Before any update that changes the schema, take a [backup](/operations/backup-and-restore/).

## Services in the composition

The production composition is in [`deploy/docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml) and defines three services, all on the internal `wcui_net` network.

| Service | Image | Host port | Role |
|---|---|---|---|
| `caddy` | `caddy:2-alpine` | `80`, `443` | Terminates TLS, acts as the session data plane and forwards everything else to the portal |
| `portal` | built from the root `Dockerfile` | none | API, front end, authentication, catalog and instance lifecycle |
| `postgres` | `postgres:17-alpine` | none | Portal persistence |

### Caddy

Caddy is the only service that publishes ports. It obtains and renews the Let's Encrypt certificate for `WCUI_DOMAIN`, adds the HSTS header (`Strict-Transport-Security: max-age=31536000`, without `includeSubDomains` or `preload` — each deploy decides whether to go further), removes the `Server` header from responses, and answers `404` to any external request for `/internal/*`. The container has a fixed name, `wcui-caddy`, because the portal runs `caddy reload` in it when publishing or withdrawing session routes.

Everything that is not a session route is forwarded to `portal:8000`, with read and write timeouts of 3600 seconds so that long-lived connections are not cut. WebSocket needs no special directive: Caddy's `reverse_proxy` passes connection upgrades through by default. The configuration is in [`deploy/Caddyfile`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/Caddyfile).

Volumes: `caddy_data` (certificates), `caddy_config` and `caddy_routes` (session routes, shared with the portal).

### Portal

The portal is built from the root [`Dockerfile`](https://github.com/alanyoshida/webcontainerui/blob/main/Dockerfile), which compiles the front end and serves it alongside the API. It publishes no port: it is reachable only by Caddy, from inside `wcui_net`. The healthcheck queries `http://localhost:8000/health` every 30 seconds.

The portal mounts `/var/run/docker.sock` to create the instance containers, which join the same `wcui_net` without publishing any port on the host. Isolation between users depends on this topology, not just on the ownership check — see [Isolation layers](/security/isolation-layers/).

Volumes: `wcui_db` at `/data` (covers uploaded by the administrator and the SQLite file from earlier versions) and `caddy_routes` at `/data/caddy-routes`.

### PostgreSQL

In production, persistence is the `postgres` service, on the internal network and with no port published on the host: only the portal reaches it. The portal receives `WCUI_DATABASE_URL`, assembled by the composition from `WCUI_POSTGRES_PASSWORD` (database `wcui`, user `wcui`), and only starts after the database healthcheck, via `depends_on` with `condition: service_healthy`.

- The data lives in the named volume `wcui_pg_data` and survives `docker compose down` (without `-v`).
- Production starts with an empty database; there is no automatic migration from the old SQLite.
- Development and tests stay on SQLite (`WCUI_DB_PATH`), without `WCUI_DATABASE_URL`.

Backup and restore are covered in [Backup and restore](/operations/backup-and-restore/); the design of the persistence layer, in [Database](/architecture/database/).

## Session data plane

Caddy is not just TLS termination: it carries `/i/{uuid}/` (HTTP and WebSocket) directly to the instance containers, without the frames passing through the portal process. For each live instance, the portal writes a route snippet to the named volume `caddy_routes` — mounted in Caddy at `/etc/caddy/caddy-routes` and in the portal at `/data/caddy-routes` — and reloads Caddy with `docker exec` in the `wcui-caddy` container. The reload command is fixed in the portal's code.

Before forwarding each request, Caddy queries the portal at `/internal/data-plane/authorize` (`forward_auth`), which checks for a valid session, ownership and a running instance. Only the 2xx response carries the instance's internal credential, which is copied onto the forwarded request; the client never sees it. The endpoint requires `WCUI_DATA_PLANE_SECRET` and is not exposed by the edge (Caddy answers `404` to `/internal/*` coming from outside).

The full design is in [Session data plane](/architecture/session-data-plane/) and the formal contract in the [`stream-data-plane`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md) spec.

### Symptoms and diagnosis

**Session stuck on "carregando" (loading) with the portal up.** Check the published routes:

```bash
docker exec wcui-caddy ls /etc/caddy/caddy-routes
```

The expected result is one file per instance in the `running` state, plus `000-placeholder.caddy` (which keeps the Caddyfile's `import` matching at least one file).

**Route published but not applied.** The `reload` failed. The portal's audit log has a `data_plane.reload` event with the reason:

```bash
docker compose logs portal | grep data_plane.reload
```

Caddy keeps the last valid configuration, so it never ends up with a broken configuration; the route goes in on the instance's next lifecycle event. The event format is described in [Audit log](/security/audit-log/).

**Publishing turned off.** `WCUI_CADDY_ROUTES_DIR` is empty. In this mode the portal serves sessions through its own internal path (the in-process proxy), which is the default in development and in the tests.

## TLS proxy and the `Secure` cookie

Behind Caddy, the portal only sees the real scheme of the request (`https`) and the real client IP if it trusts the forwarded headers (`X-Forwarded-Proto`, `X-Forwarded-For`). Without that, the session cookie is created without the `Secure` flag and the login limiter only sees Caddy's own IP.

The production composition already turns this behavior on: it sets `UVICORN_PROXY_HEADERS=true` and restricts the trusted origin to the `wcui_net` subnet (`10.213.0.0/24`, pinned in the composition's IPAM) through `UVICORN_FORWARDED_ALLOW_IPS`. These variables only need to be touched if you change the network's subnet; in that case, change the IPAM and `WCUI_FORWARDED_ALLOW_IPS` together. See [Environment variables](/operations/environment-variables/).

The development composition does not set these variables: with no proxy in front, forwarded headers remain ignored (untrusted origin).

The security context for these measures is in [Login hardening](/security/login-hardening/).

## Security headers and interactive documentation

The portal adds the headers below to every response of its own:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `no-referrer` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Content-Security-Policy` | restrictive policy with `default-src 'self'` |

The exception is the session path `/i/...`, whose content comes from the user's container and must not receive the portal's policy. The CSP's `style-src 'unsafe-inline'` is a requirement of MUI/Emotion (styles injected inline); scripts, fonts and connections are all same-origin. `X-Frame-Options` is `SAMEORIGIN`, not `DENY`, because the portal itself embeds the session in an iframe.

The interactive API documentation (`/docs`, `/redoc` and `/openapi.json`) is off by default, so as not to hand the API map to anonymous visitors. `WCUI_DOCS_ENABLED=true` turns it on, which is useful in development.

The formal contract is in the [`http-hardening`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md) spec.

## Startup in development

The development composition ([`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml)) has neither Caddy nor PostgreSQL: `http://localhost` is already a secure context, which is what the Selkies client requires for WebCodecs to work, so TLS is not needed in development.

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

This composition brings up only the portal, with the following differences from production:

- Port `8000` is published only on `127.0.0.1`, never on the LAN.
- The database is SQLite at `/data/webcontainerui.db`, in the `wcui_db_dev` volume.
- The instance network is `wcui_net_dev`.
- The administrator and the encryption key for SSH identities are fixed, public values defined in the file itself. Never reuse them in production.
- The external data plane is off: the portal serves sessions through the in-process proxy.

The image already includes the compiled front end, so the complete application responds at `http://127.0.0.1:8000`. To develop the front end with automatic reload, run `npm run dev` inside `frontend/`: the Vite proxy ([`frontend/vite.config.js`](https://github.com/alanyoshida/webcontainerui/blob/main/frontend/vite.config.js)) forwards `/api`, `/i` and `/uploads` to the portal, playing the single-origin role that in production is FastAPI itself serving the React build.

The step-by-step guide to trying the portal locally is in [Local trial](/getting-started/local-trial/); the development and testing workflow, in [Development](/reference/development/).
