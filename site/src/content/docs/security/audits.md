---
title: Audits
description: Current status of each finding from the project's security reports — fixed, accepted or open — with an indication of where it was addressed.
sidebar:
  order: 5
sourceHash: 8a8f684a0fb13f2a91b533cb832ac939f90a228bbfca7c4af59e8a6918268ba3
---

This page lists each finding from the security reports published in the repository and states, one by one, what state it is in in the current code. The findings that remain unfixed appear as "open" on purpose: the page exists so that you can decide with complete information, not to look clean. A finding is only marked "fixed" when there is concrete evidence in the code — file, specification or test — that the problem described no longer exists.

## How to read the statuses

| Status | Meaning |
|---|---|
| **fixed** | The problem described no longer exists in the current code, and the fix is pointed to in the "Where it was addressed" column |
| **accepted** | The risk is acknowledged and kept by a documented project decision; the column points to where the decision is recorded |
| **open** | No fix, or insufficient evidence of a fix |

:::note[Scope of this verification]
The statuses were checked by reading the code, the specifications and the existing automated tests. The dynamic tests from the reports (response time measurement, inspection of headers behind Caddy, image scan) **were not re-run** for this page. Where the fix depends on deployment configuration, that is stated in the finding's row.
:::

## Penetration test — November 1, 2026

