# Design

## Context

Ver proposal.md para a motivação. Estado atual relevante:

- `images` só suporta `repository`/`tag` como referência pronta pra
  `docker pull` ([backend/app/services/image_pull.py:9-26](../../../backend/app/services/image_pull.py#L9),
  [backend/app/services/images.py:27-63](../../../backend/app/services/images.py#L27)).
  Não existe `docker build` em nenhum lugar do backend.
- `ContainerSpec` ([backend/app/runtime/protocol.py:22-35](../../../backend/app/runtime/protocol.py#L22))
  não tem campo de porta, e containers nunca publicam porta no host
  (`HostConfig` sem `PortBindings`,
  [backend/app/runtime/docker_runtime.py:69-85](../../../backend/app/runtime/docker_runtime.py#L69)) — são
  alcançados só pela rede Docker interna, por nome de container.
- `session_proxy.py` encaminha para uma porta fixa, `3000`, pra toda
  instância ([backend/app/api/session_proxy.py:40-41](../../../backend/app/api/session_proxy.py#L40)).
- As env vars injetadas em todo container são específicas do
  LinuxServer/Selkies e incondicionais —
  `SUBFOLDER`, `CUSTOM_USER`, `PASSWORD`, `SELKIES_ENABLE_SHARING`,
  `SELKIES_ENABLE_SHARED`, `PUID`, `PGID`, `TZ`
  ([backend/app/services/instances.py:105-117](../../../backend/app/services/instances.py#L105)).
- O portal já fala com o daemon do host via `/var/run/docker.sock`
  montado ([deploy/docker-compose.yml:44](../../../deploy/docker-compose.yml#L44)), por `aiodocker`
  ([backend/app/runtime/docker_runtime.py](../../../backend/app/runtime/docker_runtime.py)), sempre
  assíncrono (nenhuma chamada síncrona ao Docker).
- `_INSTANCE_SELECT` já faz `JOIN` com `images` pra expor campos da
  imagem junto da instância
  ([backend/app/services/instances.py:18-22](../../../backend/app/services/instances.py#L18)).

## Goals / Non-Goals

**Goals:**
- Catálogo com 5 entradas fixas (Claude Code CLI, Hermes, Agy, OpenCode,
  oh-my-pi), provisionadas automaticamente pelo portal, acessíveis pelo
  mesmo mecanismo de sessão que já existe.
- Provisionamento por build local como alternativa ao pull, reusando a
  mesma máquina de estados (`pulling`/`ready`/`failed`) já especificada.
- Porta de encaminhamento por imagem, substituindo o literal fixo `3000`.

**Non-Goals:**
- UI de admin para "build from Dockerfile" genérico — decidido
  explicitamente fora de escopo; só o seed automático das 5 imagens usa
  build.
- Gestão de segredos/API keys dos agentes pelo portal — decidido
  explicitamente fora de escopo; usuário configura manualmente dentro do
  terminal.
- Qualquer integração nova de desktop remoto/Selkies — ttyd é só um
  servidor HTTP/WS de terminal, sem GPU nem WebRTC.
- Mudança de semântica do ciclo de vida de instância — `desktop-instances`
  permanece inalterada.

## Decisions

### D1: Terminal web genérico (ttyd) em vez de integração por ferramenta

Das 5 ferramentas, só o OpenCode tem UI web nativa (`opencode web`);
Hermes, Agy, Claude Code CLI e oh-my-pi são só terminal. O ttyd é um
binário único que serve um terminal (xterm.js) por HTTP/WS, com
`--base-path` (equivalente direto do `SUBFOLDER` já usado) e
`--credential user:pass` (HTTP Basic Auth — o mesmo mecanismo que
`session_proxy.py` já injeta). Isso deixa as 5 imagens passando pelo
exato mesmo caminho de proxy, sem lidar com nenhum protocolo novo.

Alternativa considerada: desktop Selkies completo + navegador em kiosk
apontado pra UI web de cada ferramenta. Rejeitada: mais pesada (GPU/WebRTC
por instância) e a maioria das ferramentas não tem UI web nenhuma pra
apontar o navegador.

Alternativa considerada: proxy direto pro protocolo nativo de cada
ferramenta (ex.: o servidor HTTP do `opencode web`). Mantida como opção
por imagem — como a porta já passa a ser configurável por imagem (D3), o
Dockerfile do OpenCode PODE optar por rodar `opencode web` direto em vez
de embrulhar em ttyd; as outras 4 não têm essa opção por não terem UI web.

### D2: Um Dockerfile por agente, com uma base comum

```
agent-images/
  _base/Dockerfile        # imagem base + ttyd + entrypoint comum
  claude-code/Dockerfile  # FROM wcui-agent-base + CLI do Claude Code
  hermes/Dockerfile
  agy/Dockerfile
  opencode/Dockerfile
  oh-my-pi/Dockerfile
```

O entrypoint comum lê `SUBFOLDER`/`CUSTOM_USER`/`PASSWORD` (já injetadas
hoje em toda instância) e executa
`ttyd --base-path "$SUBFOLDER" --credential "$CUSTOM_USER:$PASSWORD" -p <porta> <comando-do-agente>`.
Cada Dockerfile de agente só define `<comando-do-agente>`.

Uma imagem por agente (em vez de uma imagem genérica onde o usuário digita
qual CLI rodar) foi decidido com o usuário: mantém a UX atual do catálogo,
onde escolher a imagem já escolhe a ferramenta.

### D3: Porta de encaminhamento por imagem, não mudança de protocolo

Nova coluna `images.port` (padrão `3000`, o valor hoje implícito),
propagada por `_INSTANCE_SELECT` como `image_port` e lida por
`default_backend_base_url` em `session_proxy.py` no lugar do literal
`3000`. Como containers nunca publicam porta no host, essa coluna só
afeta qual porta o *proxy* discando — `ContainerSpec` permanece sem campo
de porta, sem mudança em `create_container`.

### D4: Build é só um caminho interno de provisionamento, sem endpoint de admin

Nova operação `ContainerRuntime.build_image(context_dir, repository, tag) -> AsyncIterator[PullProgress]`,
ao lado de `pull_image`, implementada sobre `aiodocker` (`images.build`,
streaming de eventos do build), reusando o mesmo formato `PullProgress`
que `mark_pull_progress`/`mark_pull_ready`/`mark_pull_failed` já
consomem sem alteração.

Um novo módulo `backend/app/services/agent_images.py` (paralelo a
`image_pull.py`) roda no startup: para cada uma das 5 definições de
agente, insere a linha em `images` só se a combinação repositório/tag
ainda não existir (idempotente, mesmo padrão de `_open_run`), e então
builda do mesmo jeito que `run_pull` já faz o pull.

Build não é exposto no endpoint de admin de criar imagem — decidido
explicitamente com o usuário, pra não abrir superfície nova de
segurança (caminho de Dockerfile arbitrário vindo de um campo de admin)
sem necessidade no escopo atual.

### D5: Falha de uma imagem no seed não derruba o startup

Cada build do seed é isolado: a falha de uma das 5 imagens marca só
aquela entrada como `failed` (via `mark_pull_failed`, já existente) e não
propaga exceção pro `lifespan` — as demais imagens seguem sendo
provisionadas e o portal sobe normalmente.

## Risks / Trade-offs

- [Risco] Buildar 5 imagens a cada subida do portal soma tempo de boot →
  [Mitigação] cache de camadas do Docker torna o rebuild de um
  Dockerfile inalterado quase instantâneo; só uma mudança real no
  conteúdo da imagem dispara rebuild de verdade.
- [Risco] Cada agente precisa de API key própria, que o portal não vê nem
  valida → [Mitigação] decidido explicitamente fora de escopo com o
  usuário; fica documentado no próprio primeiro acesso ao terminal.
- [Risco] `docker build` bloquear o event loop → [Mitigação] mesmo padrão
  assíncrono de `pull_image` ([docker_runtime.py:57-67](../../../backend/app/runtime/docker_runtime.py#L57)), tudo
  via `aiodocker`, consistente com a decisão original do projeto de nunca
  travar o loop com chamada síncrona ao Docker.
- [Risco] Versões das CLIs fixadas nos Dockerfiles ficam desatualizadas
  com o tempo → [Mitigação] fora de escopo desta change; mesmo ônus de
  manutenção de qualquer imagem base fixada, fica pra uma change futura
  se virar problema.

## Migration Plan

- Puramente aditivo: coluna `images.port` nova (com padrão), módulo
  `agent_images.py` novo, Dockerfiles novos sob `agent-images/`. Nenhum
  dado existente é migrado.
- Deploy: na primeira subida após o deploy, as 5 imagens buildam e se
  registram sozinhas, sem passo manual.
- Rollback: reverter a imagem do portal remove a rotina de seed; as
  linhas de `images` já criadas (incluindo as 5 de agente, já buildadas)
  continuam existindo como entradas de catálogo normais — inofensivo, o
  administrador pode desabilitá-las.

## Open Questions

- Fixar a versão exata de cada CLI nos Dockerfiles ou seguir `latest`?
  Fica pra quando os Dockerfiles forem escritos nas tasks; não afeta a
  arquitetura nem as specs.
