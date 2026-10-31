# Proposal

## Why

O sistema hoje só guarda o estado atual de cada instância (`state`, sobrescrito a cada
transição), sem nenhum registro de quando um ciclo de execução começou ou terminou.
Isso torna impossível para um administrador validar quantas instâncias estão em uso,
por quanto tempo cada uma rodou e quais usuários as iniciaram — tanto agora quanto no
histórico recente.

## What Changes

- Nova tabela `instance_runs` registrando cada ciclo start→stop de uma instância:
  usuário, imagem, início, fim (nulo enquanto em execução) e motivo do término
  (parada pelo usuário, idle timeout, reconciliação por queda externa, ou exclusão
  da instância).
- Os pontos de transição existentes (`stop_instance`, reap por ociosidade,
  reconciliação de estado, exclusão de instância) passam a abrir/fechar o registro
  correspondente em `instance_runs`, sem alterar o comportamento de lifecycle já
  especificado em `desktop-instances`.
- Novos endpoints administrativos (reaproveitando `require_admin`) expondo:
  instâncias em execução agora (com duração em curso), execuções históricas dos
  últimos 30 dias, agregados de horas totais por usuário e por grupo, ranking de
  imagens mais usadas, distribuição por motivo de término, série temporal de
  instâncias ativas por dia e pico de instâncias simultâneas no período.
- Nova aba "Métricas de uso" no painel administrativo, com uma seção "Rodando
  agora" separada da tabela histórica, mais os agregados e visualizações acima.
- Nenhuma retenção automática é introduzida: o histórico de execuções cresce
  indefinidamente no banco; o painel apenas filtra a visualização para os
  últimos 30 dias por padrão.

## Capabilities

### New Capabilities
- `instance-usage-metrics`: governa o registro do histórico de execuções de
  instâncias (quem, qual imagem, início, fim, motivo do término) e a visibilidade
  administrativa sobre esse uso — ao vivo e histórico, individual e agregado.

### Modified Capabilities
(nenhuma — o comportamento de lifecycle de `desktop-instances` não muda; este
change apenas observa e registra as transições já existentes, sem alterar
estados, prazos de idle timeout ou critérios de reconciliação.)

## Impact

- **Backend**: nova tabela/migração em `backend/app/db.py`; instrumentação em
  `backend/app/services/instances.py` (`stop_instance`, `delete_instance`,
  provisionamento) e `backend/app/services/reaper.py` (`reap_idle_instances`,
  `reconcile_instance_states`) para abrir/fechar registros de execução; novo
  módulo de serviço para consultas agregadas; novo router admin (ex.:
  `backend/app/api/usage_metrics.py`) montado sob `/api/admin`.
- **Frontend**: novo painel `frontend/src/features/admin/UsageMetricsPanel.jsx`,
  registrado em `frontend/src/pages/AdminPage.jsx` (array `TABS`); provável nova
  dependência de gráfico para a série temporal (o projeto não tem nenhuma
  biblioteca de charting hoje) — a escolha específica fica para `design.md`.
- **Dados**: nenhuma migração destrutiva; `instance_runs` é uma tabela nova,
  aditiva, sem impacto nas tabelas existentes além de novas referências a
  `instances`, `users` e `images`.
