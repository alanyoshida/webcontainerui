---
title: Development
description: How to set up the development environment, run the test suites and follow the project's conventions when contributing.
sidebar:
  order: 2
sourceHash: 30b8b4639f6d46f381c840005782bfd8543613e89a7c2eb278ce7633a26f8c88
---

This page gathers what you need to contribute: setting up the environment, running the tests and following the code conventions. The full operational instructions for coding agents are in the repository's [`AGENTS.md`](https://github.com/alanyoshida/webcontainerui/blob/main/AGENTS.md).

## Repository structure

| Path | Contents |
|---|---|
| `backend/` | Portal in FastAPI (Python 3.12 or later) |
| `frontend/` | Interface in React with Vite |
| `agent-images/` | Dockerfiles for the agent images and default covers |
| `deploy/` | Development and production compositions, and the `Caddyfile` |
| `openspec/` | Behavior specs and change planning |
| `site/` | This site |

## Environment

The back end and the front end are installed independently.

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev,postgres]"
```

```bash
cd frontend && npm ci
```

### Bring up the portal

The development composition brings up the full portal at `http://127.0.0.1:8000`, without Caddy:

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

The development credentials and the details of the composition are in [Local trial](/getting-started/local-trial/).

### Front end with hot reload

With the portal running, run Vite in another terminal:

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api`, `/i` and `/uploads` to the portal at `http://127.0.0.1:8000`, preserving the single origin in development.

Caddy is not used in development: `http://localhost` is already a secure context, which is what the Selkies client requires for the WebCodecs API to work.

## Tests

### Back end

The default suite runs on SQLite, with a fake container runtime, and **does not require Docker**. The `e2e` marker is deselected by default.

```bash
cd backend && .venv/bin/python -m pytest
```

The e2e tests require real Docker and a downloaded webtop image, and start an ephemeral PostgreSQL to cover the production dialect:

```bash
cd backend && .venv/bin/python -m pytest -m e2e
```

Run the e2e suite before changes to the Docker runtime, the agent images' entrypoint, SSH identity injection or data access.

### Front end

```bash
cd frontend && npm test
```

```bash
cd frontend && npm run build
```

`npm test` runs Vitest in jsdom; `npm run build` produces the production build and serves as a compilation check. The Playwright browser tests live in `frontend/e2e/` and run separately, with `npm run test:e2e`.

### Manual verification

To check a change end to end, bring up the development composition and verify the catalog, starting an instance and the SSH identity screen.

## Conventions

### Async and the event loop

The portal runs with **one worker**. In development, each session's stream passes through the Python process, so a synchronous call to Docker in the path of a request would stall the event loop for every session.

- Every Docker operation goes through `aiodocker`, in `backend/app/runtime/docker_runtime.py`.
- `backend/app/runtime/fake.py` implements the same protocol and is the runtime used by the tests.

### Security

- The portal has the Docker socket mounted, which is equivalent to root on the host. Do not execute user code inside the portal process.
- Instance containers never publish a port on the host.
- The owner check on session forwarding and the random per-instance credential are distinct layers; do not remove either of them. See [Isolation layers](/security/isolation-layers/).
- Commands executed in containers through `runtime.exec` are always fixed in the code, never derived from user input.
- Secrets live in the environment (`WCUI_*`), never in the repository. `.env` is ignored by git; use `deploy/.env.example` as a template.

### Database

Data access is SQLAlchemy Core with explicit SQL and must run the same on SQLite and PostgreSQL. The rules for timestamps, booleans and migrations are in [Database](/architecture/database/).

### Front end

- No custom CSS: use the MUI theme (`frontend/src/theme.js`) and the `sx` prop.
- Tests use `@testing-library/react` with Vitest, in `*.test.jsx` files next to the component.
- In production, FastAPI serves the build from `frontend/dist`; API routes take priority over the SPA catch-all.

### Data plane

The in-process proxy (`backend/app/api/session_proxy.py`) must remain registered: it is the path for development and the test suite, and the defense in depth in production. Do not reintroduce activity recording per message carried. See [Session data plane](/architecture/session-data-plane/).

### Agent images

A build failure in one agent must not prevent the others or the portal's startup. See [Agent images](/architecture/agent-images/).

## Planning with OpenSpec

Behavior changes are planned in `openspec/changes/<name>/`, with `proposal.md`, `design.md`, one spec delta per affected capability and `tasks.md`. Read the relevant specs before changing behavior; the index is in [Capabilities](/reference/capabilities/).

```bash
openspec status --change "<name>"
openspec instructions apply --change "<name>" --json
```

Once implemented and reviewed, the change is archived, which syncs the deltas into the main specs:

```bash
openspec archive "<name>"
```

The specs use `DEVE` (Portuguese for MUST) per requirement, with at least one scenario in WHEN/THEN format.

## Commits

- Messages in Portuguese, in the imperative, with no type prefix, for example `Adiciona tela cheia à visão de sessão`.
- One commit per coherent unit of work. The proposal commit (`Propõe change <nome>`) is separate from the implementation commit (`Implementa <resumo>`).
- Do not commit secrets, `.env` or local databases.
- Use `git add` with explicit paths; avoid `git add .` when there are build artifacts or a venv in the directory.
