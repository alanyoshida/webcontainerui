---
title: Capabilities
description: Index of the project's 19 capabilities, with the purpose of each one and the link to the formal spec in the repository.
sidebar:
  order: 1
sourceHash: 9c029ff3ece4b40a628fff7746667c11b7b620ca21e3d1d53d7a897fd2a97eb0
---

The portal's behavior is specified per capability, in [`openspec/specs/`](https://github.com/alanyoshida/webcontainerui/tree/main/openspec/specs). This page is the index of the 19 current capabilities.

The specs are the formal contract for the product's behavior: each one states a purpose and a list of normative requirements (with `DEVE`, Portuguese for MUST), and each requirement has at least one scenario in WHEN/THEN format. When this documentation and a spec disagree, the spec prevails. The specs exist only in Portuguese; there is no English translation.

## Accounts and access

| Capability | Purpose |
|---|---|
| [`auth`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) | Authenticates people in the portal and governs the session lifecycle; a session can be revoked at any time by the user or the administrator. |
| [`user-management`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/user-management/spec.md) | Manages the accounts that can use the portal and the groups that organize them, the basis on which image permissions are resolved. |
| [`access-control`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/access-control/spec.md) | Decides which images each user can use, by granting permission to groups, and defines what happens to running instances when a permission is withdrawn. |
| [`ssh-identity`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/ssh-identity/spec.md) | Gives each user their own SSH identity, generated and stored by the portal, available in any of their instances so that `git` authenticates without manual setup. |

## Catalog and images

| Capability | Purpose |
|---|---|
| [`image-catalog`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/image-catalog/spec.md) | Maintains the set of images the portal offers, including the download and the readiness state that decides whether the image can already be used to create instances. |
| [`coding-agent-images`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/coding-agent-images/spec.md) | Maintains in the catalog a fixed set of CLI coding agent images, provisioned by the portal and accessed through the same session mechanism as the desktops. |
| [`agents-md`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agents-md/spec.md) | Maintains a library of `AGENTS.md` documents, allows each catalog entry to be linked to one of them and injects the document into instances. |
| [`agent-skills`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agent-skills/spec.md) | Maintains a library of skills, allows each agent image to be linked to several of them and ensures the image build installs them. |
| [`mcp-servers`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/mcp-servers/spec.md) | Maintains a library of MCP servers, allows each agent image to be linked to several of them and configures them in instances without requiring a rebuild. |

## Instances and sessions

| Capability | Purpose |
|---|---|
| [`desktop-instances`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/desktop-instances/spec.md) | Governs each user's sessions: when a container is created, stopped and removed, where files persist, how many sessions a person keeps and how abandoned sessions stop consuming memory. |
| [`session-proxy`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md) | Delivers the session to the owner's browser and to no one else, authorizing each request by instance ownership before forwarding it to the container. |
| [`stream-data-plane`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md) | Defines the transport of session traffic through a data plane external to the portal in production, with the authorization decision remaining in the portal. |
| [`session-view`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-view/spec.md) | Defines how the portal displays a running session and lets it be expanded to full screen, preserving a clear way to leave that mode. |
| [`instance-usage-metrics`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/instance-usage-metrics/spec.md) | Records the run history of each instance and gives the administrator visibility, live and historical, into who uses which instances and for how long. |

## Security and persistence

| Capability | Purpose |
|---|---|
| [`http-hardening`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md) | Hardens the portal's HTTP surface with security headers and minimal exposure of documentation and stack identification. |
| [`security-audit-log`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md) | Maintains a structured, queryable trail of security events: who did what, from where and with what outcome, without ever recording secrets. |
| [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md) | Defines which database the portal uses in each environment, how the choice is configured and how the production composition provides PostgreSQL. |

## Interface

| Capability | Purpose |
|---|---|
| [`app-shell`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/app-shell/spec.md) | Defines the portal's visible frame: the top bar, the admin navigation, the page structure of the console and the rules for feedback and empty states. |
| [`theming`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/theming/spec.md) | Defines the portal's visual identity: the three color themes, the default theme, persistence of the choice and the font and icon families. |

## Consulting the specs locally

With the OpenSpec CLI installed, the list and content of the specs can be consulted from a clone of the repository:

```bash
openspec list --specs
openspec show auth
```

The workflow for proposing and implementing changes is in [Development](/reference/development/).
