# Proposal

## Why

Cada imagem de agente de código expõe um terminal onde o usuário roda CLIs de
IA dentro do container. Para essas ferramentas produzirem código consistente
com as convenções do projeto sendo editado, falta uma forma de o administrador
publicar um texto `AGENTS.md` que apareça dentro do container — hoje o
arquivo precisa ser criado manualmente pelo usuário, sessão após sessão. Um
texto só de um projeto, ou padrão da equipe, precisaria ser copiado à mão em
cada instância de cada imagem.

## What Changes

- Novo painel administrativo de documentos `AGENTS.md`: uma biblioteca de
  textos nomeados, com criação, edição e remoção restritas a administradores.
- Cada entrada do catálogo de imagens (agente ou webtop) passa a poder ser
  vinculada a **um** texto da biblioteca, ou a nenhum.
- Na criação ou reinício de uma instância, o portal injeta o texto vinculado à
  sua imagem como `/config/AGENTS.md` (o `HOME` dos dois tipos de imagem),
  com dono e permissões adequados, pelo mesmo mecanismo de `put_archive`
  usado pela identidade SSH.
- Quando o administrador salva um texto ou altera o vínculo de uma imagem, o
  portal reescreve o arquivo em todas as instâncias vivas das imagens
  afetadas — mesmo comportamento da regeneração de chave SSH: best-effort
  por instância, falha isolada, sem derrubar as demais.
- Quando o administrador desvincula um texto de uma imagem, o arquivo
  `AGENTS.md` é removido de fato das instâncias vivas dela, via nova operação
  de execução de comando no runtime (remove no padrão de
  `stop_container`/`put_archive`).

Fora de escopo: edição por usuário comum (a biblioteca é exclusiva do
administrador), múltiplos documentos combinados por imagem (um vínculo por
entrada), documentos com outros nomes de arquivo e validação do conteúdo
Markdown além de limites de tamanho.

## Capabilities

### New Capabilities

- `agents-md`: mantém uma biblioteca de documentos `AGENTS.md` administrável,
  permite vincular cada entrada do catálogo a um deles e injeta o documento
  nas instâncias na criação, no reinício e sob demanda do administrador.

### Modified Capabilities

Nenhuma. A vinculação por imagem e a injeção no ciclo de vida da instância
seguem integralmente dentro da capability nova, no mesmo padrão da change
`instance-ssh-keys` (uma capability dona do comportamento de ponta a ponta,
sem fragmentar em `image-catalog`/`desktop-instances`).

## Impact

- Backend: `backend/app/db.py` (tabela de documentos + coluna de vínculo em
  `images`, migração idempotente), `backend/app/services/agents_md.py` (novo
  serviço de biblioteca e injeção), `backend/app/api/agents_md.py` (rotas
  admin de CRUD e vínculo), `backend/app/services/instances.py` (injeção na
  criação, junto da identidade SSH), `backend/app/runtime/protocol.py`,
  `docker_runtime.py` e `fake.py` (operação de remoção de arquivo em
  container vivo), `backend/app/main.py` (router novo).
- Frontend: nova aba em `frontend/src/features/admin/` com a biblioteca e o
  vínculo por imagem, `frontend/src/api/client.js` com as chamadas novas.
- Banco: `agent_md_documents` (id, nome, conteúdo, timestamps) e coluna
  `agents_md_id` nullable em `images`.
- Testes: CRUD e permissões da biblioteca, vínculo por imagem, injeção na
  criação, propagação ao salvar, remoção ao desvincular, isolamento de
  falhas, e e2e com Docker real para a operação de remoção.