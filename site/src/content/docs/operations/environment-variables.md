---
title: Environment variables
description: Reference for every environment variable of the portal and the production composition, with whether it is required, its default and its effect.
sidebar:
  order: 2
sourceHash: a1302d39bd16ff7364502d871a174f75e0e308cb73015a4e1f53ee40cc67c0c3
---

The portal reads its configuration from the environment, with the `WCUI_` prefix. This page lists every variable: the ones the production composition requires, the ones it sets itself, and the optional ones, which have sensible defaults and only need to be touched for tuning. The source of truth is [`backend/app/config.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/config.py) for the portal and [`deploy/docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml) for the composition.

## How variables reach the portal

There are two levels, and the difference matters when changing a value:

- **Composition variables.** `docker compose` reads the shell environment and the `deploy/.env` file to interpolate `docker-compose.yml`. The six required variables and `WCUI_FORWARDED_ALLOW_IPS` are of this kind.
- **Portal container variables.** The portal only sees what is in the `environment` block of the `portal` service. An optional variable placed only in `deploy/.env` does **not** reach the portal: to change it in production, also add it to the `environment` block of the `portal` service (for example, `WCUI_IDLE_TIMEOUT_MINUTES: "60"`) and recreate the container with `docker compose up -d`.

Secrets live in the environment, never in the repository. `deploy/.env` is ignored by git; use [`deploy/.env.example`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/.env.example) as a template. `install.sh` writes this file with permission `600`.

## Required in production

The composition refuses to start without these six variables: `docker compose` fails early with a clear message, instead of the portal crashing at startup.

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_DOMAIN` | Yes (production composition only) | — | Public domain of the portal. Caddy obtains a Let's Encrypt certificate for it. Not read by the portal. |
| `WCUI_ADMIN_EMAIL` | Yes | empty | Email of the first administrator, provisioned at startup. |
| `WCUI_ADMIN_PASSWORD` | Yes | empty | Initial password of the first administrator. Minimum of 12 characters (`WCUI_PASSWORD_MIN_LENGTH`). |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | Yes (in every environment) | — | Fernet key that encrypts at rest each user's SSH private key and the secrets (environment variables and headers) of the registered MCP servers. The portal does not start without it, nor with a value that is not a valid Fernet key. |
| `WCUI_DATA_PLANE_SECRET` | Yes | empty | Secret shared between the portal and Caddy. `forward_auth` presents it to the internal authorization endpoint; without it, no session is approved. |
| `WCUI_POSTGRES_PASSWORD` | Yes (production composition only) | — | Password of the internal PostgreSQL. The composition assembles `WCUI_DATABASE_URL` from it. Not read directly by the portal. |

Outside the production composition, `WCUI_ADMIN_EMAIL` and `WCUI_ADMIN_PASSWORD` may both be left empty, which disables provisioning of the first administrator. Providing only one of the two is a configuration error and prevents startup.

### Generating the Fernet key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Without the `cryptography` package installed on the host, the equivalents below produce the same format (32 random bytes in urlsafe base64) and are the ones `install.sh` uses:

```bash
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# or, without python3:
openssl rand -base64 32 | tr '+/' '-_'
```

:::caution
Store `WCUI_SSH_KEY_ENCRYPTION_KEY` securely and off the host. Losing it makes it impossible to decrypt the SSH keys and MCP server secrets already encrypted in the database, and a database backup is only useful together with it. The fixed key that appears in `docker-compose.dev.yml` is public and is for development only.
:::

### Generating the secrets

`WCUI_DATA_PLANE_SECRET` and `WCUI_POSTGRES_PASSWORD` are generated the same way:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# or, without python3:
openssl rand -base64 32 | tr '+/' '-_' | tr -d '='
```

Generate each value only once. The PostgreSQL password is written to the `wcui_pg_data` volume on the database's first startup; changing the variable afterwards does not change the password already stored.

