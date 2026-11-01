# Tasks

## 1. Esquema de dados

- [x] 1.1 Adicionar tabelas `mcp_servers` (id, display_name UNIQUE, transport, command, args_json, url, env_encrypted BLOB, headers_encrypted BLOB, enabled, created_at, updated_at) e `image_mcp_servers` (image_id, mcp_server_id, PK composta, FKs para `images`/`mcp_servers`) em `backend/app/db.py` — verificar rodando as migrações duas vezes seguidas sem erro e inspecionando o schema resultante
- [x] 1.2 Cobrir a migração com teste em `backend/tests/test_db.py` (tabelas existem, índice único de `display_name`, FK funcionando) — verificar com `pytest backend/tests/test_db.py`
- [x] 1.3 Adicionar `ruamel.yaml` como dependência em `backend/pyproject.toml` — verificar com `pip install -e backend` (ou equivalente do ambiente) sem erro

## 2. Criptografia dos segredos (env/headers)

- [x] 2.1 Em `backend/app/services/mcp_servers.py`, reaproveitar o padrão Fernet de `ssh_identity.py` (`Fernet(settings.ssh_key_encryption_key.encode())`) para cifrar/decifrar os dicionários `env`/`headers` antes de gravar/ler do banco — verificar com teste que cifra, grava, lê e decifra um dicionário de exemplo
- [x] 2.2 Garantir que a leitura pública do cadastro (listagem/detalhe) nunca devolve `env`/`headers` em claro (só indica que existem, ex: lista de chaves sem valor, ou omite) — verificar com teste que cadastra um segredo e confere que a resposta da leitura não contém o valor original

## 3. Biblioteca de MCP (serviço e API)

- [x] 3.1 Criar `backend/app/services/mcp_servers.py` com CRUD (`create_mcp_server`, `update_mcp_server`, `delete_mcp_server`, `list_mcp_servers`, `get_mcp_server`), validando nome único, `transport` coerente com os campos exigidos (`stdio` exige `command`; `http`/`sse` exige `url`) — verificar com testes unitários em `backend/tests/test_mcp_servers.py`
- [x] 3.2 Implementar `delete_mcp_server` removendo em cascata as linhas de `image_mcp_servers` do servidor (sem recusar por vínculo ativo) e disparando a propagação de remoção para as instâncias vivas das imagens afetadas (tarefa 8) — verificar com teste que remove um MCP vinculado a 2 imagens e confere que ambas ficam sem o vínculo
- [x] 3.3 Criar `backend/app/api/mcp_servers.py` com rotas admin de CRUD (`GET/POST/PATCH/DELETE /admin/mcp-servers`), restritas por `require_admin` — verificar com `backend/tests/test_mcp_servers_api.py` cobrindo 403 para não-admin e CRUD feliz
- [x] 3.4 Registrar o router novo em `backend/app/main.py` — verificar que `GET /admin/mcp-servers` responde 200 autenticado como admin

## 4. Vínculo N:N entre MCP e imagem

- [x] 4.1 Implementar `link_mcp_server`/`unlink_mcp_server` em `mcp_servers.py`, recusando o vínculo quando `images.provision_kind != 'build'` (`ValidationFailedError`) — verificar com teste que tenta vincular MCP a imagem `pull` e recebe recusa
- [x] 4.2 Adicionar rotas `POST/DELETE /admin/mcp-servers/images/{image_id}/servers/{mcp_server_id}` retornando o estado atualizado da imagem, disparando a propagação (tarefa 8) — verificar com teste de vínculo e desvínculo via API
- [x] 4.3 Endpoint de listagem retorna, por imagem de agente, os MCPs vinculados, e por MCP, as imagens vinculadas (contador, como `linked_images` em `agents_md`/`agent_skills`) — verificar com teste checando os dois formatos de resposta

## 5. Runtime: ler um arquivo do container (`get_archive`)

