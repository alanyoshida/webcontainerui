# Tasks

## 1. Banco e modelo de documentos

- [x] 1.1 Adicionar a tabela `agent_md_documents` (id, name UNIQUE, content,
  created_at, updated_at) e a coluna nullable `agents_md_id` em `images` em
  `backend/app/db.py`, com migração idempotente no padrão de
  `_migrate_add_icon_path`; verificar com teste que `init_db` cria tudo e que
  rodar de novo não falha nem duplica.
- [x] 1.2 Implementar as funções de biblioteca em
  `backend/app/services/agents_md.py` (criar, editar, listar com contagem de
  imagens vinculadas, remover com recusa por vínculo ativo, resolver
  documento por imagem); verificar com testes unitários nome único, conteúdo
  vazio/excedente, remoção recusada com vínculo e remoção permitida sem
  vínculo.

## 2. Runtime: operação de execução

- [x] 2.1 Adicionar `exec(container_id, command) -> (exit_code, output)` ao
  protocolo `backend/app/runtime/protocol.py`, implementar em
  `AioDockerContainerRuntime` (`docker exec`) e em `FakeContainerRuntime`
  (registra as chamadas e opcionalmente falha); verificar com testes
  unitários no padrão de `test_runtime.py`.
- [x] 2.2 Escrever o teste e2e marcado (Docker real) criando um container de
  `agent-images/_base`, gravando e removendo `/config/AGENTS.md` via `exec`,
  e conferindo código de saída e ausência do arquivo.

## 3. Injeção na criação da instância

- [x] 3.1 Estender a montagem de tar em `ssh_identity.py` (ou módulo
  equivalente) para produzir o membro `AGENTS.md` com 0644 e dono
  uid/gid por tipo de imagem; verificar com teste que o tar tem o membro
  com nome, conteúdo, modo e dono corretos.
- [x] 3.2 Injetar o documento em `_inject_ssh_identity`/criação de instância
  quando `images.agents_md_id` está preenchido; verificar com testes que a
  instância com imagem vinculada recebe `/config/AGENTS.md`, que sem
  vínculo nada é gravado e que falha da injeção não impede a instância de
  ficar pronta.
- [x] 3.3 Verificar no e2e (Docker real) que a instância criada de imagem com
  documento tem o arquivo presente com o dono e permissões corretos
  (root para agente, PUID/PGID para webtop).

## 4. Propagação e remoção em instâncias vivas

- [x] 4.1 Implementar a propagação ao salvar conteúdo: imagens vinculadas ao
  documento → instâncias `running` com container → `put_archive` do novo
  conteúdo, isolando falha por instância e devolvendo as falhas; verificar
  com testes usando o runtime fake.
- [x] 4.2 Implementar a propagação ao vincular (novo documento nas vivas da
  imagem) e a remoção ao desvincular (`exec rm` nas vivas), com o mesmo
  isolamento; verificar com testes que instâncias paradas não recebem
  propagação nem remoção via exec, e que falhas individuais não derrubam o
  restante.

## 5. API e painel admin

- [x] 5.1 Criar as rotas em `backend/app/api/agents_md.py` (listar, criar,
  editar, remover, listar vínculos, definir vínculo) sob `/api/admin`,
  todas exigindo admin, com a resposta de salvar/vincular reportando as
  falhas de propagação; registrar o router em `main.py` e verificar com
  testes de API os códigos de status e permissões.
- [x] 5.2 Adicionar as chamadas em `frontend/src/api/client.js` e a nova aba
  em `frontend/src/features/admin/AgentsMdPanel.jsx` (lista de documentos
  com dialog de edição textarea, e por imagem um Select com valor vazio =
  nenhum); registrar a aba em `AdminPage.jsx`.
- [x] 5.3 Escrever os testes do painel (vitest + testing-library) no padrão
  dos painéis existentes: criação, edição, vinculo por imagem, resposta de
  erro e estado vazio.

## 6. Documentação e verificação final

- [x] 6.1 Atualizar `AGENTS.md` e `README.md` se o comportamento do startup
  ou das operações mudar para administradores; verificar que os comandos
  documentados rodam como escritos.
- [x] 6.2 Rodar a suíte completa do backend (`pytest`) e do frontend
  (`npm test`) e confirmar que tudo passa.
- [x] 6.3 Subir o stack de dev, criar um documento, vincular a uma imagem,
  iniciar uma instância e confirmar que `/config/AGENTS.md` existe com o
  conteúdo salvo; editar o documento e confirmar a propagação na instância
  viva; desvincular e confirmar a remoção do arquivo.

## Workflow follow-up

- Arquivar a change após a revisão, sincronizando o delta em `agents-md`.
- Verificar o resultado arquivado.