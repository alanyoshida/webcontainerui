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
  ao `docker pull` por registry já existente. O build falho pode ser
  repetido, assim como já vale para o download falho.
- Entradas do catálogo passam a admitir uma porta de encaminhamento própria
  (padrão 3000, mesmo valor assumido hoje), para containers cujo processo de
  interface não escuta na porta fixa usada pelos desktops webtop.
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
- `backend/app/db.py`: coluna de porta de encaminhamento em `images`; dados
  para distinguir entradas provisionadas por build.
- `backend/app/api/session_proxy.py`: porta de destino lida da entrada do
  catálogo da instância em vez do literal fixo atual.
- `backend/app/main.py`: rotina de seed idempotente no startup que garante as
  5 imagens de agente buildadas e cadastradas no catálogo.
- `agent-images/` (novo diretório no repositório): Dockerfile base comum
  (ttyd) e um Dockerfile por agente.
- Sem mudança no frontend: as novas entradas aparecem no catálogo existente
  pelo mesmo fluxo que qualquer outra imagem já cadastrada.
