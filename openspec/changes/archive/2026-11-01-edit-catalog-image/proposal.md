# Proposal

## Why

Uma entrada do catálogo, uma vez registrada, não pode mais ser editada: não
existe endpoint de edição (nome, limites de recurso, porta) nem forma de
**reativar** uma entrada desabilitada — o disable é uma rua de mão única. O
administrador que erra um limite ou um nome teria que recriar a entrada (e os
grants de acesso a ela). Além disso, a flag `harden_desktop` (achado I1 do
pentest de 2026-11-01) é aceita, armazenada e devolvida pela API sem nenhum
efeito no sistema — falsa sensação de segurança exposta a quem cadastra.

## What Changes

- `PATCH /api/admin/images/{id}` para edição do conjunto seguro de campos:
  `display_name`, `shm_size_mb`, `mem_limit_mb`, `cpu_limit`, `port` — só os
  campos recebidos são alterados; identidade (`repository`/`tag`) e estado de
  provisionamento ficam de fora e permanecem imutáveis.
- `POST /api/admin/images/{id}/enable` para reativar entrada desabilitada
  (idempotente), espelhando o disable existente.
- Remoção do `harden_desktop` da API de cadastro/resposta e do código
  (coluna fica dormente no banco, sem migração).
- Frontend: diálogo de edição no painel do catálogo (reaproveitando o
  formulário de criação) e botão de reativação para entradas desabilitadas.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `image-catalog`: novo requisito — o administrador edita os campos de
  apresentação e recurso de uma entrada, com identidade imutável; o
  requisito de desabilitação ganha o cenário de reativação. A remoção do
  `harden_desktop` não altera requisito especificado algum (a flag nunca
  foi especificada — é limpeza de implementação).

## Impact

- `backend/app/api/images.py` (PATCH + enable), `backend/app/services/images.py`
  (função de edição), `backend/app/api/images.py`/`services/images.py`
  (remoção do `harden_desktop` do cadastro/resposta).
- Frontend: `ImagesPanel.jsx` (diálogo de edição + reativar),
  `client.js` (duas chamadas novas).
- Instâncias: efeito de limites/porta editados segue o fluxo existente —
  valem para instâncias criadas depois; as existentes aplicam ao serem
  atualizadas pelo dono ("atualizar imagem" recria o container da linha
  atual do catálogo). Nenhuma instância é recriada automaticamente pela edição.
- Testes: edição parcial, validação, imutabilidade de identidade, enable
  idempotente, remoção do `harden_desktop`.
