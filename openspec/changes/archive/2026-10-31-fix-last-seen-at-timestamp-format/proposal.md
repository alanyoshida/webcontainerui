# Proposal

## Why

`instances.last_seen_at` é gravado por `activity.py` usando
`datetime.now(timezone.utc).isoformat(...)`, que inclui o sufixo `+00:00`,
enquanto toda outra coluna de timestamp do banco (`created_at`,
`started_at`, `ended_at`, `deleted_at`) é gravada via `datetime('now')` do
SQLite, sem sufixo. Essa divergência de formato hoje só funciona por sorte
nas comparações de string usadas no cálculo de ociosidade, mas quebra de
verdade em `backfill_open_runs` (introduzido na change
`admin-instance-usage-metrics`): quando uma instância está `running` no
restart do backend e já tem `last_seen_at` gravado, esse valor com `+00:00`
é copiado para `instance_runs.started_at`, e a próxima leitura de métricas
de uso sobre essa linha derruba `/api/admin/usage/*` com 500, porque
`datetime.strptime` não aceita o sufixo.

## What Changes

- `activity.py` (`_now_iso`) e `reaper.py` (`_cutoff_iso`) passam a gerar
  timestamps no mesmo formato sem offset usado pelo resto do banco
  (`YYYY-MM-DD HH:MM:SS`), eliminando a divergência na origem.
- `backend/app/db.py` ganha um passo de migração, no mesmo padrão de
  `_migrate_add_icon_path`, que normaliza `last_seen_at` já gravado no
  formato antigo (remove o sufixo `+00:00`) em bancos existentes.
- `usage_metrics._parse` também passa a aceitar os dois formatos (com e sem
  offset), como proteção adicional — não depende só da migração ter
  rodado, cobrindo qualquer linha que escape dela por algum motivo.
- Nenhum comportamento observável pelo usuário ou administrador muda: os
  mesmos instantes reais (em UTC) continuam sendo os mesmos, apenas
  representados de forma consistente. É uma correção de bug, não uma nova
  regra de negócio.

## Capabilities

### New Capabilities
(nenhuma)

### Modified Capabilities
(nenhuma — nenhum requisito de `desktop-instances` ou
`instance-usage-metrics` muda; os dois já especificam o comportamento
correto, isto corrige uma divergência de implementação que podia violá-lo)

## Impact

- **Backend**: `backend/app/services/activity.py`, `backend/app/services/reaper.py`,
  `backend/app/services/usage_metrics.py`, `backend/app/db.py`.
- **Dados**: migração idempotente e aditiva (só normaliza valores já
  existentes no formato antigo); nenhuma tabela ou coluna muda de forma.
