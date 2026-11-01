# Design

## Context

A rota de login (`backend/app/api/auth.py`) já executa o hash dummy quando o
e-mail não existe (herança da criação original) e, desde `harden-login`, passa
pelo limitador antes de qualquer consulta. Hoje a ordem interna é: consulta →
`disabled_at` → `verify_password` — a checagem de desabilitação antecede o
Argon2 e cria o canal lateral de ~20x medido no pentest. O reaper
(`backend/app/services/reaper.py`) já roda em ciclo
(`WCUI_REAPER_INTERVAL_SECONDS`, default 60s) com `stop_instance`/reconcile, e
é o hospedeiro natural para uma purga de tabela.

## Goals / Non-Goals

**Goals:**

- Tempo de resposta do login uniforme entre todos os casos de falha.
- Tabela `sessions` limitada ao uso recente, sem migração de schema.
- Nenhuma mudança observável para quem usa credenciais corretas.

**Non-Goals:**

- Novos eventos de log (change `security-audit-log`).
- Rotação/purga de outras tabelas (`instance_runs` é histórico de métricas e
  permanece).
- Mudar o limitador ou a política de expiração.

## Decisions

### D1 — Hash antes da checagem de desabilitação

Reordenar para: consulta → `verify_password` → `disabled_at`. O Argon2 passa a
rodar em toda tentativa com e-mail existente, desabilitada ou não; o hash dummy
já cobre e-mail inexistente. A resposta continua o mesmo 401 com o mesmo corpo
para todos os casos. Detalhe de custo: conta desabilitada com senha correta
agora paga Argon2 + checagem — irrelevante (conta desabilitada não autentica de
qualquer forma).

Alternativa rejeitada: executar o hash dummy também no ramo desabilitado,
mantendo a ordem — funcionaria para o timing, mas deixa a ordem das checagens
confusa; a reordenação é menor e elimina a classe do problema (nenhum ramo de
falha pula a verificação).

### D2 — Purga no reaper com carência configurável

`purge_sessions(conn, grace_hours)` em `services/sessions.py`:
`DELETE FROM sessions WHERE expires_at < ? OR (revoked_at IS NOT NULL AND revoked_at < ?)`,
com o corte em UTC no mesmo formato das demais colunas (`YYYY-MM-DD HH:MM:SS`).
Chamada a cada ciclo do `run_reaper`, junto das tarefas existentes — a tabela é
pequena e o DELETE é barato; não justifica cadência própria.

A carência (default 24h, `WCUI_SESSION_PURGE_GRACE_HOURS`, `ge=1`) preserva
registros revogados/expirados recentes: o logout e a desabilitação de conta
gravam `revoked_at`, e a janela mantém rastro consultável para depuração e
para o log de auditoria da change `security-audit-log` (que poderá ler eventos
antes da purga). Expiradas são inúteis para autenticação desde o segundo em
que expiram — a carência é só cortesia operacional.

Alternativa rejeitada: purgar apenas no startup (`lifespan`) — um portal que
roda por meses acumularia entre deploys; o ciclo do reaper já existe.

### D3 — Sem flag de desligar

A purga é incondicional (grace via setting). Um setting extra "desligar purga"
adicionaria superfície de configuração para benefício nulo — diferente do
`harden-login`, aqui não há caso de uso legítimo para acumular sessões mortas.

## Risks / Trade-offs

- [DELETE concorrente com login] → SQLite WAL + `busy_timeout` 5s já cobrem; o
  DELETE raramente briga com INSERT de nova sessão e leva milissegundos.
- [Alguém dependia de sessões antigas persistirem] → sessões expiradas/
  revogadas não autenticam desde a expiração/revogação; a purga só remove
  linha morta. Difícil degradar algo observável.
- [Reaper falha → purga não roda] → mesma semântica best-effort existente do
  reaper; nada acumula de forma irreversível.

## Migration Plan

Deploy único, sem janela especial: a reordenação é invisível e a purga começa
a remover linhas antigas no primeiro ciclo. Rollback: `git revert` — linhas já
purgadas eram estado morto, não há restauração necessária.
