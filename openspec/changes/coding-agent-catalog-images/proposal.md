# Proposal

## Why

Os usuários querem acessar agentes de código em CLI (Claude Code, Hermes, Agy,
OpenCode, oh-my-pi) pelo navegador, com o mesmo ciclo de vida de
iniciar/parar/excluir já oferecido para os desktops webtop. A maioria dessas
ferramentas não tem interface web própria — o denominador comum é o terminal —
e o catálogo hoje só sabe provisionar uma entrada via `docker pull` de um
registry, o que não serve para imagens que precisam ser construídas a partir
de um Dockerfile mantido neste repositório.

## What Changes

- Novo conjunto mantido de entradas de catálogo para os 5 agentes de código
  (Claude Code CLI, Hermes, Agy, OpenCode, oh-my-pi), cada uma rodando um
  terminal web leve (ttyd) que inicia o agente correspondente, provisionado
  automaticamente pelo portal ao subir — sem exigir ação do administrador.
- Entradas do catálogo passam a admitir provisionamento por build local de
  Docker (Dockerfile + contexto versionados no repositório), como alternativa
  ao `docker pull` por registry já existente. O portal reconstrói uma imagem
  de build somente quando o conteúdo do Dockerfile/contexto muda (hash do
  contexto registrado na entrada), e o build falho pode ser repetido, assim
  como já vale para o download falho.
- Entradas do catálogo passam a admitir uma porta de encaminhamento própria
  (padrão 3000, mesmo valor assumido hoje), para containers cujo processo de
  interface não escuta na porta fixa usada pelos desktops webtop. A porta é
  definida internamente pelo seed; não é exposta na API de admin de criação
  de imagem.
- O portal injeta a porta de encaminhamento da entrada como variável de
  ambiente `PORT` no container, para que o processo de interface (ttyd)
  escute na mesma porta que o proxy usa.
- Uma imagem base comum (com ttyd e entrypoint) é construída e marcada antes
  das 5 imagens de agente; cada imagem de agente parte dela.
- O encaminhamento de sessão passa a usar a porta definida pela entrada do
  catálogo da instância, em vez de uma porta fixa.

## Capabilities

### New Capabilities

- `coding-agent-images`: mantém um conjunto fixo de entradas de catálogo para
  agentes de código em CLI, cada uma acessível por um terminal web, mantidas
  em sincronia com o portal automaticamente.

### Modified Capabilities

- `image-catalog`: entrada do catálogo pode ser provisionada por build local
  de Docker em vez de apenas por download de registry; entrada passa a
  definir também a porta de encaminhamento do container.
- `session-proxy`: o encaminhamento passa a direcionar à porta definida pela
  entrada do catálogo da instância, em vez de uma porta fixa.

## Impact

- `backend/app/runtime/docker_runtime.py`: nova operação de build de imagem.
- `backend/app/runtime/protocol.py` / `backend/app/runtime/fake.py`: nova
  operação de build no protocolo de runtime e no fake usado em testes.
- `backend/app/services/images.py`: caminho de provisionamento por build,
  paralelo ao de pull existente.
- `backend/app/services/instances.py`: injeção da variável de ambiente `PORT`
  com a porta da imagem no container.
- `backend/app/services/agent_images.py` (novo): definições das 5 imagens,
  hash do contexto de build e seed idempotente que reconstrói só quando o
  contexto muda.
- `backend/app/db.py`: colunas de porta de encaminhamento, tipo de
  provisionamento (build ou pull) e hash do contexto de build em `images`.
- `backend/app/api/images.py`: retry escolhe build ou download conforme o
  tipo de provisionamento da entrada.
- `backend/app/api/session_proxy.py`: porta de destino lida da entrada do
  catálogo da instância em vez do literal fixo atual.
- `backend/app/main.py`: seed que constrói a base e as 5 imagens de agente
  (aguardando os builds) e as cadastra no catálogo antes de liberar o
  startup.
- `agent-images/` (novo diretório no repositório): Dockerfile base comum
  (ttyd) e um Dockerfile por agente.
- Sem mudança no frontend: as novas entradas aparecem no catálogo existente
  pelo mesmo fluxo que qualquer outra imagem já cadastrada. A liberação para
  usuários continua manual, via concessão por grupo.
