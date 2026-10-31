# Tasks

## 1. Runtime: capacidade de build de imagem

- [x] 1.1 Adicionar `build_image` ao protocolo `ContainerRuntime`
  (`backend/app/runtime/protocol.py`) e implementar em
  `FakeContainerRuntime` (`backend/app/runtime/fake.py`); verificar com
  teste unitário que o fake produz a sequência de `PullProgress`
  configurada e propaga falha corretamente.
- [x] 1.2 Implementar `build_image` em `AioDockerContainerRuntime`
  (`backend/app/runtime/docker_runtime.py`) sobre `aiodocker`
  (`images.build`, streaming de progresso); verificar com teste e2e
  (mesma marca dos testes e2e existentes) que builda um Dockerfile de
  fixture e confirma a imagem resultante existente no Docker local.

## 2. Catálogo: porta, tipo de provisionamento e rebuild

- [x] 2.1 Adicionar a `images` em `backend/app/db.py` as colunas `port`
  (padrão `3000`), `provision_kind` (padrão `'pull'`) e `build_hash`
  (nula), com migrações idempotentes no padrão de `_migrate_add_icon_path`;
  verificar com teste que as colunas existem após `init_db` e que uma
  entrada pré-existente recebe os valores padrão.
- [x] 2.2 Fazer `create_image` (`backend/app/services/images.py`) aceitar
  porta e tipo de provisionamento opcionais, com padrões `3000` e
  `'pull'`; verificar com teste unitário os caminhos informado e omitido.
- [x] 2.3 Expor `image_port` em `_INSTANCE_SELECT`
  (`backend/app/services/instances.py`); verificar com teste unitário que
  uma linha de instância carrega a porta da sua imagem.
- [x] 2.4 Fazer `default_backend_base_url`
  (`backend/app/api/session_proxy.py`) usar `row["image_port"]` em vez do
  literal `3000`; verificar com teste que duas instâncias de imagens com
  portas diferentes são encaminhadas cada uma à sua porta.
- [x] 2.5 Injetar `PORT` em `_build_spec` (`backend/app/services/instances.py`)
  com a porta da imagem; verificar com teste unitário que o `ContainerSpec`
  resultante leva `PORT` igual a `image_port` e continua sem campo próprio
  de porta.
- [x] 2.6 Unificar o retry por `provision_kind`: o caminho de retry lê o
  tipo da entrada e agenda `run_build` para `'build'` ou `run_pull` para
  `'pull'`; verificar com testes que entrada de build em falha dispara build
  e entrada de pull em falha dispara download.

## 3. Provisionamento por build

- [x] 3.1 Criar `backend/app/services/agent_images.py` com `run_build`
  paralela a `run_pull` (`image_pull.py`), usando `runtime.build_image` e os
  mesmos `mark_pull_progress` / `mark_pull_ready` / `mark_pull_failed`;
  verificar com teste unitário que sucesso marca a entrada como pronta e
  falha marca como falha com a mensagem de erro.
- [x] 3.2 Definir no mesmo módulo a lista estática das 5 imagens de agente
  (nome de exibição, repositório/tag locais, diretório de contexto de
  build, porta de encaminhamento) para Claude Code CLI, Hermes, Agy,
  OpenCode e oh-my-pi, mais a definição da imagem base comum; verificar com
  teste unitário que a lista contém exatamente esses 5 agentes e a base,
  com todos os campos obrigatórios.
- [x] 3.3 Calcular um hash do conteúdo do contexto de cada agente incluindo
  `agent-images/_base`, gravar em `images.build_hash` e fazer o seed
  inserir a linha só se repositório/tag não existirem e reconstruir somente
  quando o hash diferir do gravado; verificar com teste unitário que duas
  execuções sem mudança não duplicam nem rebuildam, e que alterar um
  arquivo do contexto dispara rebuild.
- [x] 3.4 Isolar falha por imagem no seed: a falha de build de uma entrada
  não impede as demais nem propaga exceção; verificar com teste unitário
  usando um runtime fake que falha o build de uma das 5 definições e
  confirma que as outras seguem sendo provisionadas.
- [x] 3.5 Construir e marcar a imagem base (`wcui-agent-base`) antes das 5
  imagens de agente; verificar com teste unitário usando um runtime fake que
  registra a ordem das chamadas de build.
- [x] 3.6 Ligar o seed ao `lifespan` em `backend/app/main.py`, depois da
  reconciliação e do backfill já existentes, aguardando base e agentes;
  verificar com teste de integração (`TestClient` como context manager, no
  padrão já usado para o backfill de execuções em `test_instance_runs.py`)
  que as 5 entradas aparecem prontas no catálogo após o startup e que uma
  falha isolada não impede o startup.

## 4. Imagens Docker dos agentes

- [x] 4.1 Criar `agent-images/_base/Dockerfile`: imagem base com `ttyd` e
  um script de entrypoint comum que lê `SUBFOLDER`/`CUSTOM_USER`/
  `PASSWORD`/`PORT` e executa
  `ttyd --writable --base-path "$SUBFOLDER" --credential "$CUSTOM_USER:$PASSWORD" -p "$PORT" <comando>`;
  verificar com `docker build` local bem-sucedido e `docker run` manual
  confirmando que o ttyd sobe, exige a credencial e aceita digitação.
- [x] 4.2 Criar `agent-images/claude-code/Dockerfile` (`FROM` a base,
  instala a CLI do Claude Code, define o comando); verificar com
  `docker build` e `docker run` manuais confirmando o terminal com a CLI
  disponível.
- [x] 4.3 Criar `agent-images/hermes/Dockerfile`, mesma verificação para o
  Hermes.
- [x] 4.4 Criar `agent-images/agy/Dockerfile`, mesma verificação para o
  Agy (Antigravity CLI).
- [x] 4.5 Criar `agent-images/opencode/Dockerfile`, mesma verificação
  para o OpenCode.
- [x] 4.6 Criar `agent-images/oh-my-pi/Dockerfile`, mesma verificação
  para o oh-my-pi.
- [x] 4.7 Copiar `agent-images/` para dentro da imagem do portal no
  `Dockerfile` raiz, para que o contexto de build exista em runtime
  quando o seed executar; verificar com `docker build` da imagem do
  portal e `docker run --rm <imagem-do-portal> ls agent-images`
  confirmando o diretório presente.

## 5. Verificação integrada

- [x] 5.1 Subir o stack de dev (`docker compose -f deploy/docker-compose.dev.yml up --build -d`)
  e confirmar no catálogo de admin que as 5 imagens de agente aparecem
  prontas após o startup, sem ação manual.
- [x] 5.2 Criar uma instância a partir de uma das imagens de agente, abrir
  a sessão e confirmar que o terminal carrega autenticado e executa a CLI
  do agente correspondente.
- [x] 5.3 Parar e excluir essa instância e confirmar que o comportamento
  observado (estados, preservação/remoção de volume) é idêntico ao de uma
  instância de imagem webtop comum.
- [x] 5.4 Provocar falha de build numa entrada de agente e acionar o
  retry, confirmando que um novo build é executado (e não um download).
- [x] 5.5 Reiniciar o portal sem alterar nenhum contexto e confirmar que
  as imagens não são reconstruídas.
- [x] 5.6 Rodar a suíte completa de testes (`pytest` no backend, `npm test`
  no frontend) e confirmar que nada regrediu.

## Workflow follow-up

- Arquivar a change após a revisão, sincronizando as specs
  (`image-catalog`, `session-proxy`) e criando a nova capability
  `coding-agent-images`.
