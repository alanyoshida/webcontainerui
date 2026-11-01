# Relatório de Scan de Vulnerabilidades — SAST + SCA

> **Adendo (correções aplicadas no mesmo dia, ver §8):** vitest atualizado
> (npm audit zerado), pip/setuptools atualizados na imagem e piso de msgpack
> no pyproject. O rescan pós-correção reduziu a seção Python da imagem a
> falsos positivos de pacotes vendored pelo próprio pip (§8.2). As seções 1–7
> abaixo registram o estado anterior às correções, como escaneado.

**Projeto:** webcontainerui · **Data:** 1 de novembro de 2026
**Escopo:** código do backend (Python 3.12), código do frontend (React/JS), dependências Python e npm, imagem Docker de produção (`deploy-portal:latest`, base `python:3.12-slim` / Debian 13.7)
**Ferramentas:** pip-audit 2.10.1 (OSV/PyPI), npm audit (registro npm), bandit 1.9.4, trivy (latest, DB do dia) · semgrep 1.183.0 tentado (ver §6)
Complementar ao `docs/relatorio-pentest-2026-11-01.md` (análise manual). Ferramentas instaladas em venv isolado em `/tmp` — o `.venv` do projeto não foi alterado.

---

## 1. Resumo executivo

| Alvo | Ferramenta | Achados | Triagem |
|---|---|---|---|
| Dependências Python (54, runtime+dev) | pip-audit | **0 vulnerabilidades conhecidas** | — |
| Dependências npm de **produção** (11) | npm audit | **0 vulnerabilidades** | — |
| Dependências npm de **desenvolvimento** (vitest/vite & cia) | npm audit | **6** (2 critical, 1 high, 3 moderate) | dev-only; correção exige bump major |
| Código backend (`backend/app`) | bandit | **6** (2 medium, 4 low) | 2 falsos positivos, 4 padrões intencionais |
| Imagem Docker de produção | trivy | **177** em pacotes do SO (0 critical, 46 high, 62 medium, 61 low, 8 unknown) + 6 no `pip` da base | baixa alcançabilidade; ver §5 |

**Conclusão:** nenhuma vulnerabilidade em dependência de **runtime em produção** com correção disponível. Os pontos acionáveis são (a) bump major do vitest (toolchain de teste), (b) upgrade do `pip` dentro da imagem e rebuild periódico da base Debian.

## 2. SCA — Backend Python (pip-audit)

`pip list --format freeze` do `.venv` (54 pacotes, incluindo dev) auditado contra OSV/PyPI: **nenhuma vulnerabilidade conhecida**. Versões relevantes atuais: fastapi 0.162.0, uvicorn 0.54.0, httpx 0.28.1, cryptography 50.0.2, argon2-cffi 25.1.0, aiodocker 0.27.0.

## 3. SCA — Frontend (npm audit)

