# Tasks

## 1. Runtime: capacidade de build de imagem

- [ ] 1.1 Adicionar `build_image` ao protocolo `ContainerRuntime`
  (`backend/app/runtime/protocol.py`) e implementar em
  `FakeContainerRuntime` (`backend/app/runtime/fake.py`); verificar com
  teste unitário que o fake produz a sequência de `PullProgress`
  configurada e propaga falha corretamente.
- [ ] 1.2 Implementar `build_image` em `AioDockerContainerRuntime`
  (`backend/app/runtime/docker_runtime.py`) sobre `aiodocker`
  (`images.build`, streaming de progresso); verificar com teste e2e
  (mesma marca dos testes e2e existentes) que builda um Dockerfile de
  fixture e confirma a imagem resultante existente no Docker local.

## 2. Catálogo: porta de encaminhamento por imagem

- [ ] 2.1 Adicionar coluna `port` a `images` em `backend/app/db.py`
  (schema + migração idempotente para bancos existentes, no padrão de
  `_migrate_add_icon_path`); verificar com teste que a coluna existe após
  `init_db` e que uma entrada pré-existente recebe o valor padrão.
- [ ] 2.2 Fazer `create_image` (`backend/app/services/images.py`) aceitar
  porta opcional, com padrão `3000` quando omitida; verificar com teste
  unitário os dois caminhos (porta informada e omitida).
- [ ] 2.3 Expor `image_port` em `_INSTANCE_SELECT`
  (`backend/app/services/instances.py`); verificar com teste unitário que
  uma linha de instância carrega a porta da sua imagem.
- [ ] 2.4 Fazer `default_backend_base_url`
  (`backend/app/api/session_proxy.py`) usar `row["image_port"]` em vez do
  literal `3000`; verificar com teste que duas instâncias de imagens com
  portas diferentes são encaminhadas cada uma à sua porta.

## 3. Provisionamento por build (generaliza o estado pulling/ready/failed)

- [ ] 3.1 Criar `backend/app/services/agent_images.py` com uma função de
  build paralela a `run_pull` (`image_pull.py`), usando
  `runtime.build_image` e os mesmos `mark_pull_progress` /
  `mark_pull_ready` / `mark_pull_failed`; verificar com teste unitário que
  sucesso marca a entrada como pronta e falha marca como falha com a
  mensagem de erro.
- [ ] 3.2 Definir no mesmo módulo a lista estática das 5 imagens de
  agente (nome de exibição, repositório/tag locais, diretório de contexto
  de build, porta de encaminhamento) para Claude Code CLI, Hermes, Agy,
  OpenCode e oh-my-pi; verificar com teste unitário que a lista contém
  exatamente esses 5 agentes com todos os campos obrigatórios.
- [ ] 3.3 Implementar o seed idempotente: para cada definição, inserir a
  linha em `images` somente se repositório/tag ainda não existirem, e
  disparar o build; verificar com teste unitário que chamar o seed duas
  vezes não duplica entradas.
- [ ] 3.4 Isolar falha por imagem no seed: a falha de build de uma
  entrada não impede as demais nem propaga exceção; verificar com teste
  unitário usando um runtime fake que falha o build de uma das 5
  definições e confirma que as outras seguem sendo provisionadas.
- [ ] 3.5 Ligar o seed ao `lifespan` em `backend/app/main.py`, depois da
  reconciliação e do backfill já existentes; verificar com teste de
  integração (`TestClient` como context manager, no padrão já usado para
  o backfill de execuções em `test_instance_runs.py`) que as 5 entradas
  aparecem no catálogo após o startup.

## 4. Imagens Docker dos agentes

- [ ] 4.1 Criar `agent-images/_base/Dockerfile`: imagem base com `ttyd` e
  um script de entrypoint comum que lê `SUBFOLDER`/`CUSTOM_USER`/`PASSWORD`
  e executa `ttyd --base-path "$SUBFOLDER" --credential "$CUSTOM_USER:$PASSWORD" -p <porta> <comando>`;
  verificar com `docker build` local bem-sucedido e `docker run` manual
  confirmando que o ttyd sobe e exige a credencial.
- [ ] 4.2 Criar `agent-images/claude-code/Dockerfile` (`FROM` a base,
  instala a CLI do Claude Code, define o comando); verificar com
  `docker build` e `docker run` manuais confirmando o terminal com a CLI
  disponível.
- [ ] 4.3 Criar `agent-images/hermes/Dockerfile`, mesma verificação para o
  Hermes.
- [ ] 4.4 Criar `agent-images/agy/Dockerfile`, mesma verificação para o
  Agy (Antigravity CLI).
- [ ] 4.5 Criar `agent-images/opencode/Dockerfile`, mesma verificação
  para o OpenCode.
- [ ] 4.6 Criar `agent-images/oh-my-pi/Dockerfile`, mesma verificação
  para o oh-my-pi.
- [ ] 4.7 Copiar `agent-images/` para dentro da imagem do portal no
  `Dockerfile` raiz, para que o contexto de build exista em runtime
  quando o seed executar; verificar com `docker build` da imagem do
  portal e `docker run --rm <imagem-do-portal> ls agent-images`
  confirmando o diretório presente.

## 5. Verificação integrada

- [ ] 5.1 Subir o stack de dev (`docker compose -f deploy/docker-compose.dev.yml up --build -d`)
  e confirmar no catálogo de admin que as 5 imagens de agente aparecem
  prontas após o startup, sem ação manual.
- [ ] 5.2 Criar uma instância a partir de uma das imagens de agente, abrir
  a sessão e confirmar que o terminal carrega autenticado e executa a CLI
  do agente correspondente.
- [ ] 5.3 Parar e excluir essa instância e confirmar que o comportamento
  observado (estados, preservação/remoção de volume) é idêntico ao de uma
  instância de imagem webtop comum.
- [ ] 5.4 Rodar a suíte completa de testes (`pytest` no backend, `npm test`
  no frontend) e confirmar que nada regrediu.

## Workflow follow-up

- Arquivar a change após a revisão, sincronizando as specs
  (`image-catalog`, `session-proxy`) e criando a nova capability
  `coding-agent-images`.