## Database

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_DATABASE_URL` | No (set by the production composition) | absent | SQLAlchemy URL, in the format `postgresql+psycopg://usuario:senha@host:5432/banco`. When present, the portal uses the database it points to; when absent or empty, it falls back to the SQLite at `WCUI_DB_PATH`. In production the composition assembles it as `postgresql+psycopg://wcui:<WCUI_POSTGRES_PASSWORD>@postgres:5432/wcui`. |
| `WCUI_DB_PATH` | No | `/data/webcontainerui.db` | Path of the SQLite file, used in development and tests when `WCUI_DATABASE_URL` is not set. |

See [Database](/architecture/database/) and [Backup and restore](/operations/backup-and-restore/).

## TLS proxy and the `Secure` cookie

These variables make the portal trust the headers forwarded by Caddy. Without them, the session cookie is created without the `Secure` flag and the login limiter only sees Caddy's IP. The production composition already sets them; the development one does not, because there is no proxy in front.

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_FORWARDED_ALLOW_IPS` | No | `10.213.0.0/24` | Composition variable: trusted subnet (that of `wcui_net` in the IPAM) allowed to send `X-Forwarded-*`. The composition passes it to the portal as `UVICORN_FORWARDED_ALLOW_IPS`. Not read by the portal under this name. |
| `UVICORN_FORWARDED_ALLOW_IPS` | No (set by the production composition) | value of `WCUI_FORWARDED_ALLOW_IPS` | Read by uvicorn: list of origins from which forwarded headers are accepted. |
| `UVICORN_PROXY_HEADERS` | No (set by the production composition) | `true` in the composition | Read by uvicorn: turns on `ProxyHeadersMiddleware`. |

Only change `WCUI_FORWARDED_ALLOW_IPS` if you change the `wcui_net` subnet, and always together with the composition's `ipam` block. The IPAM is the source of truth; check it with `docker network inspect wcui_net`.

## Session data plane

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_DATA_PLANE_SECRET` | Yes in production | empty | Secret required by the internal endpoint `/internal/data-plane/authorize` (`X-Data-Plane-Secret` header). Empty disables the endpoint, which is the case in development and tests. The composition hands the same value to `caddy` and to `portal`. |
| `WCUI_CADDY_ROUTES_DIR` | No (set by the production composition) | absent; `/data/caddy-routes` in the composition | Shared directory where the portal publishes the session routes that Caddy imports. When absent or empty, publishing is turned off and the portal serves sessions through the in-process proxy. |
| `WCUI_CADDY_CONTAINER` | No (set by the production composition) | `wcui-caddy` | Name or ID of the Caddy container in which the portal runs `caddy reload` after publishing routes. Only used when `WCUI_CADDY_ROUTES_DIR` is set. |
| `WCUI_HEARTBEAT_MIN_SECONDS` | No | `30` | Minimum interval between activity heartbeats accepted per instance. The session view signals while it is open, and the portal does not write more often than this. |

See [Session data plane](/architecture/session-data-plane/).

## Login attempt limiting

