# Tasks

## 1. Configuração e limitador de login (M2)

- [x] 1.1 Adicionar `login_max_failures` (10), `login_window_seconds` (300) e `login_lock_seconds` (300) a `Settings` (`gt=0`, env `WCUI_LOGIN_*`) e verificar que `Settings()` aceita os defaults e sobrescreve via ambiente em teste rápido de `config.py`
- [x] 1.2 Criar `backend/app/services/login_throttle.py` (janela deslizante por chave, recusa temporária, relógio injetável, poda de expirados) e verificar com testes unitários novos (`login_throttle`): limite atingido, liberação após `login_lock_seconds`, poda de memória, contadores independentes por chave
- [x] 1.3 Integrar o limitador à rota `POST /api/auth/login`: checar **antes** do banco/Argon2, registrar falha por e-mail normalizado e por IP do cliente, limpar bucket da conta no sucesso, responder `429` com `Retry-After` e corpo genérico idêntico para conta existente/inexistente — verificado por testes de rota no padrão existente em `tests/`

## 2. Proxy confiável e HSTS (M1)

- [x] 2.1 Fixar subnet da `wcui_net` via IPAM no `deploy/docker-compose.yml` (ex. `10.213.0.0/24`) e adicionar `UVICORN_PROXY_HEADERS: "true"` + `UVICORN_FORWARDED_ALLOW_IPS: <subnet>` ao serviço `portal`; verificar com `docker compose config` que a rede e as variáveis renderizam como esperado
- [x] 2.2 Adicionar `header Strict-Transport-Security "max-age=31536000"` ao site do `deploy/Caddyfile` e verificar com `docker compose config` + leitura do Caddyfile renderizado
- [x] 2.3 Verificar o efeito fim a fim no arranjo dev (design D7): `deploy/docker-compose.dev.yml` com as variáveis `UVICORN_PROXY_HEADERS`/`UVICORN_FORWARDED_ALLOW_IPS` apontando a subnet dev em override local (sem commit de mudança de comportamento no dev), `curl -D -` no login com `X-Forwarded-Proto: https` deve devolver `Set-Cookie` contendo `Secure`

## 3. Documentação de deploy

- [x] 3.1 Documentar em `deploy/README.md` as variáveis novas (`UVICORN_PROXY_HEADERS`/`UVICORN_FORWARDED_ALLOW_IPS`, `WCUI_LOGIN_*`), a necessidade de recriar a rede ao fixar IPAM e o checklist pós-deploy (HSTS presente; `Set-Cookie: Secure` via HTTPS) — verificado conferindo que o comando/procedimento documentado executa como escrito
- [x] 3.2 Registrar em `deploy/SECURITY.md` o racional do allowlist por subnet (D2) e do trade-off do limitador por conta (D4), referenciando o relatório de pentest — revisão por leitura: texto condiz com o design

## 4. Verificação de integração

- [x] 4.1 Rodar a suíte padrão (`cd backend && .venv/bin/python -m pytest`) e o build do front (`cd frontend && npm test && npm run build`) — ambos verdes
- [x] 4.2 Repetir o protocolo do pentest para os itens M1/M2 contra o stack dev com as variáveis ativas (25 senhas erradas → limite aplica `429`; login correto dentro do limite funciona; cookie com `Secure` atrás do cabeçalho confiável) e registrar o resultado no contexto da change

## Workflow follow-up

- Arquivar a change (`openspec archive "harden-login"`) após revisão, sincronizando os deltas na spec `auth`.
- Change futura `session-origin-isolation` (achado M3) segue separada, conforme decisão de escopo.
