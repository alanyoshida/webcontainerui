# Proposal

## Why

O pentest de 2026-11-01 (`docs/relatorio-pentest-2026-11-01.md`) apontou dois
resíduos de higiene no caminho de autenticação, ambos fora do escopo da change
`harden-login` (já arquivada): contas desabilitadas são enumeráveis por
diferença de tempo de resposta (B1 — a checagem de `disabled_at` pula o
Argon2, ~4ms contra ~85ms dos demais casos), e a tabela `sessions` cresce sem
purga (I5 — cada login cria linha e nada remove expiradas/revogadas).

## What Changes

- Login: a verificação da senha passa a ocorrer antes da checagem de conta
  desabilitada — o Argon2 roda em todos os casos de falha, nivelando o tempo
  de resposta entre conta inexistente, senha errada e conta desabilitada.
  Resposta e status continuam idênticos (401 uniforme).
- Purga periódica de sessões: o reaper existente passa a remover, a cada
  ciclo, linhas de `sessions` expiradas ou revogadas há mais de um intervalo
  de carência. Sem migração de schema — a tabela já carrega `expires_at` e
  `revoked_at`.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `auth`: o requisito "Falha de autenticação não revela existência da conta"
  ganha um cenário fixando que conta desabilitada também é indistinguível
  por tempo; novo requisito de purga de sessões expiradas/revogadas com
  carência (grace period) para não apagar evidência recente de revogação.

## Impact

- `backend/app/api/auth.py`: reordenação de duas checagens na rota de login.
- `backend/app/services/sessions.py`: função de purga (`DELETE ... WHERE
  expires_at < ? OR revoked_at < ?`).
- `backend/app/services/reaper.py` (`run_reaper`): chamada da purga por
  ciclo; setting novo `WCUI_SESSION_PURGE_GRACE_HOURS` (default 24h).
- Testes: timing indistinguível (conta desabilitada executa o hash), purga
  remove só o que passou da carência, reaper integra a purga.