The portal limits failed login attempts per account (email) and per origin (IP), with temporary refusal (`429` with `Retry-After`). The state is kept in memory and is reset when the portal restarts; the windows are short. The implementation is in [`backend/app/services/login_throttle.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/services/login_throttle.py).

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_LOGIN_MAX_FAILURES` | No | `10` | Failures that trigger the refusal, per key (account or IP), within the window. |
| `WCUI_LOGIN_WINDOW_SECONDS` | No | `300` | Sliding counting window, in seconds. |
| `WCUI_LOGIN_LOCK_SECONDS` | No | `300` | Duration of the refusal once the threshold is reached, in seconds. |

See [Login hardening](/security/login-hardening/).

## Portal authentication and sessions

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_SESSION_TTL_HOURS` | No | `12` | Lifetime of the login session, in hours. |
| `WCUI_PASSWORD_MIN_LENGTH` | No | `12` | Minimum password length. Also applies to `WCUI_ADMIN_PASSWORD`. |
| `WCUI_SESSION_PURGE_GRACE_HOURS` | No | `24` | Purge grace period: an expired or revoked session is only removed from the database after this period. Minimum `1`. |

## Security headers and interactive documentation

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_DOCS_ENABLED` | No | `false` | Turns on `/docs`, `/redoc` and `/openapi.json`. Off by default so as not to hand the API map to anonymous visitors; useful in development. |

## Instances: idleness and resource limits

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_IDLE_TIMEOUT_MINUTES` | No | `30` | Idle time after which an instance is stopped automatically. |
| `WCUI_REAPER_INTERVAL_SECONDS` | No | `60` | Interval between the sweeps that stop idle instances and purge sessions. |
| `WCUI_ACTIVITY_DEBOUNCE_SECONDS` | No | `30` | Minimum interval between writes of an instance's activity record. |
| `WCUI_DEFAULT_SHM_SIZE_MB` | No | `1024` | Default size of `/dev/shm` per image, in MB. |
| `WCUI_DEFAULT_MEM_LIMIT_MB` | No | `2048` | Default memory limit per image, in MB. |
| `WCUI_DEFAULT_CPU_LIMIT` | No | `2.0` | Default CPU limit per image, in cores. |
| `WCUI_PUID` | No | `1000` | Value of `PUID` passed to the instance containers: UID of the user in the desktop images and owner of the files the portal injects into them. Agent images run as root. |
| `WCUI_PGID` | No | `1000` | Value of `PGID` passed to the instance containers, with the same role for the GID. |
| `WCUI_TIMEZONE` | No | `Etc/UTC` | Time zone (`TZ`) of the instance containers. |

The three resource limits apply to catalog entries registered without an explicit limit; each entry stores its own values, which the administrator can edit per image.

## Docker: network and names

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_DOCKER_NETWORK` | No (set by the compositions) | `wcui_net` | Docker network to which the portal connects the instance containers. The development composition uses `wcui_net_dev`. |
| `WCUI_VOLUME_PREFIX` | No | `wcui` | Prefix of the user volume names (`<prefixo>-u<usuário>-i<imagem>`). |
| `WCUI_CONTAINER_PREFIX` | No | `wcui` | Prefix of the instance container names (`<prefixo>-<id>`). |

:::caution
Changing `WCUI_VOLUME_PREFIX` or `WCUI_CONTAINER_PREFIX` in a deploy already in use makes the portal look for volumes and containers under other names: the users' existing data is no longer found. Set these values only on a fresh installation.
:::

## Files and content limits

| Variable | Required? | Default | Effect |
|---|---|---|---|
| `WCUI_FRONTEND_DIST` | No | `/app/frontend/dist` | Directory of the front-end build served at `/`. If the directory does not exist, the portal starts without a front end. |
| `WCUI_UPLOADS_DIR` | No | `/data/uploads/images` | Directory of the cover images uploaded by the administrator. It sits under the volume mounted at `/data`. |
| `WCUI_MAX_ICON_UPLOAD_MB` | No | `5` | Maximum size of an uploaded cover image, in MB. |
| `WCUI_MAX_AGENTS_MD_BYTES` | No | `262144` | Maximum size of the content of an AGENTS.md document in the library, in bytes. |

## Values in the development composition

The [`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml) composition sets five variables with fixed values and requires none from the operator:

| Variable | Value in development |
|---|---|
| `WCUI_DB_PATH` | `/data/webcontainerui.db` |
| `WCUI_DOCKER_NETWORK` | `wcui_net_dev` |
| `WCUI_ADMIN_EMAIL` | `admin@local.test` |
| `WCUI_ADMIN_PASSWORD` | fixed, public value defined in the file |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | fixed, public key defined in the file |

It does not set `WCUI_DATABASE_URL`, `WCUI_DATA_PLANE_SECRET`, `WCUI_CADDY_ROUTES_DIR` or the `UVICORN_*` variables: in development the database is SQLite, the external data plane is off and forwarded headers are ignored.
