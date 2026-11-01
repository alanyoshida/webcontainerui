# Proposal

## Why

As imagens de agente de código rodam ferramentas que suportam MCP (Model
Context Protocol) para dar acesso a ferramentas externas, mas hoje não há
como o administrador disponibilizar um servidor MCP pronto dentro das
instâncias — cada usuário precisaria configurar manualmente, dentro de cada
sessão, repetindo credenciais e comandos. Falta uma biblioteca central de
servidores MCP, vinculável às imagens, no mesmo espírito do que já existe
para `AGENTS.md` e para skills.

## What Changes

- Nova biblioteca de servidores MCP no admin: cada entrada tem nome de
  exibição único, tipo de transporte (`stdio`, `http` ou `sse`), e conforme
  o tipo: comando + argumentos + variáveis de ambiente (stdio), ou URL +
  headers (http/sse). Valores de variáveis de ambiente e headers são
  criptografados em repouso (mesma infraestrutura Fernet já usada pela
  identidade SSH), por poderem carregar credenciais.
- Vínculo N:N entre servidores MCP e as 5 imagens de agente de código
  (`provision_kind = 'build'`): uma imagem pode ter N MCPs vinculados, um
  MCP pode estar vinculado a N imagens.
- Vincular, editar ou desvincular um MCP propaga **imediatamente** para as
  instâncias vivas das imagens afetadas, sem rebuild de imagem — MCP é só
  configuração, não precisa de instalação (diferente de skills). O portal
  escreve diretamente o arquivo de config nativo de cada ferramenta dentro
  do container (merge, não sobrescrita: esses arquivos guardam outro
  estado da ferramenta além de MCP). Nenhuma das 5 ferramentas é acionada
  via seu próprio comando `mcp add`: todas têm algum grau de validação de
  conexão ao vivo ou fluxo interativo que não se presta a automação (o do
  Hermes, por exemplo, tenta conectar de verdade e pede confirmação).
- Na criação de uma instância, os MCPs vinculados à imagem já são
  injetados de início, mesmo padrão do `AGENTS.md`.
- Remover um MCP da biblioteca é permitido mesmo vinculado a imagens: o
  sistema desvincula automaticamente de todas elas (mesma regra de
  `agent-skills`, não a do `AGENTS.md`).

Fora de escopo: imagens webtop (só as 5 de agente de código participam),
qualquer descoberta/catálogo de servidores MCP públicos (o cadastro é
sempre manual), e qualquer UI de teste de conexão do MCP dentro do portal
(o administrador confere funcionando dentro da sessão).

## Capabilities

### New Capabilities

- `mcp-servers`: mantém uma biblioteca de servidores MCP cadastrados pelo
  administrador, o vínculo N:N com imagens de agente de código, e a
  injeção desses servidores — traduzidos para o formato nativo de cada
  ferramenta — nas instâncias, na criação e sob demanda quando o vínculo
  muda.

### Modified Capabilities

Nenhuma. Mesmo padrão autocontido de `agent-skills` e `agents-md`: a
capability nova é dona de ponta a ponta do comportamento (biblioteca,
vínculo, tradução por ferramenta e injeção), sem fragmentar em
`coding-agent-images`.

## Impact

- Backend: `backend/app/db.py` (tabelas `mcp_servers` e `image_mcp_servers`,
  colunas de segredo cifrado), `backend/app/services/mcp_servers.py` (novo:
  CRUD da biblioteca, vínculo, um tradutor por ferramenta para o formato
  nativo), `backend/app/api/mcp_servers.py` (novo: rotas admin de CRUD e
  vínculo), `backend/app/services/instances.py` (injeção na criação, junto
  da identidade SSH e do `AGENTS.md`), `backend/app/runtime/protocol.py` /
  `docker_runtime.py` / `fake.py` (operação nova para ler um arquivo do
  container, necessária para o merge — ver design.md), `backend/app/main.py`
  (router novo).
- Frontend: `frontend/src/features/admin/McpServersPanel.jsx` (novo),
  `frontend/src/api/client.js` (chamadas novas), aba nova na página de
  admin.