- **Date:** November 1, 2026
- **Commit assessed:** `22f2d69`
- **Type:** white-box penetration test (source code available), with dynamic tests against a local development instance
- **Result:** no critical or high findings; 3 medium, 5 low, 5 informational
- **Full report:** [docs/relatorio-pentest-2026-11-01.md](https://github.com/alanyoshida/webcontainerui/blob/main/docs/relatorio-pentest-2026-11-01.md) (in Portuguese)

| Finding | Severity | Summary | Status | Where it was addressed |
|---|---|---|---|---|
| M1 | Medium | Session cookie without `Secure` in production, because the portal did not honor the headers forwarded by Caddy | **fixed** | Specification [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (cookie protected in transport). `deploy/docker-compose.yml` sets `UVICORN_PROXY_HEADERS` and `UVICORN_FORWARDED_ALLOW_IPS` with the fixed subnet of `wcui_net`; `deploy/Caddyfile` sends HSTS. Depends on deployment configuration — see the note below |
| M2 | Medium | Login with no attempt limiting and no temporary lockout | **fixed** | Specification [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (failed attempts are limited). `backend/app/services/login_throttle.py`, consulted in `backend/app/api/auth.py` before the database and Argon2; tests in `backend/tests/test_login_throttle.py` and `backend/tests/test_auth.py` |
| M3 | Medium | Content from the user's container executes on the same origin as the portal and can use the user's session | **accepted** | Architecture decision recorded in the [session-proxy](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md) specification (each instance has an address under the portal's origin). Partial mitigation in [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md), which does not cover `/i/` |
| B1 | Low | Disabled account distinguishable from the others by the login response time | **fixed** | Specification [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (disabled account indistinguishable by time as well). In `backend/app/api/auth.py` the password is verified before the `disabled_at` check; test `test_conta_desabilitada_passa_pelo_hash` in `backend/tests/test_auth.py` |
| B2 | Low | Responses without security headers (CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) | **fixed** | Specification [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md). `SecurityHeadersMiddleware` in `backend/app/main.py`; tests in `backend/tests/test_http_hardening.py` |
| B3 | Low | `/docs` and `/openapi.json` exposed without authentication | **fixed** | Specification [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md). `docs_enabled` off by default in `backend/app/config.py`, applied in `backend/app/main.py` |
| B4 | Low | Containers of different users share the same Docker network and can reach each other | **open** | No fix. `backend/app/services/instances.py` creates every instance on the single network of `WCUI_DOCKER_NETWORK`; there is no per-user or per-instance network in the runtime |
| B5 | Low | `icon_url` used as an image `src` without validation in the front end | **fixed** | `localCoverUrl()` in `frontend/src/utils/iconUrl.js` only accepts paths under `/uploads/`; used in `CatalogSection.jsx` and `ImagesPanel.jsx`, with a test in `frontend/src/utils/iconUrl.test.js`. Reinforced by the portal's CSP (`img-src 'self' data:` in `backend/app/main.py`), specification [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md) |
| I1 | Informational | `harden_desktop` option accepted and returned by the API with no effect at all | **fixed** | The field is no longer accepted or returned by the API and does not appear in the interface; test `test_harden_desktop_some_da_api` in `backend/tests/test_image_edit.py`. The column remains in the schema (`backend/app/db.py`), unused |
| I2 | Informational | Orphan containers from previous deployments keep running on the host | **open** | No fix. The reconciliation in `backend/app/services/reaper.py` only corrects the state recorded in the database; nothing lists or removes `wcui-*` containers without a record |
| I3 | Informational | `Server: uvicorn` header discloses the stack | **fixed** | `header -Server` in `deploy/Caddyfile`. Applies at the production edge; in development, without Caddy, the header is still present |
| I4 | Informational | No security event was recorded | **fixed** | Specification [security-audit-log](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md). `backend/app/services/audit_log.py` and callers in the routes; tests in `backend/tests/test_audit_log.py` and `backend/tests/test_audit_events.py` |
| I5 | Informational | `sessions` table grows indefinitely | **fixed** | Specification [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (expired or revoked sessions are purged). `purge_sessions` in `backend/app/services/sessions.py`, called by the cycle of `backend/app/services/reaper.py` |

### Notes on the fixed items

Some fixed items have caveats that do not fit in a table cell.

- **M1 depends on the deployment.** The fix is in the production Compose file, not in the image: the cookie only gets `Secure` if the forwarded headers allowlist matches the real subnet of the internal network. Whoever changes the subnet without adjusting `WCUI_FORWARDED_ALLOW_IPS`, or runs the portal behind another proxy with a Compose file of their own, goes back to the state of the finding with no visible error. The [Post-deploy checklist](/operations/post-deploy-checklist/) has the check.
- **M2 was fixed with a trade-off.** The per-account limiter allows an attacker to keep a victim's account temporarily locked. The state lives in memory and is reset when the portal restarts. The exponential delay recommended by the report was not implemented. Details in [Login hardening](/security/login-hardening/).
- **B1 was verified by the structure of the code, not by measurement.** Argon2 now runs on all failure branches, and there is a test that confirms the order of the checks. The timing measurement from the original report was not redone.
- **B2 does not cover the session path.** The headers apply to the portal's own responses. The content of `/i/{uuid}/` arrives without CSP — which is precisely the M3 scenario. The policy uses `X-Frame-Options: SAMEORIGIN` instead of the recommended `DENY`, because the portal embeds the session in an iframe, and keeps `style-src 'unsafe-inline'` as a requirement of the interface library.
- **I4 has coverage gaps.** The trail exists and covers login, administration and instance lifecycle, but it does not record attempts denied by authorization, automatic stops or SSH identity regeneration. See [Security event trail](/security/audit-log/).
- **I5 does not limit sessions per user.** The purge removes dead rows; the optional limit on active sessions per user, suggested by the report, was not implemented.

## SAST and SCA scan — November 1, 2026

- **Date:** November 1, 2026
- **Commit assessed:** the report does not state the commit; it was produced on the same day, as a complement to the penetration test
- **Type:** static code analysis (bandit) and software composition analysis — Python dependencies (pip-audit), npm dependencies (npm audit) and production Docker image (trivy)
- **Full report:** [docs/relatorio-sast-sca-2026-11-01.md](https://github.com/alanyoshida/webcontainerui/blob/main/docs/relatorio-sast-sca-2026-11-01.md) (in Portuguese)

The report does not number the findings; the identifiers `S1` to `S7` below were assigned by this page, in the order in which they appear in it. The severity is the maximum reported by the tool, before triage.

| Finding | Severity | Summary | Status | Where it was addressed |
|---|---|---|---|---|
| S1 | Critical (only in development tooling) | 6 npm advisories in the test and build chain: `vitest`, `tinypool`, `vite`, `esbuild`, `vite-node`, `@vitest/mocker` | **fixed** | `frontend/package.json` requires `vitest@^5.0.5`; `frontend/package-lock.json` pins vitest 5.0.5, vite 6.4.5 and esbuild 0.25.12, and no longer contains `tinypool` or `vite-node`. Addendum 8.1 of the report |
| S2 | Medium (bandit B608) | Two alerts of possible SQL injection through string construction, in `agents_md.py` and `usage_metrics.py` | **accepted** | False positive, triaged in section 4 of the report. Checked in the current code: the SQL text is assembled only from module constants and generated parameter placeholders; the values always go as named parameters |
| S3 | Low (bandit B110/B112) | Four `try/except` blocks that swallow the exception, in `agent_images.py`, `image_covers.py`, `image_pull.py` and `mcp_tool_configs.py` | **accepted** | Per-item isolation, intentional: the failure of one image, cover or MCP server does not bring down the startup or the others. Documented in the code comments and in section 4 of the report; none is on an authentication or authorization path |
| S4 | High | 177 CVEs in operating system packages of the base image (`python:3.12-slim`, Debian 13): 46 high, 62 medium, 61 low, 8 unclassified | **open** | No fix. The mitigation indicated by the report is to rebuild the image periodically; the repository has no automation that does this |
| S5 | Medium | 6 CVEs in the `pip` 25.0.1 bundled in the base image | **fixed** | `Dockerfile` upgrades `pip` and `setuptools` before installing the dependencies. Addendum 8.1 of the report |
| S6 | Unclassified | `msgpack`, a transitive dependency of `aiodocker`, with no version floor that excludes releases with deserialization flaws | **fixed** | `backend/pyproject.toml` requires `msgpack>=1.2.3`. Addendum 8.1 of the report |
| S7 | Unclassified | 8 "Python" findings in the new scan of the image, all in copies bundled in `pip/_vendor/` | **accepted** | Known noise, triaged in addendum 8.2 of the report: they are copies used only by `pip` itself during the build, never loaded at runtime |

The same report records **zero** known vulnerabilities in the portal's Python dependencies and in the production npm dependencies, as of the scan date. It also records a limitation: the `semgrep` tool failed to run, so the automated static analysis was restricted to `bandit`, and the front end had no automated static analysis — only the manual review of the penetration test.

:::caution[Dependency scans age]
The SCA results are valid for the date on which they were obtained. `npm audit`, `pip-audit` and `trivy` were not re-run for this page, and the repository has no periodic automatic check. Advisories published after November 1, 2026 are not reflected here. Run the tools against your own image before deploying; the commands are in section 7 of the report.
:::

## What remains open

Open and accepted items, with the real impact of each one.

### M3 — the container executes on the portal's origin (accepted)

The desktop or terminal is embedded in an iframe served by the portal itself at `/i/{uuid}/`. All HTML and JavaScript that comes out of the user's container runs, as far as the browser is concerned, as if it were the portal: it shares the session cookie and can call the API authenticated as the logged-in user.

In practice: if something inside the container manages to serve malicious content through the interface port — a compromised npm package that overwrites the web terminal's files, or an XSS flaw in the embedded interface —, that content can delete the user's instances, regenerate their SSH key and, **if the logged-in user is an administrator, operate the entire admin API**: create users, change the catalog, propagate documents and MCP servers to other people's instances. The product exists to run AI agents and third-party packages inside these containers; the trust boundary of the terminal is, in fact, the trust boundary of the account on the portal.

The decision to keep the same origin is in the session proxy specification: it is what allows embedding the session without relaxing the container's origin policy. The underlying fix — serving the sessions on a separate origin, with a subdomain per instance — was not done. The CSP added later protects the portal's pages, not the content of `/i/`.

What you can do today: **do not use an administrator account to open desktop or agent sessions.** Keep a separate administrative account, used only for the panel, and an ordinary account for the work in the containers.

### B4 — Docker network shared between users (open)

All instances, of all users, sit on the same internal network, together with the portal, Caddy and PostgreSQL. From inside one's own container — where the user has root — it is possible to scan ports and connect to the other users' containers.

What holds today is the random per-instance credential, which resisted in the test: the other user's container responded `401`. But it protects only the interface process. Any other service that a user, an agent or an image brings up on another port — a development server, a debugging API, a local database — is exposed to all the other users of the portal, without authentication. For a product whose purpose is to run development environments, this is a common scenario, not a hypothetical one.

Neither of the report's two recommendations was implemented: there is no per-user network, and the requirement "every listener requires the internal credential" was not formalized as a contract of the agent images. In the meantime, instruct users to listen only on `localhost` inside the container and treat all users of one same installation as belonging to the same network trust level. See [Isolation layers](/security/isolation-layers/).

### I2 — orphan containers (open)

The portal reconciles the state of the instances it knows about: if a container has disappeared, the instance becomes "parada" (stopped). The reverse does not happen. A `wcui-*` container that keeps running without a corresponding record in the database — after restoring an old backup, switching databases or deleting the data volume without bringing down the containers — is neither detected nor removed.

The impact is one of hygiene and resources, with a security component: the orphan container keeps consuming CPU and memory, keeps the user's volume and data, stays connected to the internal network and is outside any control by the portal (it is not stopped for idleness or by access revocation). The containers created by the portal do not receive labels that identify the deployment, which makes it hard to tell orphans from legitimate instances beyond the name prefix.

When reprovisioning or restoring, manually compare the running containers with the registered instances:

```bash
docker ps --filter "name=wcui-" --format '{{.Names}}\t{{.Status}}\t{{.Networks}}'
```

Related procedures in [Backup and restore](/operations/backup-and-restore/) and [Rollback](/operations/rollback/).

### S4 — CVEs in the base image's operating system (open)

The portal image starts from `python:3.12-slim`. On the scan date it carried 177 CVEs in Debian packages, 46 of them of high severity, several with no fixed version available. The report's triage classifies them as a depth risk: the affected libraries (util-linux, ncurses, PAM, systemd) are not on any request path of the portal.

That triage is reasonable, but it carries particular weight here: the portal process has the Docker socket and is equivalent to root on the host. A flaw that in another application would be contained by the container is not contained in this component. And the number does not go down by itself — the only mitigation is to rebuild the image to incorporate the base's fixes, and the repository does not automate this.

Rebuild the portal image regularly (`docker compose build --pull`) and run the scan against the image you actually deploy.

### S2, S3 and S7 — alerts triaged as not exploitable (accepted)

- **S2:** the two SQL injection alerts are false positives. The text of the queries is assembled only from constants and placeholders generated by the code itself; no user input enters the SQL text. The residual risk is one of maintenance: a future change to these two functions that interpolates an external value would not be stopped by anything other than review.
- **S3:** the four blocks that swallow exceptions are deliberate isolation at startup and in the assembly of configuration. The cost is one of observability — a failure at these points can go unrecorded — and not of authorization.
- **S7:** the findings in `pip/_vendor/` are internal copies of `pip`, which only runs during the image build. They keep appearing in scans; filter the directory or treat it as known noise.

## What the audits did not cover

To size what the reports prove:

- The penetration test ran against the local **development** environment. The production Compose file — Caddy, external data plane, PostgreSQL — was reviewed statically in the test, not attacked. The external session data plane and the migration to PostgreSQL are later than the commit assessed and **have not been through a penetration test**.
- Left out of scope, by decision: destructive denial of service, exploitation on a public network and social engineering.
- Container escape and the security of third-party images (webtop, the agents' CLIs) were not assessed.
- The two reports combine automated tools and manual review, run on the maintainer's own environment. Neither of them is an audit by an independent third party.

The structural risks that are not "findings" — because they follow from what the product does — are in [Trust surface](/security/trust-surface/).
