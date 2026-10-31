# Tasks

## 1. Corrigir a origem dos timestamps

- [x] 1.1 Trocar `_now_iso` em `backend/app/services/activity.py` para
      `datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")`; teste
      verificando que o valor gravado em `last_seen_at` não contém `+`
      nem `Z`.
- [x] 1.2 Aplicar a mesma mudança a `_cutoff_iso` em
      `backend/app/services/reaper.py`; confirmar que os testes já
      existentes de ociosidade (`find_idle_running_instances`,
      `reap_idle_instances`) continuam passando sem alteração — eles
      validam o comportamento, não o formato da string, então uma
      regressão apareceria como teste quebrado.

## 2. Migrar `last_seen_at` já gravado no formato antigo

- [x] 2.1 Adicionar `_migrate_normalize_last_seen_at` em
      `backend/app/db.py`, chamada em `init_db` junto de
      `_migrate_add_icon_path`; teste no padrão de
      `test_init_db_adiciona_icon_path_a_banco_sem_a_coluna`: cria um
      banco com uma linha de `last_seen_at` no formato antigo
      (`...+00:00`), roda `init_db`, confirma que o valor foi normalizado
      para os 19 caracteres sem sufixo.
- [x] 2.2 Teste cobrindo que rodar a migração sobre um banco já
      normalizado (ou sem nenhuma linha com `last_seen_at`) não altera
      nada e não falha.

## 3. Parsing tolerante em `usage_metrics`

- [x] 3.1 Atualizar `_parse` em `backend/app/services/usage_metrics.py`
      para aceitar `YYYY-MM-DD HH:MM:SS` e qualquer timestamp ISO com
      offset, via fallback para `datetime.fromisoformat`; teste
      verificando que `duration_seconds` e as agregações não quebram
      quando um `instance_runs.started_at` (que pode ter vindo de
      `backfill_open_runs` lendo um `last_seen_at` legado) está no
      formato com offset.
- [x] 3.2 Teste de regressão reproduzindo o cenário real do bug: uma
      instância `running` no boot com `last_seen_at` no formato antigo —
      `backfill_open_runs` abre o run com esse valor como `started_at`, e
      uma chamada a `list_live_runs`/`duration_seconds` sobre essa linha
      não levanta exceção.

## 4. Verificação integrada

- [x] 4.1 Rodar a suíte completa do backend e confirmar que nada quebrou.
- [x] 4.2 Subir o backend contra o banco de desenvolvimento (que já tem
      `last_seen_at` no formato antigo, confirmado durante a exploração)
      e verificar nos logs/pelo painel "Métricas de uso" que
      `/api/admin/usage/live` responde normalmente, sem 500, e que a
      linha antiga aparece com `last_seen_at` já normalizado no banco.
