---
title: Post-deploy checklist
description: Checks to run after bringing up or updating the portal in production, with the commands for each one.
sidebar:
  order: 5
sourceHash: 61485c6c22fae39d70d7778777d38f3c41d63b5f5ea6993d82baef00b2ec8be9
---

Run this checklist after every startup or update in production. The first two checks take two minutes and catch the two silent failures in the login area: HSTS missing at the edge and a session cookie without the `Secure` flag. Neither causes a visible error — the portal works normally, just less protected. The remaining ones confirm that the composition came up as expected.

The commands assume the `deploy/` directory and the `WCUI_DOMAIN` variable set in the shell.

## 1. HSTS present at the edge

```bash
curl -sI https://$WCUI_DOMAIN | grep -i strict-transport-security
```

Expected result:

```text
strict-transport-security: max-age=31536000
```

The header is added by Caddy. If the command prints nothing, the `Caddyfile` in use is not the one from the repository or the response is not coming from Caddy.

## 2. Session cookie with `Secure`

Log in through the API and inspect the `Set-Cookie` header. Replace `...` with the administrator's password:

```bash
curl -sD - -o /dev/null -X POST https://$WCUI_DOMAIN/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$WCUI_ADMIN_EMAIL\",\"password\":\"...\"}" | grep -i set-cookie
```

The `Set-Cookie` must contain the `Secure` attribute.

:::caution
If the `Set-Cookie` comes back without `Secure`, `UVICORN_FORWARDED_ALLOW_IPS` does not match the real subnet of `wcui_net`. Check the subnet with the command below; the composition's IPAM is the source of truth.

```bash
docker network inspect wcui_net
```

Set `WCUI_FORWARDED_ALLOW_IPS` to the subnet shown (or fix the IPAM) and recreate the portal. See [Environment variables](/operations/environment-variables/).
:::

:::note
Avoid leaving the password in the shell history. Every attempt with a wrong password counts toward the login limiter, described in [Login hardening](/security/login-hardening/).
:::

## 3. Services up and healthy

```bash
docker compose ps
```

The three services (`postgres`, `portal` and `caddy`) must be running, with `postgres` and `portal` marked as `healthy`.

## 4. Internal endpoint closed at the edge

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://$WCUI_DOMAIN/internal/data-plane/authorize
```

Expected result: `404`. The data plane authorization endpoint can only be reached from inside the internal network.

## 5. Interactive documentation off

With the default `WCUI_DOCS_ENABLED=false`, the paths `/docs`, `/redoc` and `/openapi.json` answer `404`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://$WCUI_DOMAIN/openapi.json
```

Expected result: `404`.

## 6. Catalog and first session

- Sign in to the portal with `WCUI_ADMIN_EMAIL` and `WCUI_ADMIN_PASSWORD`.
- In the "Catálogo" (Catalog) tab of the admin panel, follow the pull and build of the images. They run in the background and, on the first deploy, add up to several GB.
- Create groups and users and grant the images to the groups. A user only sees an image granted to a group they belong to.
- Start an instance and open the session. With it open, check the routes published in the data plane:

```bash
docker exec wcui-caddy ls /etc/caddy/caddy-routes
```

The expected result is one file per instance in the `running` state, plus `000-placeholder.caddy`. If the session gets stuck on "carregando" (loading), follow the diagnosis in [Manual deployment](/operations/manual-deployment/).

## 7. Backup and secrets stored

- Take the first database backup and confirm that the file is not empty — see [Backup and restore](/operations/backup-and-restore/).
- Store `deploy/.env` off the host, in particular `WCUI_SSH_KEY_ENCRYPTION_KEY`: without it, a restored backup cannot decrypt the users' SSH keys.
- Reread [Trust surface](/security/trust-surface/) before opening the portal to other users.
