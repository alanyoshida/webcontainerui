---
title: Installation
description: Production installation guided by install.sh, with the prerequisites and what the script asks for, generates and runs.
sidebar:
  order: 3
sourceHash: ca8211f50af3d467ff6d3bf0cb2a5f051be085d089ab3497b738d8e6950f287a
---

Production installation is guided by the [`install.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/install.sh) script, at the repository root. It checks the prerequisites, collects the required configuration, writes `deploy/.env` and brings up the production composition: Caddy, portal and PostgreSQL.

:::danger[Read before deploying]
The portal process is equivalent to root on the host, and each user has root inside their own desktop. Read [Trust surface](/security/trust-surface/) before exposing the portal beyond your own machine.
:::

## Prerequisites

- A Linux host with Docker and the Docker Compose v2 plugin.
- The Docker daemon running and accessible to the user who runs the script (for example, through membership in the `docker` group).
- A domain already pointing to the host. Caddy obtains the Let's Encrypt certificate automatically, which requires ports 80 and 443 on the host to be free and reachable from the internet.
- `python3` or `openssl`, used to generate the secrets. The script prefers `python3` and falls back to `openssl` when it is not available.

## Install

```bash
git clone https://github.com/alanyoshida/webcontainerui.git webcontainerui
cd webcontainerui
./install.sh
```

`./install.sh --help` (or `-h`) prints the usage summary and exits.

## What the script does

### 1. Checks the prerequisites

The script exits with an error if the `docker` command does not exist, if `docker compose version` fails or if `docker info` cannot talk to the daemon.

### 2. Collects the configuration

If `deploy/.env` already exists, its values are loaded first. Then each variable that is still empty is either prompted for or generated:

| Variable | Source | Rule |
|---|---|---|
| `WCUI_DOMAIN` | Prompted | Required; the portal's public domain |
| `WCUI_ADMIN_EMAIL` | Prompted | Required; email of the first administrator |
| `WCUI_ADMIN_PASSWORD` | Prompted, without echo | Minimum of 12 characters; the prompt repeats until the password is accepted |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | Generated | Fernet key (32 random bytes in urlsafe base64) that encrypts SSH identities at rest |
| `WCUI_POSTGRES_PASSWORD` | Generated | Password for the internal PostgreSQL |
| `WCUI_DATA_PLANE_SECRET` | Generated | Secret shared between the portal and Caddy for `forward_auth` |

:::caution[Keep the encryption key safe]
Losing `WCUI_SSH_KEY_ENCRYPTION_KEY` makes it impossible to decrypt the SSH keys already encrypted in the database. Include `deploy/.env` in your backup routine, and treat it as a secret.
:::

### 3. Writes `deploy/.env`

The six variables are written to `deploy/.env`, with permission `600`. The file is ignored by git. The script then displays a summary, hiding the password and the secrets.

### 4. Asks for confirmation and brings up the composition

Before bringing anything up, the script warns that it will build the image, expose ports 80 and 443 on the host and request the certificate for the given domain, and asks `Continuar? [s/N]` (Continue? [y/N]). Any answer other than `s` or `y` cancels the startup; the configuration in `deploy/.env` is kept for the next run.

Once confirmed, the script runs:

```bash
cd deploy && docker compose up -d --build
```

At the end, the portal is available at `https://<your-domain>` as soon as DNS and the certificate have propagated.

## First access

Sign in with the email and password of the first administrator. From there:

1. In the admin panel, follow the build of the agent images and the download of the default desktop images. Register other images if you want.
2. Create users and groups.
3. Grant the groups access to the images. A user with no group has access to no image at all.

Then go through the [post-deploy checklist](/operations/post-deploy-checklist/).

## Update

Running `./install.sh` again, for example after a `git pull`, reuses the `deploy/.env` already written, does not repeat the questions already answered, and only rebuilds and restarts the containers.

```bash
git pull
./install.sh
```

:::caution
Back up the database before updating to a version that changes the schema. See [Backup and restore](/operations/backup-and-restore/) and [Rollback](/operations/rollback/).
:::

## Non-interactive installation

The variables `WCUI_DOMAIN`, `WCUI_ADMIN_EMAIL`, `WCUI_ADMIN_PASSWORD`, `WCUI_SSH_KEY_ENCRYPTION_KEY`, `WCUI_DATA_PLANE_SECRET` and `WCUI_POSTGRES_PASSWORD`, when already exported in the environment, skip the corresponding prompt or generation. If `WCUI_ADMIN_PASSWORD` comes from the environment with fewer than 12 characters, the script exits with an error instead of prompting.

When `deploy/.env` already exists, it is loaded after the environment: the values written in it take precedence over the exported ones. To change a value in an existing installation, edit the file.

The final confirmation (`Continuar? [s/N]`) is always read from standard input; in automated provisioning, supply the answer through it:

```bash
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="senha com pelo menos 12 caracteres"
echo s | ./install.sh
```

## Prefer to do it by hand?

If you prefer to configure things without the script, or need the optional variables, the startup order is in [Manual deployment](/operations/manual-deployment/) and the full list is in [Environment variables](/operations/environment-variables/).
