---
title: Login hardening
description: How the portal protects login and the session — forwarded headers, attempt limiter, password hash, cookie and HTTP headers — and the trade-offs taken on.
sidebar:
  order: 3
sourceHash: 76980725e2d078e68f7001afad5cb1d531d3724a0c238bd186ae1a79ed4d7b86
---

Login is the entry door to a root shell inside the container network (see [Trust surface](/security/trust-surface/)). This page describes the controls around it: whom the portal trusts to learn the scheme and the IP of the request, how failed attempts are limited, how password and session are stored, and which security headers the responses carry. Each control comes with what it leaves out.

## Forwarded headers and subnet allowlist

In production Caddy terminates TLS and speaks HTTP to the portal over the internal network. To know that the client used HTTPS and what its real IP is, the portal depends on `X-Forwarded-Proto` and `X-Forwarded-For`. Without them the portal would always see itself as `http` — and the session cookie would be issued without `Secure` — and the login limiter would only see Caddy's IP.

The portal only honors these headers when they come from IPs in the `UVICORN_FORWARDED_ALLOW_IPS` allowlist, matched to the fixed subnet of `wcui_net` in the Compose file's IPAM — not `*`:

```yaml
# deploy/docker-compose.yml (excerpt)
services:
  portal:
    environment:
      UVICORN_PROXY_HEADERS: "true"
      UVICORN_FORWARDED_ALLOW_IPS: ${WCUI_FORWARDED_ALLOW_IPS:-10.213.0.0/24}

networks:
  wcui_net:
    name: wcui_net
    ipam:
      config:
        - subnet: 10.213.0.0/24
```

In production the practical effect of `*` would be close (every connection arrives over the internal network), but the explicit subnet does not extend trust to future ports or origins.

:::caution[The allowlist must match the real subnet]
If you change the subnet of `wcui_net`, adjust `WCUI_FORWARDED_ALLOW_IPS` along with it. When the two diverge, the failure is silent: login works, but the cookie goes out without `Secure`. The [Post-deploy checklist](/operations/post-deploy-checklist/) has the two-minute check that catches this case.
:::

### What a forger inside the subnet can achieve

Instance containers are on the same subnet, and therefore inside the allowlist. A user, from inside their own container, can talk directly to the portal at `portal:8000` and forge the headers. What they gain from that:

- Announcing `X-Forwarded-Proto: https`: the only effect is that the cookie gets `Secure` — harmless.
- Rotating `X-Forwarded-For`: it splits the login limiter's **per-IP** counter, and makes the forged IP appear in the `ip` field of the [event trail](/security/audit-log/).

That is why the main line of limiting is the **per-account** bucket (normalized e-mail), which does not depend on any header; the per-IP bucket is best-effort behind a proxy. And that is why the `ip` field of the trail must be read as "what the trusted proxy reported", not as proof of origin when the request may have come from inside the internal network.

### HSTS

The edge sends `Strict-Transport-Security: max-age=31536000`. With the cookie marked `Secure`, this eliminates the downgrade to HTTP as a vector for cookie theft by an attacker on the network. The directive includes neither `includeSubDomains` nor `preload`: the domain may host other services, and aggressive HSTS is hard to reverse. Each deployment decides whether it wants to go further, by editing the `Caddyfile`.

In development there is no Caddy and no TLS: the portal responds at `http://127.0.0.1:8000`, the cookie goes out without `Secure` and there is no HSTS. This is expected and is one of the reasons why the development Compose file only publishes the port on `127.0.0.1`.

## Login attempt limiter

Failed login attempts are counted in a sliding window, under two independent keys:

- **per account** — the normalized e-mail (no leading or trailing whitespace, lowercase), so that case variations do not split the counter;
- **per IP** — the client's origin as the portal sees it.

Once the threshold is exceeded on either of the two keys, the portal responds `429` with `Retry-After` to every new attempt on that key, for the refusal period.

| Variable | Default | Meaning |
|---|---|---|
| `WCUI_LOGIN_MAX_FAILURES` | `10` | Failures within the window that trigger the refusal |
| `WCUI_LOGIN_WINDOW_SECONDS` | `300` | Size of the sliding window |
| `WCUI_LOGIN_LOCK_SECONDS` | `300` | Duration of the refusal |

Behavior details:

- The limiter is consulted **before** any database access or Argon2 computation. The refusal is identical for an existing and a nonexistent account (it does not become an enumeration oracle) and spares the CPU cost of the hash, which would be an exhaustion vector.
- The attempt that reaches the threshold is still processed; the next one meets the refusal.
- A successful login resets only the account key. The IP key remains, to contain the attempt of one same password against several accounts from one same address.
- Once the refusal expires, the key starts again from zero.
- Attempts against a disabled account also count as a failure.
- Each refusal generates an `auth.login.throttled` event in the [event trail](/security/audit-log/).

### Trade-off of the per-account limiter

Once the failure threshold is exceeded, the refusal (`429`) applies to any attempt during the window — **including with the correct password**: verifying the password while under refusal would become an oracle.

:::caution[Temporary denial of service is an accepted consequence]
An attacker can keep a victim's account "locked" by renewing failures — knowing the e-mail is enough. The mitigation is that the refusal is short and configurable (`WCUI_LOGIN_LOCK_SECONDS`, default 300s), never permanent. It is the same trade-off as any per-account limiter. There is no manual unlock mechanism other than waiting for the refusal to expire or restarting the portal.
:::

### Limits of the limiter

