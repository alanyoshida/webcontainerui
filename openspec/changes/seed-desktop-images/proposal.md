# Proposal

## Why

O provisionamento automático de catálogo cobre hoje só as imagens de agente de
código (`seed_agent_images`): um deploy do zero nasce com um catálogo de CLIs,
sem nenhuma imagem de desktop — o caso de uso original do portal — e o
administrador precisa registrar manualmente webtop/VS Code em toda instalação
nova. A capa padrão do VS Code já é asset versionado do repositório; falta a
entrada do catálogo.

## What Changes

- Novo seed de startup que garante entradas de **pull** de desktop no
  catálogo: as três variantes de webtop do produto (XFCE `:latest`,
  `:ubuntu-kde` e `:alpine-mate`) e o VS Code
  (`lscr.io/linuxserver/vscode:latest`) — o conjunto completo de desktops
  cadastrados no catálogo de referência —, cada uma baixada em segundo plano
  (mesmo fluxo do cadastro manual: `run_pull` com progresso, falha isolada e
  retry-pull disponível).
- Idempotente e respeitoso ao administrador: entrada que já existe no
  catálogo (por repositório+tag) é apenas ignorada — estado, limites
  editados, desabilitação e capa manual do admin nunca são sobrescritos.
- Ordem no lifespan: o seed de desktops roda **antes** do seed de capas, para
  que a capa padrão (asset já versionado no repositório) seja aplicada no
  mesmo boot em que a entrada nasce.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `image-catalog`: novo requisito — as entradas de desktop padrão são
  garantidas no startup por download, sem duplicar nem sobrescrever o que o
  administrador já configurou, e falha de download não impede o startup nem
  as demais.

## Impact

- `backend/app/services/desktop_images.py` (novo, espelho simplificado do
  seed de agentes) e `backend/app/main.py` (chamada no lifespan, entre os
  seeds existentes).
- Sem migração de schema, sem variável de configuração nova, sem dependência
  nova.
- Testes: unidade do seed (banco vazio cria e dispara pull; entrada
  existente é respeitada; falha isolada) e verificação no stack dev de que
  não há duplicação.