**Dependências de produção limpas** (react, react-dom, react-router-dom, @mui/*, @emotion/*, @fontsource/*, @mui/x-charts, lucide-react — nenhuma com advisory).

Os **6 advisories são todos da toolchain de teste/build** (`devDependencies`), corrigíveis apenas com `vitest@5.0.5` (bump de versão principal):

| Pacote | Severidade máx. | Advisory representativo |
|---|---|---|
| vitest | **critical** | GHSA-5xrq-8626-4rwp — servidor de UI do Vitest permite ler/executar arquivo arbitrário |
| tinypool | **critical** | GHSA-85c8-ppgw-ccpr — prototype pollution → RCE nas opções de `run()` |
| vite | high | GHSA-587h-7wmj-h5pm — bypass em `fs.existsSync` no dev server (Windows) + mais 5 moderate (dev server, `server.fs.deny`, path traversal em `.map`) |
| esbuild | moderate | GHSA-67mh-4wv8-2f99 — dev server responde requisições cross-origin |
| vite-node / @vitest/mocker | moderate | path traversal / leitura de arquivo via mock redirect |

**Triagem:** todos exigem o servidor de dev/teste em execução (`npm run dev`, `npm test`, UI do vitest) — não existem no build de produção (assets estáticos servidos pelo FastAPI). Risco real: estação de desenvolvimento executando testes em rede hostil ou dependência maliciosa no momento do build. **Recomendação:** planejar o bump `vitest@5` (+ `vite` compatível) e, até lá, rodar `npm test`/`npm run dev` apenas em rede confiável.

## 4. SAST — Backend (bandit)

6 achados, **nenhum é vulnerabilidade real**:

- **B608 (medium) `agents_md.py:43` e `usage_metrics.py:121`** — "possível SQL injection via construção de string": falsos positivos. No primeiro, concatenação de constante de módulo (`_DOCUMENT_SELECT`) com literal contendo `?` e valor via tupla; no segundo, a f-string interpola **apenas placeholders `?` gerados** (`",".join("?" for ...)`) com os valores sempre parametrizados. Nenhum input de usuário entra no texto SQL.
- **B110/B112 (low) `agent_images.py:191`, `image_covers.py:121`, `image_pull.py:36`, `mcp_tool_configs.py:438`** — `try/except/pass|continue`: padrão de **isolamento por item, intencional e documentado nos próprios comentários** (falha de uma imagem/capa/MCP não derruba o startup nem as demais — requisito D5 do design). Nenhum está em caminho de autenticação/autorização.

## 5. SCA — Imagem Docker de produção (trivy)

`deploy-portal:latest` (base `python:3.12-slim`, Debian 13.7):

- **177 CVEs em pacotes do SO** (46 high, 62 medium, 61 low, 8 unknown, 0 critical), concentrados em: família util-linux (bsdutils/libblkid1/libmount1/libsmartcols1/libuuid1/mount/login/util-linux), ncurses, `libacl1` (GHSA/CVE-2026-54369, escalada via symlink — requer uso da lib dentro do container), `libsqlite3-0`, `libsystemd0`/`libudev1`, `perl-base`. Vários **sem versão corrigida disponível** ainda no Debian 13.
- **6 CVEs no `pip` 25.0.1 da imagem base** (5 medium + 1 low; ex.: CVE-2026-6357 execução arbitrária, CVE-2026-8643 path traversal na instalação). Não aparecem no pip-audit porque este audita dependências do app e ignora a ferramenta pip em si. O `pip` só roda no **build** da imagem, nunca em runtime.

**Triagem de alcançabilidade:** o processo do portal é um serviço FastAPI sem shell interativo; as libs atingidas (ncurses, util-linux, PAM, systemd) não estão em nenhum caminho de request. A extração de tar/`put_archive` roda no **daemon Docker**, não no portal. Os CVEs de SO são risco de profundidade, não de superfície exposta.

**Recomendações:**
1. No `Dockerfile`: `RUN pip install --no-cache-dir --upgrade pip` antes do `pip install -e .` — elimina os 6 achados de pip.
2. Rebuild periódico (CI mensal) para incorporar point-releases do `python:3.12-slim`; considerar `python:3.12-slim-bookworm`→`trixie` tracking e, no futuro, `debian:stable-slim` + venv, para reduzir a superfície de SO.
3. Onde houver fix disponível (ex.: libacl1), o rebuild da base resolve na próxima publicação da imagem oficial.

## 6. Limitações

- **semgrep 1.183.0 crashou** (`semgrep-core exit code 2`) em qualquer ruleset, no Python 3.14 do host — 0 arquivos escaneados. Cobertura SAST de código ficou por conta do bandit + revisão manual do pentest (que incluiu leitura integral do backend e do frontend).
- trivy usou a DB do dia; advisories sem fix no Debian podem demorar a fechar.
- npm audit não cobre o Playwright dos e2e além do lockfile (sem advisory no momento).

## 7. Reprodução

```bash
# SCA Python (venv isolado de ferramentas)
python3 -m venv /tmp/scan-tools && /tmp/scan-tools/bin/pip install pip-audit bandit
cd backend && .venv/bin/pip list --format freeze | grep -v '^-e\|^webcontainerui' > /tmp/freeze.txt
/tmp/scan-tools/bin/pip-audit -r /tmp/freeze.txt

# SCA npm
cd frontend && npm audit

# SAST
/tmp/scan-tools/bin/bandit -r backend/app

# Imagem
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image deploy-portal:latest
```

## 8. Adendo — correções aplicadas e rescan

### 8.1 Correções

| Item | Correção | Resultado |
|---|---|---|
| npm: 6 advisories (vitest & cia) | `npm install -D vitest@^5.0.5` (vite 6.4.5, esbuild 0.25.12 na árvore) | **npm audit: 0 vulnerabilidades**; 142 testes verdes; build ok |
| Dockerfile: 6 CVEs do pip 25.0.1 | `pip install --upgrade pip setuptools` antes do install (pip 26.2.2, setuptools 84.2.1 na imagem) | CVEs do pip/setuptools/ensurepip eliminados |
| msgpack (dependência real do aiodocker) | piso `msgpack>=1.2.3` em `backend/pyproject.toml` (instalado 1.2.4) | dependência runtime protegida contra regressão |

### 8.2 Rescan pós-correção e falsos positivos do diretório `_vendor`

O rescan da imagem reconstruída ainda lista 8 achados "Python" — **todos são
cópias vendored dentro de `pip/_vendor/`** (msgpack 1.1.2, setuptools 70.3.0,
urllib3 2.7.0), usadas apenas pelo próprio pip durante builds, nunca em
runtime: `pip list` dentro da imagem não os contém como pacotes top-level, o
venv do backend não os tem, e o filesystem só carrega `pip/_vendor/<pacote>`.
O upgrade do pip (25.0.1 → 26.2.2) mudou a metadata visível ao trivy — o pip
novo publica as licenses/fontes vendored em formato que o scanner passa a
parsear — o que fez "aparecerem" achados que antes não eram listados.

Verificação executada: `docker run deploy-portal:latest pip list` (sem
urllib3/msgpack 1.1.2/setuptools 70.3.0), `pip show` vazio para os três, e
`find` localizando-os somente sob `pip/_vendor/`. Em CI, filtrar com
`trivy image --skip-dirs pip/_vendor` (ou aceitar como ruído conhecido).

**Estado final real:** dependências de runtime Python e npm sem
vulnerabilidades conhecidas; SO da base Debian 13.7 com os 177 CVEs de
baixa alcançabilidade descritos na §5 (mitigação por rebuild periódico,
item 2 da §5).
