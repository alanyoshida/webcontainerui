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
- `retry_pull` só reabre a entrada para um novo `docker pull`
  ([backend/app/services/images.py:91-100](../../../backend/app/services/images.py#L91));
  `images` não registra se a entrada veio de pull ou de build, nem um hash
  do contexto — não há como decidir retry ou rebuild sem essa informação.
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
- Rebuild de imagem de agente apenas quando o conteúdo do Dockerfile/contexto
  muda, comparando um hash do contexto guardado na entrada.
- Retry correto tanto para download quanto para build, conforme o tipo de
  provisionamento da entrada.
- Imagem base comum construída e marcada antes das 5 imagens de agente.
- Porta de encaminhamento por imagem, substituindo o literal fixo `3000`, e
  injetada no container como `PORT`.

**Non-Goals:**
- UI de admin para "build from Dockerfile" genérico — decidido
  explicitamente fora de escopo; só o seed automático das 5 imagens usa
  build.
- Expor a porta de encaminhamento na API/UI de admin — decidido
  explicitamente fora de escopo; só o seed a define.
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
`session_proxy.py` já injeta). O comando também precisa de `--writable`
(sem ele o ttyd é somente leitura e não aceita digitação) e escuta na porta
vinda de `PORT`, injetada pelo portal (D3). Isso deixa as 5 imagens passando
pelo exato mesmo caminho de proxy, sem lidar com nenhum protocolo novo.

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

O entrypoint comum lê `SUBFOLDER`/`CUSTOM_USER`/`PASSWORD`/`PORT` (as três
primeiras já injetadas hoje em toda instância; `PORT` passa a ser injetada,
D3) e executa
`ttyd --writable --base-path "$SUBFOLDER" --credential "$CUSTOM_USER:$PASSWORD" -p "$PORT" <comando-do-agente>`.
Cada Dockerfile de agente só define `<comando-do-agente>`.

Uma imagem por agente (em vez de uma imagem genérica onde o usuário digita
qual CLI rodar) foi decidido com o usuário: mantém a UX atual do catálogo,
onde escolher a imagem já escolhe a ferramenta.

A imagem base comum é construída e marcada como `wcui-agent-base` pelo seed
antes de qualquer imagem de agente (D6); sem esse passo o `FROM` dos
Dockerfiles de agente falharia.

### D3: Porta de encaminhamento por imagem, não mudança de protocolo

Nova coluna `images.port` (padrão `3000`, o valor hoje implícito),
propagada por `_INSTANCE_SELECT` como `image_port` e lida por
`default_backend_base_url` em `session_proxy.py` no lugar do literal
`3000`. A mesma porta é injetada no container como `PORT` em `_build_spec`
([backend/app/services/instances.py:89](../../../backend/app/services/instances.py#L89)),
então o processo de interface escuta exatamente onde o proxy disca.
`ContainerSpec` permanece sem campo de porta — a porta viaja pelo `env` já
existente, sem mudança em `create_container`. A coluna é preenchida só pelo
seed (D4); a API de admin de criação de imagem não a expõe.

### D4: Build é só um caminho interno de provisionamento, sem endpoint de admin

Nova operação `ContainerRuntime.build_image(context_dir, repository, tag) -> AsyncIterator[PullProgress]`,
ao lado de `pull_image`, implementada sobre `aiodocker` (`images.build`,
streaming de eventos do build), reusando o mesmo formato `PullProgress`
que `mark_pull_progress`/`mark_pull_ready`/`mark_pull_failed` já
consomem sem alteração.

Duas colunas novas em `images` distinguem a origem e controlam o rebuild:
`provision_kind` (`'pull'` | `'build'`, padrão `'pull'` para preservar as
entradas existentes e o fluxo de admin) e `build_hash` (hash do conteúdo do
contexto de build). O hash de cada agente cobre tanto o diretório do agente
quanto `agent-images/_base`, já que uma mudança na base também exige
reconstruir as imagens derivadas.

Um novo módulo `backend/app/services/agent_images.py` (paralelo a
`image_pull.py`) roda no startup: para cada uma das 5 definições de
agente, insere a linha em `images` só se a combinação repositório/tag
ainda não existir (idempotente, mesmo padrão de `_open_run`); se já
existir como build, reconstrói somente quando o hash calculado difere do
`build_hash` gravado. O build em si reusa `run_pull`/`mark_pull_*`, como o
pull já faz.

Build não é exposto no endpoint de admin de criar imagem — decidido
explicitamente com o usuário, pra não abrir superfície nova de
segurança (caminho de Dockerfile arbitrário vindo de um campo de admin)
sem necessidade no escopo atual.

### D5: Falha de uma imagem no seed não derruba o startup

Cada build do seed é isolado: a falha de uma das 5 imagens marca só
aquela entrada como `failed` (via `mark_pull_failed`, já existente) e não
propaga exceção pro `lifespan` — as demais imagens seguem sendo
provisionadas e o portal sobe normalmente.

### D6: A base é construída antes dos agentes

O seed constrói `agent-images/_base` e a marca como `wcui-agent-base` antes
de iniciar os builds dos 5 agentes. Essa ordem é uma dependência real dos
Dockerfiles (`FROM wcui-agent-base`), não um detalhe de implementação: se a
base falhar, as 5 imagens de agente falham individualmente (D5) e o portal
ainda sobe.

### D7: Retry é unificado por `provision_kind`

A entrada de retry existente passa a olhar `images.provision_kind`: para
`'pull'` agenda `run_pull`, para `'build'` agenda o build do contexto da
imagem. Sem isso, o retry de uma imagem buildada tentaria `docker pull` de
um repositório/tag que só existe localmente e falharia sempre.

### D8: O seed aguarda os builds no `lifespan`

Decidido com o usuário: o startup aguarda a construção da base e das 5
imagens para que o catálogo já esteja consistente quando o portal começa a
aceitar tráfego. O custo é boot mais lento no primeiro deploy ou após
mudança de contexto; o hash (D4) evita pagá-lo nas subidas em que nada
mudou. A falha de um build não propaga (D5), então o `await` não impede o
portal de subir.

## Risks / Trade-offs

- [Risco] O startup aguardar os builds atrasa o healthcheck do portal →
  [Mitigação] o hash do contexto (D4) evita rebuild quando nada mudou; no
  primeiro deploy ou após mudança real o custo é aceito em troca de o
  catálogo estar pronto ao fim do startup, e a falha isolada (D5) nunca
  impede o portal de subir.
- [Risco] Hash do contexto não detectar mudança relevante (ex.: conteúdo
  baixado pela rede no build) → [Mitigação] o hash cobre os arquivos de
  contexto versionados; mudanças externas de CLI ficam fora do escopo,
  como já registrado em Open Questions.
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

- Puramente aditivo: colunas `images.port`, `images.provision_kind` e
  `images.build_hash` novas (com padrões que preservam as linhas
  existentes como `port=3000` e `provision_kind='pull'`), módulo
  `agent_images.py` novo, Dockerfiles novos sob `agent-images/`. Nenhum
  dado existente é migrado.
- Deploy: na primeira subida após o deploy, a base e as 5 imagens buildam e
  se registram sozinhas, aguardadas pelo `lifespan`, sem passo manual.
  Subidas seguintes só reconstroem o que mudou de contexto.
- Rollback: reverter a imagem do portal remove a rotina de seed; as
  linhas de `images` já criadas (incluindo as 5 de agente, já buildadas)
  continuam existindo como entradas de catálogo normais — inofensivo, o
  administrador pode desabilitá-las.

## Open Questions

- Fixar a versão exata de cada CLI nos Dockerfiles ou seguir `latest`?
  Fica pra quando os Dockerfiles forem escritos nas tasks; não afeta a
  arquitetura nem as specs.
