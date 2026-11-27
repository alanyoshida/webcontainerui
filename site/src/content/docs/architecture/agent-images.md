---
title: Agent images
description: How the portal builds the coding agent images from a common base, decides when to rebuild and injects covers and AGENTS.md documents.
sidebar:
  order: 4
sourceHash: 473f9d35549f0b21dde66ab5fd182afd1f6e5279026ad85d4b809f22633dd193
---

Agent images give access, through the browser, to command-line coding agents. Unlike the desktops, which are downloaded from a registry, they are built locally by the portal, from Dockerfiles versioned in [`agent-images/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images), and enter the catalog with no manual action from the administrator.

## Image set

| Entry | Directory | Image | Installation | Command |
|---|---|---|---|---|
| Claude Code | `claude-code/` | `wcui-agent-claude-code:latest` | `npm install -g @anthropic-ai/claude-code` | `claude` |
| Hermes | `hermes/` | `wcui-agent-hermes:latest` | `pip install hermes-agent` in an isolated venv | `hermes` |
| Agy | `agy/` | `wcui-agent-agy:latest` | official Antigravity CLI script | `agy` |
| OpenCode | `opencode/` | `wcui-agent-opencode:latest` | `npm install -g opencode-ai` | `opencode` |
| oh-my-pi | `oh-my-pi/` | `wcui-agent-oh-my-pi:latest` | official oh-my-pi script | `omp` |

All of them use port 3000 and are registered in the catalog with provisioning of type `build`.

## Common base

Each agent starts from `wcui-agent-base:latest`, built from [`agent-images/_base/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images/_base). The base contains:

- `node:20-bookworm-slim`, with Python 3, `pip` and `venv`, which are the runtimes the agent CLIs usually rely on;
- `git` and `openssh-client`;
- [ttyd](https://github.com/tsl0922/ttyd), the web terminal, as a static binary at a pinned version;
- GitHub CLI (`gh`) and GitLab CLI (`glab`), also as binaries at pinned versions. Logging in to each one is manual, done by the user in the terminal; neither uses the portal's SSH identity;
- the common entrypoint.

### Entrypoint

The [`entrypoint.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/agent-images/_base/entrypoint.sh) runs `ttyd --writable` with the agent's command (the `CMD` of each derived image), using the same environment variables the portal passes to any instance:

| Variable | Effect |
|---|---|
| `PORT` | Port ttyd listens on; the portal sets it to the port of the catalog entry |
| `SUBFOLDER` | Becomes ttyd's `--base-path`, to match the `/i/<uuid>/` prefix |
| `CUSTOM_USER` and `PASSWORD` | Become ttyd's `--credential`, which is the instance's internal credential |

This is what lets an agent image use the same session mechanism as the desktops, described in [Single origin](/architecture/overview/).

### Home at `/config`

The user's file volume is mounted at `/config`. The base sets `HOME=/config`, adjusts the user's directory in `/etc/passwd` (the `ssh` client resolves the home from there, not from the environment variable) and sets `/config` as the working directory. This way, the CLIs' credentials, sessions and configuration live on the volume and survive container recreation, and the agent starts in the directory where `AGENTS.md` is injected.

## Provisioning at startup

On every startup, the portal:

1. builds the base image;
2. for each agent, ensures the catalog entry exists and builds the image when needed, waiting for each build.

A build failure is isolated: the entry is marked as failed, the others carry on and the portal comes up anyway. A failed build is retried on the next startup.

The build happens inside the portal container, which carries a copy of `agent-images/` and sends the context to the host's daemon through the Docker socket.

## Context hash

To avoid rebuilding everything on every startup, the portal computes a SHA-256 hash of each agent's build context and stores it alongside the entry after a successful build. A rebuild only happens when the hash changes or when the entry is not ready.

The hash covers:

- the content and relative path of every file in `_base/` and in the agent's subdirectory;
- the list of skills linked to the image.

It does not depend on modification time, only on content.

:::note
Changes in `agent-images/covers/` are not part of the hash and therefore do not trigger a rebuild.
:::

## Skills and MCP servers

Two administrative libraries apply only to agent images, with different mechanisms:

- **Skills** are installed during the build. Each Dockerfile receives the `SKILLS` argument and installs each item with `npx skills add`, in isolation: a skill that fails does not break the build or prevent the others. Linking or unlinking a skill changes the hash and triggers an immediate rebuild of the image. Instances already running do not receive the skills from a later rebuild.
- **MCP servers** are configured in the instances, with no rebuild: linking, editing or unlinking a server propagates to live instances, and new instances are created already configured.

## Default covers

At startup, the portal assigns a default cover to every catalog entry, desktop or agent, from the PNGs versioned in [`agent-images/covers/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images/covers). The cover is chosen by matching the entry's name, repository or tag against a map of logos; with no match, a generic cover is used.

- A cover uploaded by the administrator is never overwritten.
- A default cover is updated automatically when the versioned PNG changes.
- An image registered after startup receives its default cover on the next restart.
- The portal does not generate images at runtime: the covers are generated in development by a script and versioned. The procedure and the logo sources are in the [covers README](https://github.com/alanyoshida/webcontainerui/blob/main/agent-images/covers/README.md).

## AGENTS.md documents

The administrator maintains a library of `AGENTS.md` documents and links each catalog entry to at most one of them. The link applies to any entry, not only to agent images.

- **When the instance is created**, the linked document is written as `/config/AGENTS.md`. The injection is best-effort, done together with the SSH identity: a failure does not prevent the instance from coming up.
- **On saving** the text or the link, the portal propagates the change to the live instances of that entry.
- **On unlinking**, the file is removed from live instances through `docker exec`, with a command fixed in the portal's code, never derived from user input.
- **Deleting** a document is refused while there are entries linked to it.

A document's content is limited to 262144 bytes by default (`WCUI_MAX_AGENTS_MD_BYTES`).

## Adding or changing an agent

Before changing the entrypoint or an agent Dockerfile, run the e2e suite, which requires real Docker; see [Development](/reference/development/).

## Formal reference

The behavior contract is in the [`coding-agent-images`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/coding-agent-images/spec.md), [`agents-md`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agents-md/spec.md), [`image-catalog`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/image-catalog/spec.md), [`agent-skills`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agent-skills/spec.md) and [`mcp-servers`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/mcp-servers/spec.md) specs.
