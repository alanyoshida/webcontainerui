# Tasks

## 1. Fundação da camada portável

- [ ] 1.1 Adicionar `sqlalchemy` e `psycopg` (extra `postgres`) em `backend/pyproject.toml`, instalar no venv e verificar `pip show sqlalchemy psycopg`
- [ ] 1.2 Adicionar `database_url: str | None = None` em `backend/app/config.py` lendo `WCUI_DATABASE_URL`, com teste cobrindo presente/ausente (`backend` + `pytest -k config`)
- [ ] 1.3 Reescrever `backend/app/db.py`: `MetaData` com todas as tabelas/índices (incl. parciais), `create_all` + migrações por `sqlalchemy.inspect` em `init_db`, e fábrica de engine que escolhe SQLite/PostgreSQL pela URL — verificar com teste que bootstrap em banco vazio e boot repetido concluem sem erro em SQLite
- [ ] 1.4 Atualizar `backend/app/deps.py` (`get_db`/`get_db_ws` devolvendo conexão do engine) e a criação do engine no `main.py`/`bootstrap.py`; verificar suíte padrão verde: `cd backend && .venv/bin/python -m pytest`

## 2. Services de identidade e acesso

- [ ] 2.1 Migrar `services/sessions.py`, `services/users.py`, `services/access_control.py` e `api/auth.py` para `text()` com parâmetros `:nome` e tipos D3 — verificar `pytest tests/ -k "session or user or access"`
- [ ] 2.2 Migrar `api/access_control.py` e o restante de SQL direto em rotas de autenticação/admin — verificar `pytest tests/ -k "auth or admin"` e login manual no dev stack

## 3. Services do catálogo

- [ ] 3.1 Migrar `services/images.py`, `api/images.py`, `services/image_covers.py`, `services/image_pull.py` e `services/desktop_images.py` — verificar `pytest tests/ -k image`
- [ ] 3.2 Migrar `services/agents_md.py`, `api/agents_md.py`, `services/agent_skills.py`, `api/agent_skills.py` — verificar `pytest tests/ -k "agents_md or skill"`
- [ ] 3.3 Migrar `services/mcp_servers.py`, `api/mcp_servers.py` e `services/mcp_tool_configs.py` (BLOBs cifrados via `LargeBinary`) — verificar `pytest tests/ -k mcp`
- [ ] 3.4 Migrar `services/groups.py`, `services/agent_images.py` (leitura de ids gerados sem `last_insert_rowid`) — verificar `pytest tests/ -k "group or agent_images"`

## 4. Services de instâncias e operação

- [ ] 4.1 Migrar `services/instances.py`, `api/instances.py` e `api/session_proxy.py` (incl. índice parcial `uq_instances_user_image_live`) — verificar `pytest tests/ -k instance`
- [ ] 4.2 Migrar `services/activity.py`, `services/activity_flusher.py`, `services/reaper.py` e `services/ssh_identity.py` — verificar `pytest tests/ -k "activity or reaper or ssh"`
- [ ] 4.3 Migrar `services/usage_metrics.py` e `api/usage_metrics.py`, normalizando timestamps `datetime`→string na borda (D3) — verificar `pytest tests/ -k metrics`, incluindo o caso `last_seen_at` com fuso

## 5. Equivalência dos dois motores

- [ ] 5.1 Adicionar testes de `init_db` parametrizados: migrações idempotentes aplicadas sobre banco legado (fixture SQLite antigo) e sobre PostgreSQL real (marker pula sem Docker) — verificar `pytest tests/ -k init_db`
- [ ] 5.2 Estender a suíte e2e com serviço PostgreSQL efêmero cobrindo bootstrap + login + criação de usuário + ciclo de instância + métricas (requirement de equivalência) — verificar `pytest -m e2e -k postgres`

## 6. Deploy e documentação

- [ ] 6.1 Adicionar serviço `postgres:17-alpine` (sem `ports`, volume `wcui_pg_data`, healthcheck `pg_isready`) e `depends_on: service_healthy` do portal em `deploy/docker-compose.yml`, montando `WCUI_DATABASE_URL` a partir de `WCUI_POSTGRES_PASSWORD` — verificar `docker compose config` válido
- [ ] 6.2 Atualizar `deploy/.env.example` (nova variável), `deploy/README.md` (subida, backup do Postgres via `pg_dump`, reversão, passo de encerrar instâncias antes de atualizar) e `deploy/SECURITY.md` (superfície do banco interno) — verificar revisão dos passos contra a composição real
- [ ] 6.3 Atualizar `README.md` e `AGENTS.md` (seção banco, produção com Postgres, suíte e2e) — verificar consistência com os comandos reais
- [ ] 6.4 Subir a composição de produção localmente (domínio de teste), conferir bootstrap no Postgres, login do admin e criação de instância; conferir que `docker compose -f docker-compose.dev.yml up` continua subindo só com SQLite — verificação manual registrada na task

## Workflow follow-up

- Revisar delta com `openspec validate --change "postgres-for-production" --strict` antes do commit de implementação
- Arquivar com `openspec archive "postgres-for-production"` após revisão
