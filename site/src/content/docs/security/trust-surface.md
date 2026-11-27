---
title: Trust surface
description: What the portal can do on the host, what the user can do inside their own desktop, and why neither of the two can be worked around by configuration.
sidebar:
  order: 1
sourceHash: 6f8c9554962aaace9ee55fcd80534fa66a0b4fcd4de2e8d21894f0b4a05a8d46
---

This page describes, without softening, what you start trusting when you install WebContainerUI. There are two structural facts, which follow from what the product does and not from an implementation oversight: the portal process has authority equivalent to root on the host, and each user has root inside their own desktop. Read it before deploying and before exposing the portal beyond your own machine.

:::danger[The portal is equivalent to root on the host]
The portal needs the Docker socket (`/var/run/docker.sock`) to create the desktop and agent containers. Whoever can create a container can mount the host's filesystem inside it. Compromising the portal process is compromising the host.
:::

## The portal is equivalent to root on the host

The Compose file mounts the Docker socket inside the portal container. There is no mode of operation without it: creating, starting, stopping and removing containers is the system's core function.

The consequence is direct. A code execution vulnerability in the portal, the leak of an administrator session combined with an authorization flaw, or write access to the portal image give the attacker the same power the Docker daemon has — which, in the default installation, is root on the host.

### Why `socket-proxy` does not mitigate this case

A common mitigation for "don't give the Docker socket directly to a process" is to put a `socket-proxy` in front of it, filtering which Docker API calls get through. That **does not work here**.

The portal needs to create containers (`POST /containers/create`) to meet the product's core requirement. Any permission that allows creating a container also allows creating a container with a bind mount of the host's `/`:

```text
  socket-proxy with CONTAINERS=1, POST=1
        |
        +--> allows container create
                 |
                 +--> allows -v /:/host
                          |
                          +--> root on the host again
```

In other words: the minimum surface the portal needs in order to work is exactly the surface that, in the hands of whoever controls it, is equivalent to root on the host. A `socket-proxy` restrictive enough to block that would also block the creation of desktop containers, which is the system's function.

## What this means in practice

**The portal process is a trusted component of the control plane.** Not a sandbox, not a process isolated from the host — a process that, by product necessity, has authority equivalent to root on the host via Docker.

This implies:

- No user code runs inside the portal process. It only orchestrates containers; it does not interpret or execute anything that comes from the end user.
- Every command the portal executes inside a container (`docker exec`) is fixed in the code — for example the removal of `/config/AGENTS.md` and the data plane's `caddy reload`. None of them is assembled from user input.
- The portal image is minimal, to reduce the surface of a possible vulnerability in the application itself.
- The portal's database is treated as being as sensitive as the Docker socket — whoever reads one effectively reaches the other (see below).
- Backups, host access and credential rotation for the environment where the portal runs must follow the same policy as a host that holds administrator secrets, not that of an ordinary user application.

The project's other mitigations — instance containers with no published port, an internal credential per instance, Selkies sharing links turned off — reduce what a user reaches from their own container. They are described in [Isolation layers](/security/isolation-layers/). None of them reduces the portal's authority over the host.

## The user has root inside their own desktop

The LinuxServer.io webtop images ship a terminal with passwordless `sudo`. Whoever has a desktop session has root inside that container. The coding agent images execute, by definition, arbitrary commands chosen by the user and by the AI agent.

The LinuxServer documentation advises treating a session like an SSH login to a machine on your network. In practice:

- Giving a user access to a catalog image is giving them a Linux machine with root, inside your internal container network, with outbound access to wherever the host has outbound access.
- Root inside the container is not root on the host: instance containers are created without privileged mode, without additional capabilities and without a host bind mount — only the instance's own named volume, mounted at `/config`. A container escape (a flaw in the kernel or in the runtime) would break that boundary, as in any use of Docker.
- Selkies' native sharing links would grant full control of the session — including the terminal with `sudo` — with no authentication of their own. The portal turns them off in every instance (`SELKIES_ENABLE_SHARING=false`, `SELKIES_ENABLE_SHARED=false`).
- What a container reaches on the internal network, and what prevents it from entering another user's session, is in [Isolation layers](/security/isolation-layers/). One relevant open point — all instances share the same Docker network — is recorded in [Audits](/security/audits/).

:::caution
Do not expose the portal to the internet without robust authentication in front of it. The portal's login has an attempt limiter and a protected cookie (see [Login hardening](/security/login-hardening/)), but it has no second factor and no identity provider integration. A leaked user password is a root shell inside your container network; a leaked administrator password is control of the catalog, of the users and of everything the portal propagates to the instances.
:::

## Database sensitivity

In production the database is PostgreSQL, running as a service of the Compose file on the internal network `wcui_net`, with no port published on the host — only the portal reaches it. In development and tests it is an SQLite file on the `/data` volume. Engine and migration details are in [Database](/architecture/database/).

The database stores:

- password hashes (Argon2) and session token hashes (SHA-256);
- the users' SSH private keys, encrypted with Fernet;
- environment variables and headers of the MCP servers, encrypted with the same Fernet key;
- the internal credential of each instance (the random username and password the container requires) — this one in cleartext, because the portal needs to present it on every forwarded request.

Whoever reads the database does not obtain user passwords or private keys in cleartext (as long as they do not also have `WCUI_SSH_KEY_ENCRYPTION_KEY`), but does obtain the instances' internal credentials and enough material for offline attacks against the hashes. Whoever **writes** to the database can promote themselves to administrator. Therefore:

- Treat backups (`pg_dump`) with the same policy as the Docker socket. The procedure is in [Backup and restore](/operations/backup-and-restore/).
- The database credential comes from `WCUI_POSTGRES_PASSWORD`, in the environment, never in the repository; the full URL is assembled in the Compose file. See [Environment variables](/operations/environment-variables/).
- The database password is not used by any instance container; it exists only in the portal process and in the `postgres` service.
- Keep the Fernet key separate from the database backups. A backup accompanied by the key is equivalent to the SSH private keys of all users and the secrets of all MCP servers.
- The portal only starts after the database healthcheck; a database that is down prevents the portal from coming up — an explicit failure, with no partial state.

:::note
The database sits on the same internal network in which the instance containers are created. A user, from inside their own container, can reach the PostgreSQL port; what separates them from the data is the database password. Use a long, random value for `WCUI_POSTGRES_PASSWORD`, as the installer generates.
:::

## What to do with this information

- Run the portal on a host dedicated to it, or on a host whose compromise you accept treating as a total compromise.
- Restrict who has administrator access to the portal the way you would restrict who has `sudo` on the host.
- Grant images to groups bearing in mind that each grant hands over a root shell on the internal network.
- Before opening the portal beyond your machine, follow [Manual deployment](/operations/manual-deployment/) and go through the [Post-deploy checklist](/operations/post-deploy-checklist/).
- Read [Audits](/security/audits/) to know what has already been tested, what was fixed and what remains open.