- **The state lives in memory**, in the portal process (which runs with a single worker). Restarting the portal resets the counts and the refusals. For five-minute windows this is acceptable, but it means the limiter is not a durable record of attacks — the event trail is.
- **There is no increasing delay** and no permanent block. A patient attacker sustains about ten attempts every five minutes per account, indefinitely. Strong passwords remain the real defense against slow brute force.
- **The per-IP bucket can be bypassed** by whoever controls the `X-Forwarded-For` header from inside the internal network, as described above.
- **There is no second factor** and no integration with an external identity provider.

Specification: [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md).

## Password hash

Passwords are stored only as an Argon2 hash (`argon2-cffi` library, default `PasswordHasher` parameters), with a per-password salt. There is no plaintext password and no reversible encryption.

- Minimum length: 12 characters (`WCUI_PASSWORD_MIN_LENGTH`). The portal refuses to start if the first administrator's password is shorter than that. There are no other composition rules and no check against lists of leaked passwords.
- The first administrator is provisioned from `WCUI_ADMIN_EMAIL` and `WCUI_ADMIN_PASSWORD` only when the database is empty; a second boot never overwrites the existing password.

### Indistinguishable response across the failure cases

Nonexistent e-mail, wrong password and disabled account produce the same response (`401`, same message) and the same CPU cost:

- for a nonexistent e-mail, the portal verifies the password against a reference hash, so that Argon2 runs anyway;
- for a disabled account, the password is verified **before** the disabled check, so that the response time does not distinguish this case from the others.

This closes account enumeration by body and by response time. It does not close enumeration through other channels your environment may offer (e-mail invitations, for example — the portal sends none).

## Session tokens

- The token is generated with `secrets.token_urlsafe(32)` — 256 bits of entropy.
- The database stores only the SHA-256 of the token. The cleartext value exists only at the moment of creation, to go into the cookie.
- Validity: 12 hours (`WCUI_SESSION_TTL_HOURS`). There is no sliding renewal; once the period is over, you have to sign in again.
- Logout revokes the session on the server: the same token stops authenticating immediately.
- Disabling an account revokes all of its sessions, and a session of a disabled account is refused even if it has not been revoked.
- Sessions expired or revoked for longer than the grace period (`WCUI_SESSION_PURGE_GRACE_HOURS`, default 24h) are removed from the database by the portal's periodic cycle. Active sessions are never touched.

The `wcui_session` cookie is issued with:

| Attribute | Value | Effect |
|---|---|---|
| `HttpOnly` | always | Page scripts do not read the token |
| `SameSite` | `Lax` | Does not accompany third-party requests that change state |
| `Secure` | when the portal sees itself on HTTPS | Does not travel over plain HTTP |
| `Path` | `/` | Applies to the portal and to `/i/{uuid}/` |
| `Max-Age` | equal to the session TTL | Expires together with the session |

What this leaves out:

- **There is no limit on simultaneous sessions per user** and no screen for the user to list and end their own sessions on other devices.
- **The cookie applies to `/i/{uuid}/`**, which serves content coming from the user's container on the same origin as the portal. `HttpOnly` prevents reading the token, but does not prevent a script served by the container from making authenticated requests to the API on the user's behalf. This is finding M3, accepted by project decision — see [Audits](/security/audits/).
- **CSRF protection** depends on `SameSite=Lax` and on the absence of permissive CORS; there is no dedicated anti-CSRF token.

## HTTP security headers

Every response generated by the portal itself — interface, API and uploads — carries:

```http
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: SAMEORIGIN
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'
```

Decisions built into this policy, and what they cost:

- `script-src 'self'`: no inline or third-party scripts. The front end is served entirely by the portal, with no CDN.
- `style-src 'unsafe-inline'`: a requirement of MUI/Emotion, which injects `<style>` at runtime. Injected inline style remains possible.
- `connect-src 'self' ws: wss:`: the `ws:` and `wss:` schemes are allowed for any host, not only for the portal's own origin.
- `X-Frame-Options: SAMEORIGIN` and `frame-ancestors 'self'`, instead of `DENY`: the portal itself embeds the session in a same-origin iframe. Third-party sites cannot frame the portal.

:::caution[`/i/{uuid}/` does not receive these headers]
The responses of the session path come from the user's container and pass through without the portal's headers: imposing the portal's policy would break the desktop and terminal interfaces. In production these responses do not even go through the portal — they go from the container to the client via Caddy. Therefore the embedded content runs on the portal's origin **without CSP**. The CSP above limits what the portal's front end loads; it does not contain what a container serves.
:::

At the edge, Caddy removes the `Server` header from responses, so as not to advertise the stack, and adds HSTS. In development, without Caddy, `Server: uvicorn` still appears.

Specification: [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md).

## Interactive documentation turned off

`/docs`, `/redoc` and `/openapi.json` are turned off by default and respond `404`, including when the front end is being served by the portal (the paths do not fall into the single-page application's catch-all). This way the complete map of the API, including the admin routes, is not handed to anonymous users.

To turn it on in development:

```bash
export WCUI_DOCS_ENABLED=true
```

Do not turn it on in production. The routes would remain protected by session and by role, but there is no reason to publish their inventory. The data plane's internal endpoint never appears in the schema, whether the documentation is on or not.

## Where to check in the code

| Control | File |
|---|---|
| Login route, order of the checks, cookie | `backend/app/api/auth.py` |
| Limiter | `backend/app/services/login_throttle.py` |
| Password hash | `backend/app/services/passwords.py` |
| Session creation, resolution, revocation and purge | `backend/app/services/sessions.py` |
| Configurable defaults | `backend/app/config.py` |
| Security headers and interactive documentation | `backend/app/main.py` |
| Forwarded headers allowlist and subnet | `deploy/docker-compose.yml` |
| HSTS and removal of `Server` | `deploy/Caddyfile` |

The full list of variables is in [Environment variables](/operations/environment-variables/).
