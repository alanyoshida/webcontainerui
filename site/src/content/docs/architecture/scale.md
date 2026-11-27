---
title: Scale target
description: Where the limit on concurrent sessions lies, the order of magnitude expected on a dedicated host, and the caveat that the numbers are an estimate.
sidebar:
  order: 5
sourceHash: f64d04a33ec1fa61e7984a7648f54b95a271c78c4f5614f6770698900da74ee0
---

With the data plane in Caddy, the ceiling on concurrent sessions is no longer the portal process. The limit becomes the **Docker host**: the CPU and RAM of each desktop and the bandwidth of the link.

:::caution[Estimate, not measurement]
The numbers on this page are an architectural estimate. Validate with real load, on your hardware and with your usage profile, before promising a ceiling.
:::

## Order of magnitude

On a dedicated machine with 32 vCPUs, 64 GB of RAM and a 1 Gbps link, the order of magnitude is **about 60 to 100 active sessions**. The number is dominated by the CPU and RAM of the containers: each webtop uses 1 to 2 GB and part of a core in real use.

Caddy forwards thousands of WebSocket connections without being the bottleneck.

## What limits each component

| Component | Role under load | Practical limit |
|---|---|---|
| Instance containers | Run the desktops and the agents | Host CPU and RAM; this is the dominant factor |
| Network link | Carries the video of desktop sessions | Available bandwidth |
| Caddy | Carries the session frames | Not a bottleneck at this order of magnitude |
| Portal | Decides authorization and orchestrates containers | Does not carry frames |

The portal still runs with **one worker** and uses `aiodocker` with no blocking calls. Data plane authorization is one short call per HTTP request; the WebSocket channel opens once and is not authorized per frame. The mechanism is described in [Session data plane](/architecture/session-data-plane/).

## Per-instance limits

Each catalog entry defines the resource limits of the containers created from it. The defaults for a new entry are:

| Resource | Default | Variable |
|---|---|---|
| Memory | 2048 MB | `WCUI_DEFAULT_MEM_LIMIT_MB` |
| CPU | 2.0 | `WCUI_DEFAULT_CPU_LIMIT` |
| Shared memory (`/dev/shm`) | 1024 MB | `WCUI_DEFAULT_SHM_SIZE_MB` |

The administrator can edit these values per entry. Together with the limit of one instance per image for each user and the automatic stop of idle instances (30 minutes by default), they are the controls available for sizing host consumption.

## Growing beyond one host

To grow beyond one host, the strategy is to use more than one host. The production PostgreSQL already allows several portals over the same data; see [Database](/architecture/database/) and the [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md) spec.

:::note
The composition shipped in the repository is single-host. A multi-host topology is not delivered ready-made and has not been validated under load.
:::
