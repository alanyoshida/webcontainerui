# Proposal

## Why

O catálogo não oferece editor de código: hoje o usuário escolhe entre desktops
webtop completos ou CLIs de agente em terminal. Além disso, imagens `pull`
não têm ciclo de atualização — `retry-pull` só aceita entrada em `failed`,
instâncias existentes nunca migram de versão (o container antigo é apenas
religado) e ninguém consegue saber qual versão está rodando. Com o VS Code
esse ciclo se torna visível: a LinuxServer rebuilda a imagem a cada release.

## What Changes

- Registra `lscr.io/linuxserver/vscode:latest` no catálogo (pull, porta 3000,
  limites padrão do portal) com capa própria. A imagem roda o VS Code desktop
  completo sobre a base Selkies — o spike confirmou o contrato inteiro do
  portal (`SUBFOLDER`, basic auth `CUSTOM_USER`/`PASSWORD`, `?resize=scale`,
  `SELKIES_ENABLE_SHARING=false`) sem alterar proxy nem runtime.
- Admin pode atualizar a imagem de uma entrada `ready` do catálogo: re-pull
  do tag em segundo plano (estado volta a `pulling`, bloqueando instanciação
  até concluir). Hoje `retry-pull` só aceita entrada em `failed`.
- O dono pode atualizar a própria instância: para (se rodando), remove o
  container mantendo o volume e recria do tag atual — o caminho de recriação
  já existente (`_provision_and_start`) reaproveita volume e credenciais.
- Versão visível: o portal captura a versão da imagem no pull (label
  `build_version` das imagens LinuxServer; digest curto como fallback) e a
  mostra no catálogo; a instância mostra a versão com que seu container foi
  criado e um badge "desatualizada" quando for anterior à do catálogo.
- Fora de escopo: suporte a `cap_add` (o spike mostrou que o keyring nem roda
  nesta imagem, com ou sem `IPC_LOCK`), tags pinadas e atualização automática
  de instância.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `image-catalog`: re-pull de entrada `ready` (atualização de imagem) e
  registro/exposição da versão da imagem baixada.
- `desktop-instances`: ação de atualizar a própria instância mantendo os
  arquivos, e visibilidade da versão do container com indicador de
  desatualização.

## Impact

- **Backend**: `runtime/protocol.py` + `docker_runtime.py` (inspeção de label
  da imagem após o pull), `services/image_pull.py` / `services/images.py`
  (captura de versão e reabertura de entrada `ready`), `services/instances.py`
  (ação de atualização), migração idempotente em `db.py` (coluna de versão em
  `images` e em `instances`), API admin e API de instâncias.
- **Frontend**: botão "Atualizar imagem" no painel admin (reusa o progresso de
  pull existente), versão no card do catálogo, botão "Atualizar" na visão de
  sessão com diálogo de confirmação e badge "desatualizada".
- **Sem mudanças**: proxy de sessão, auth, runtime de criação de containers,
  specs de agente CLI.
