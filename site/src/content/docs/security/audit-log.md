---
title: Security event trail
description: Format, fields and catalog of the security events the portal emits, what is never recorded and who is responsible for retention.
sidebar:
  order: 4
sourceHash: a276141857857c280f87426fe67138a1cf494986afc7a43251b2974f0d2534e5
---

The portal emits a structured record for each relevant security event: who did what, from where and with what outcome. The trail exists for detection and forensics — knowing that there was a burst of failed logins, which administrator revoked a grant, when an instance was deleted. It is deliberately simple: JSON lines on standard output, with no database table and no additional dependency.

## Format

An event is a JSON line on the portal's standard output, capturable with `docker logs` on the portal container or by the operator's collector (Loki, Vector, CloudWatch and the like):

```bash
docker logs deploy-portal-1 2>&1 | grep '"event"'
```

```json
{"event": "auth.login", "actor_id": 1, "actor_email": "a@x.test", "ip": "203.0.113.9", "outcome": "success"}
```

The container name depends on the Compose project name; check it with `docker ps`.

The line is pure JSON, with no prefix. **There is no timestamp inside the event**: the time comes from Docker's log driver (`docker logs --timestamps`) or from the collector. If your collector discards the ingestion time, the events are left without a date.

## Fields

| Field | Presence | Content |
|---|---|---|
| `event` | always | Event name, from the catalog below |
| `actor_id` | when there is a session | Numeric identifier of who acted |
| `actor_email` | when there is a session or a login attempt | E-mail of who acted; on login failures, the e-mail that was **attempted** |
| `ip` | when available | Client IP as the portal sees it |
| `target` | when the action has an object | Object of the action: instance id, user e-mail, image `repository:tag`, group |
| `outcome` | always | `success`, `failure` or `denied` |
| `detail` | optional | Short text, for example `op=criar` or `retry_after=287s` |

About each one:

- `actor_id` and `actor_email` come from the authenticated session. In internal system events, with no user behind them — such as a provisioning failure —, they are absent.
- On login failures, `actor_email` is the text the client sent, without normalization. It is not proof that the account exists.
- `ip` is the client's real IP only behind a trusted proxy, that is, when the request arrives through Caddy and the `UVICORN_FORWARDED_ALLOW_IPS` allowlist is correct. A request made from inside the internal network can forge this value. See [Login hardening](/security/login-hardening/).
- `detail` is truncated when it carries an error message (300 characters).

## Event catalog

### Authentication

| Event | Outcome | When |
|---|---|---|
| `auth.login` | `success` | Login accepted |
| `auth.login` | `failure` | Nonexistent e-mail, wrong password or disabled account — the three indistinguishable, on purpose |
| `auth.login.throttled` | `denied` | Attempt refused by the limiter, without credential verification; `detail` carries the wait time |
| `auth.logout` | `success` | Logout of a valid session |

### Administration

| Event | When |
|---|---|
| `admin.user.created` | User created; `detail` indicates whether it is an administrator |
| `admin.user.disabled` | Account disabled (and its sessions revoked) |
| `admin.group.changed` | Group created, renamed or deleted; member added or removed |
| `admin.grant.changed` | Image granted to a group |
| `admin.grant.revoked` | Grant revoked; `detail` carries how many instances were affected |
| `admin.image.changed` | Catalog entry created, edited, updated, enabled, disabled, with its cover replaced or with its download repeated |
| `admin.document.changed` | `AGENTS.md` document created, edited, deleted or linked to an image |
| `admin.mcp.changed` | MCP server created, edited, deleted, linked or unlinked |
| `admin.skill.changed` | Skill created, edited, deleted, linked or unlinked |

All of them have the administrator as actor and `outcome` equal to `success`; the specific operation goes in `detail` (`op=criar`, `op=editar`, `op=excluir` and so on).

### Instances

| Event | Outcome | When |
|---|---|---|
| `instance.created` | `success` | Owner created an instance; `detail` carries the image |
| `instance.updated` | `success` | Owner updated the instance to the current version of the image |
| `instance.stopped` | `success` | Owner stopped the instance |
| `instance.deleted` | `success` | Owner deleted the instance |
| `instance.failed` | `failure` | Failure to create or start the container; no actor, with the truncated error in `detail` |

### Data plane

| Event | Outcome | When |
|---|---|---|
| `data_plane.reload` | `failure` | The `caddy reload` triggered by the portal after publishing or withdrawing a route failed |

This event is operational, not an authentication event, but it goes out through the same channel: a reload that fails means a session route may not have been applied — or, more importantly, **withdrawn**. It is worth an alert.

## What the trail does not cover

The current coverage is that of the tables above, and it has known gaps. Do not assume that the absence of an event means the absence of an action.

- **Attempts denied by authorization are not recorded.** An ordinary user hitting an admin route (`403`) or requesting someone else's instance (`404`) generates no event. Only the login limiter emits `denied`.
- **Administrative operations are only recorded when completed.** An attempt that fails on validation or conflict does not appear.
- **Automatic stops do not emit `instance.stopped`.** An instance stopped for idleness, by state reconciliation or as an effect of a grant revocation generates no event of its own; the revocation records only the count in `admin.grant.revoked`.
- **Regeneration of the SSH identity is not recorded.**
- **Access to sessions is not recorded.** Opening `/i/{uuid}/`, each data plane authorization and the session content are outside the trail. What the user does inside the container is not visible to the portal.
- **Reads are not recorded.** Listing users, querying usage metrics or reading a document generates no event.
- **The trail is best-effort.** Emission is not transactional with the action: if the process dies between the action and the write, the event is lost. And standard output has no protection against tampering — whoever has access to the host or to the Docker daemon can delete or alter the logs.

If your environment requires a complete access trail, also record Caddy's access log at the edge.

## What is never recorded

No event carries a secret. Password, session token, internal instance credential, SSH private key and values of MCP server environment variables or headers never pass through the emitter (`backend/app/services/audit_log.py`).

The guarantee is by construction of the emission points: the emitter only receives explicitly named fields, and no caller passes these values. There is no filter that removes secrets from arbitrary text. Two points of attention follow from this:

- `instance.failed` and `data_plane.reload` copy into `detail` up to 300 characters of the Docker or Caddy error message. These messages do not usually contain secrets, but they are not controlled by the portal.
- On login failures, the attempted e-mail is recorded as it came. A user who types their password into the e-mail field by mistake will have that text written to the log.

The trail contains personal data — e-mails and IP addresses. Treat the destination of the logs accordingly.

## Retention and rotation

The portal only writes to standard output. Retention and rotation are the responsibility of Docker's log driver or of the external collector.

:::caution[The Compose file does not configure rotation]
The production Compose file does not define log options for the portal service. With the default `json-file` driver without `max-size`, the container's log file grows without limit, and the events disappear when the container is removed and recreated (which happens on every update). If the trail matters to you, configure both things: rotation and shipping off the host.
:::

Example of local rotation, to be added to the `portal` service in the Compose file:

```yaml
services:
  portal:
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "10"
```

Local rotation limits disk usage, but it also limits the history and does not protect the trail from whoever compromises the host. For forensics, send the events to a collector on another machine.

## Useful queries

Login failures and limiter refusals, with time:

```bash
docker logs --timestamps deploy-portal-1 2>&1 \
  | grep -E '"event": "auth\.login(\.throttled)?"' \
  | grep -E '"outcome": "(failure|denied)"'
```

Everything an administrator changed:

```bash
docker logs --timestamps deploy-portal-1 2>&1 | grep '"event": "admin\.'
```

Specification: [security-audit-log](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md).