- [x] 5.1 Adicionar `get_archive(container_id, path) -> bytes | None` a `ContainerRuntime` em `backend/app/runtime/protocol.py` (retorna `None` quando o arquivo não existe) — verificar que a assinatura é consistente entre protocolo e implementações
- [x] 5.2 Implementar em `backend/app/runtime/docker_runtime.py` usando `container.get_archive()` do `aiodocker`, tratando `DockerError` de "not found" como retorno `None` — verificar com teste manual contra um container real lendo um arquivo existente e um inexistente
- [x] 5.3 Implementar no dublê `backend/app/runtime/fake.py`: um dicionário interno `_files` por `container_id` populado por `put_archive` (desempacotando o tar) e lido por `get_archive` (reempacotando), para os testes simularem round-trip sem Docker — verificar com teste que escreve via `put_archive` e lê de volta via `get_archive` no fake

## 6. Tradutores por ferramenta e merge JSON/YAML

- [x] 6.1 Implementar o merge genérico de JSON em `mcp_servers.py`: ler o arquivo via `get_archive` (ou partir de `{}` se não existir), substituir só a chave de MCP pelo objeto traduzido, reserializar preservando as demais chaves — verificar com teste que injeta num arquivo JSON com outras chaves pré-existentes e confere que elas sobrevivem
- [x] 6.2 Implementar o merge equivalente em YAML com `ruamel.yaml` (preserva comentários), usado só pelo Hermes — verificar com teste que injeta num YAML com comentários e chaves pré-existentes (`_config_version`) e confere que sobrevivem
- [x] 6.3 Implementar os 5 tradutores (claude-code, opencode, agy, hermes, oh-my-pi) conforme a tabela de design.md — cada um recebe a lista de MCPs resolvidos da imagem e devolve o caminho do arquivo + o objeto a mesclar na chave certa. Hermes também monta o conteúdo do `.hermes/.env` (`MCP_<NOME>_API_KEY=<valor>`) e referencia `${...}` no YAML em vez do valor cru — verificar com um teste por ferramenta, comparando a saída exata com a tabela confirmada em design.md
- [x] 6.4 Isolar falha por MCP dentro de um tradutor (ex: um campo inesperado de um MCP não derruba a tradução dos demais vinculados à mesma imagem) — verificar com teste que injeta um MCP malformado misturado com MCPs válidos e confere que só o malformado fica de fora

## 7. Validação de schema pós-injeção

- [x] 7.1 Adicionar `jsonschema` como dependência em `backend/pyproject.toml` — verificar com instalação sem erro
- [x] 7.2 Definir os 5 JSON Schemas (um por ferramenta, validando só a chave de MCP) como constantes no módulo dos tradutores, conforme os exemplos de design.md (nomes de campo exatos por ferramenta: `serverUrl` na Agy, `transport` no oh-my-pi, etc.) — verificar com teste que valida um payload correto e um incorreto por ferramenta, usando os schemas diretamente
- [x] 7.3 Implementar `validate_tool_config(payload, schema) -> list[str]` que roda `jsonschema` e devolve mensagens legíveis mapeando o path do erro de volta pro nome do servidor MCP e o campo (ex: `"MCP 'minha-skill': campo 'command' obrigatório ausente"`) — verificar com teste que confere o texto exato da mensagem para alguns casos de erro
- [x] 7.4 Depois de cada escrita (propagação — tarefa 8 — e injeção na criação — tarefa 9), ler o arquivo de volta via `get_archive` e rodar a validação; o conteúdo já escrito não é desfeito mesmo se a validação falhar (ver design.md) — verificar com teste que escreve um payload inválido via o fake e confere que a validação pós-escrita detecta e reporta, sem lançar exceção que interrompa o restante da propagação

## 8. Propagação para instâncias vivas

