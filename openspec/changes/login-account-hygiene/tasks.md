# Tasks

## 1. Timing uniforme no login (B1)

- [x] 1.1 Reordenar a rota `POST /api/auth/login` (`backend/app/api/auth.py`): `verify_password` antes da checagem de `disabled_at`, mantendo 401/corpo idênticos e o registro de falha no limitador em todos os ramos — verificado com teste novo em `test_auth.py`: login de conta desabilitada executa o Argon2 (afirma via monkeypatch/spy em `verify_password`) e mantém a resposta igual à de conta inexistente
- [x] 1.2 Documentar a ordem no comentário da rota (hash em todo ramo de falha, anti-enumeração por timing) e conferir que nenhum teste existente de timing enumerável quebra — suíte `tests/test_auth.py` verde

## 2. Purga de sessões (I5)

- [x] 2.1 Adicionar `session_purge_grace_hours: int = Field(default=24, ge=1)` a `Settings` (env `WCUI_SESSION_PURGE_GRACE_HOURS`) e estender `tests/test_config.py` com default + override por ambiente
- [x] 2.2 Implementar `purge_sessions(conn, grace_hours) -> int` em `backend/app/services/sessions.py` (DELETE de expiradas/revogadas além da carência, corte UTC no formato das demais colunas, devolve contagem) e cobrir com testes unitários novos: expirada além da carência removida, revogada recente preservada, ativa nunca removida
- [x] 2.3 Integrar a purga ao ciclo de `run_reaper` (`backend/app/services/reaper.py`) usando a setting, com o retorno aparecendo no log de ciclo existente — verificado com teste do reaper estendido (purga roda junto do reap de ociosas)

## 3. Verificação de integração

- [x] 3.1 Rodar a suíte padrão (`cd backend && .venv/bin/python -m pytest`) e o build do front (`cd frontend && npm test && npm run build`) — ambos verdes
- [x] 3.2 Contra o stack dev, reproduzir a medição do pentest (5 amostras por caso: inexistente, senha errada, desabilitada) e registrar que os três casos ficam dentro da mesma ordem de grandeza (~dezenas de ms, sem o salto de ~20x)

## Workflow follow-up

- Arquivar (`openspec archive "login-account-hygiene"`) após revisão, sincronizando o delta na spec `auth`.
