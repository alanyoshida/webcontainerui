# Tasks

## 1. Schema e helpers de abertura/fechamento de run

- [x] 1.1 Adicionar a tabela `instance_runs` e seus índices (`idx_instance_runs_open`,
      `idx_instance_runs_started_at`, `idx_instance_runs_user_id`) em
      `backend/app/db.py`, seguindo o padrão `CREATE TABLE IF NOT EXISTS` já usado
      nas demais tabelas; verificar subindo o backend do zero e confirmando
      via `sqlite3 <db> ".schema instance_runs"` que a tabela e os índices existem.
- [x] 1.2 Implementar `_open_run` e `_close_run` em
      `backend/app/services/instances.py` conforme `design.md`, com teste cobrindo:
      abrir um run novo cria uma linha com `ended_at` nulo; chamar `_open_run` de
      novo para a mesma instância com run já aberto não duplica a linha; fechar
      um run define `ended_at`/`ended_reason`; fechar quando não há run aberto é
      no-op (nenhuma linha afetada).

## 2. Instrumentar as transições de lifecycle existentes

- [x] 2.1 Chamar `_open_run` no ramo de sucesso de `_provision_and_start` e no
      ramo de sucesso de `_resume_existing` que reinicia sem recriar; teste
      verificando que `create_instance` bem-sucedida e `_resume_existing`
      bem-sucedida deixam exatamente um run aberto para a instância, e que os
      ramos de erro (falha ao criar/iniciar) não abrem run nenhum.
- [x] 2.2 Adicionar o parâmetro `reason: str = "user_stop"` a `stop_instance` e
      substituir o `UPDATE instances SET state = 'stopped'` isolado por
      `_close_run(conn, instance_id, reason)` seguido da atualização de estado;
      teste verificando que parar via rota (sem argumento) fecha o run com
      `user_stop`, e que parar uma instância já parada continua idempotente
      (nenhum erro, nenhum novo fechamento).
- [x] 2.3 Atualizar `reap_idle_instances` para chamar `stop_instance(...,
      reason="idle_timeout")`; teste verificando que uma instância parada por
      ociosidade tem seu run fechado com `idle_timeout`, não `user_stop`.
- [x] 2.4 Chamar `_close_run(conn, row["id"], "reconciled")` em
      `reconcile_instance_states` junto do `UPDATE` de estado já existente;
      teste verificando que uma instância reconciliada (container morto por
      fora) tem seu run fechado com `reconciled`.
- [x] 2.5 Chamar `_close_run(conn, instance_id, "deleted")` em `delete_instance`
      antes do `UPDATE ... deleted_at`; teste verificando que excluir uma
      instância em execução fecha o run com `deleted`, e que excluir uma já
      parada não falha nem fecha run nenhum (no-op).

## 3. Backfill de runs abertos na inicialização

- [x] 3.1 Adicionar ao `lifespan` de `backend/app/main.py`, junto da
      reconciliação one-shot já existente, um passo que abre um run para toda
      instância `state = 'running'` sem run aberto, usando
      `COALESCE(last_seen_at, created_at)` como `started_at`; teste de
      integração simulando uma instância `running` pré-existente sem run e
      verificando que após o passo ela aparece com um run aberto com o
      `started_at` esperado, e que rodar o passo de novo não duplica o run.

## 4. Consultas de agregação

- [x] 4.1 Implementar consulta de instâncias com run aberto agora (join
      `instance_runs`/`instances`/`images`/`users`, duração calculada a partir de
      `started_at`) em um novo módulo de serviço; teste cobrindo múltiplas
      instâncias de usuários diferentes em execução simultânea.
- [x] 4.2 Implementar consulta paginada de runs dos últimos 30 dias (usuário,
      imagem, início, fim, duração, motivo); teste verificando que runs fora da
      janela de 30 dias não aparecem e que um run ainda aberto aparece com fim
      vazio e duração calculada até agora.
- [x] 4.3 Implementar agregado de horas totais por usuário e por grupo no
      período, incluindo runs em curso na soma (`COALESCE(ended_at, agora)`);
      teste cobrindo um usuário em dois grupos (horas contadas em ambos) e um
      run em curso contribuindo horas parciais.
- [x] 4.4 Implementar ranking de imagens por número de execuções e horas totais
      no período; teste verificando a ordenação por uso.
- [x] 4.5 Implementar distribuição de execuções encerradas por motivo no
      período; teste cobrindo os quatro motivos.
- [x] 4.6 Implementar série diária de instâncias ativas por dia no período
      (intervalo do run sobrepondo o dia); teste cobrindo um run que atravessa
      a meia-noite (conta em ambos os dias) e um dia sem nenhum run ativo
      (conta zero).
- [x] 4.7 Implementar cálculo de pico de simultaneidade por varredura
      (sweep-line) sobre os intervalos do período; teste cobrindo runs
      sobrepostos (pico maior que qualquer contagem diária) e runs sequenciais
      sem sobreposição (pico igual a um).

## 5. Endpoints administrativos

- [x] 5.1 Criar `backend/app/api/usage_metrics.py` com `APIRouter(dependencies=
      [Depends(require_admin)])` e `GET /api/admin/usage/live`, montado em
      `main.py`; teste verificando 403 para usuário não-admin e 200 com os
      dados esperados para admin.
- [x] 5.2 Adicionar `GET /api/admin/usage/runs` (histórico paginado); teste
      verificando paginação e filtro padrão de 30 dias.
- [x] 5.3 Adicionar `GET /api/admin/usage/summary` (agregados por usuário, por
      grupo, ranking de imagens, distribuição por motivo, série diária, pico de
      simultaneidade) retornados em um único payload; teste verificando a
      presença e o formato de cada seção do payload.

## 6. Painel administrativo no frontend

- [x] 6.1 Adicionar `@mui/x-charts` às dependências do frontend; verificar que
      `npm install` resolve sem conflitos de versão com o MUI já instalado.
- [x] 6.2 Criar `frontend/src/features/admin/UsageMetricsPanel.jsx` com a seção
      "Rodando agora" (consumindo `/api/admin/usage/live`); teste renderizando
      instâncias em execução com usuário, imagem e duração.
- [x] 6.3 Adicionar à mesma página a tabela histórica de 30 dias (consumindo
      `/api/admin/usage/runs`) com paginação; teste cobrindo a renderização de
      uma página de resultados e a navegação entre páginas.
- [x] 6.4 Adicionar os agregados (totais por usuário, totais por grupo, ranking
      de imagens, distribuição por motivo) e o gráfico de série diária
      (consumindo `/api/admin/usage/summary`, usando `@mui/x-charts` para a
      série); teste cobrindo a renderização de cada agregado a partir de um
      payload de exemplo.
- [x] 6.5 Registrar `UsageMetricsPanel` no array `TABS` de
      `frontend/src/pages/AdminPage.jsx`; teste verificando que a aba "Métricas
      de uso" aparece e troca o painel ativo ao ser clicada.

## 7. Verificação integrada

- [x] 7.1 Subir o backend e o frontend localmente (Docker + Vite dev server,
      como nas changes anteriores), criar e parar instâncias de teste por
      diferentes motivos (parada manual, ociosidade forçando o timeout, exclusão),
      e confirmar visualmente no painel "Métricas de uso" que a seção "Rodando
      agora", o histórico e os agregados refletem corretamente o que foi feito.

## Workflow follow-up

- Sincronizar a spec delta de `instance-usage-metrics` nas specs principais e
  arquivar a change em `openspec/changes/archive/` após a implementação e
  verificação acima estarem completas.