- [x] 8.1 Implementar `propagate_mcp_servers_to_live_instances` em `mcp_servers.py`, no padrão de `propagate_document_to_live_instances`/`propagate_ssh_identity_to_live_instances`: para cada instância viva da imagem afetada, roda o merge (tarefa 6), grava via `put_archive` e valida o resultado (tarefa 7.4), isolando falha de propagação e falha de validação por instância — verificar com teste que propaga pra 2 instâncias vivas, uma delas falhando ao propagar e outra com erro de validação, e confere que a terceira (hipotética, válida) recebe a atualização normalmente
- [x] 8.2 Ligar essa propagação às rotas de vínculo/desvínculo/edição (tarefas 3.2, 4.2), devolvendo tanto `propagation_failures` (erro de runtime) quanto `schema_validation_errors` (quebra de contrato, com a mensagem por campo da tarefa 7.3) na resposta — verificar com teste de API que vincula um MCP com campo inválido numa imagem com instância viva e confere que a resposta relata a quebra, nomeando o campo

## 9. Injeção na criação da instância

- [x] 9.1 Adicionar `_inject_mcp_servers` em `backend/app/services/instances.py`, chamada em `_provision_instance` junto de `_inject_ssh_identity`/`_inject_agents_md`: resolve os MCPs vinculados à imagem, escreve via o mesmo merge da tarefa 6 e valida o resultado (tarefa 7.4), registrando o erro de validação (se houver) em algum lugar consultável pelo admin (ex: coluna de erro na instância, reaproveitando o padrão de `error_message`) — verificar com teste que cria uma instância de imagem com MCPs vinculados, um deles com campo inválido, e confere o conteúdo final do arquivo e o erro registrado via runtime fake
- [x] 9.2 Falha ao injetar ou validar um MCP na criação não impede a instância de ficar pronta (mesmo padrão de `_inject_agents_md`) — verificar com teste que simula falha no fake e confere que a instância termina `running`/pronta mesmo assim

## 10. Admin: painel de MCP no frontend

- [x] 10.1 Adicionar chamadas novas em `frontend/src/api/client.js` (listar/criar/editar/remover MCPs, listar vínculo por imagem, vincular/desvincular) — verificar manualmente o contrato com a API
- [x] 10.2 Criar `frontend/src/features/admin/McpServersPanel.jsx` no padrão de `SkillsPanel.jsx`: biblioteca (CRUD, com campos condicionais por `transport`) + vínculo por imagem com checkboxes — verificar com `frontend/src/features/admin/McpServersPanel.test.jsx` cobrindo criação (stdio e remoto), remoção e toggle de vínculo
- [x] 10.3 Mostrar, na resposta de vincular/editar/desvincular, um alerta quando `schema_validation_errors` vier preenchido, nomeando o MCP e o campo a corrigir (mesmo padrão de alerta de `propagation_failures` já usado no `AgentsMdPanel`) — verificar com teste que mocka uma resposta com erro de validação e confere o texto do alerta
- [x] 10.4 Adicionar a aba "MCP" na navegação do admin (`frontend/src/pages/AdminPage.jsx`) — verificar manualmente no navegador que a aba aparece e carrega a biblioteca

## 11. Verificação final

- [x] 11.1 Rodar a suíte completa de backend (`pytest`) e frontend (`npm test`) e confirmar que passam
- [ ] 11.2 Teste manual de ponta a ponta contra pelo menos 2 das 5 imagens reais (ex: claude-code e oh-my-pi, as duas pontas da tabela de confiança): cadastrar um MCP real, vincular, abrir uma sessão na instância e confirmar que a ferramenta lista o servidor — verificar visualmente dentro da sessão
- [x] 11.3 Teste manual forçando uma quebra de contrato (ex: cadastro com campo que o tradutor não preenche direito) numa das imagens reais e confirmar que o admin vê o alerta com o campo certo na tela

## Workflow follow-up

- Arquivar a change depois que as tasks acima estiverem concluídas e revisadas.
- Atualizar `openspec/specs/mcp-servers/spec.md` (criado no archive) se o comportamento real divergir do planejado durante a implementação.
