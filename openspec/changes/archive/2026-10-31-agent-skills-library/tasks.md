# Tasks

## 1. Esquema de dados

- [x] 1.1 Adicionar tabelas `agent_skills` (id, display_name UNIQUE, repo_owner, repo_name, subpath NULL, created_at, updated_at) e `image_skills` (image_id, skill_id, PK composta, FKs para `images`/`agent_skills`) em `backend/app/db.py`, com índice único em `(repo_owner, repo_name, subpath)`, seguindo o padrão idempotente já usado para `provision_kind`/`build_hash` — verificar rodando as migrações duas vezes seguidas sem erro (idempotência) e inspecionando o schema resultante
- [x] 1.2 Cobrir a migração com teste em `backend/tests/test_db.py` (tabelas existem, índice único aplicado, FK funcionando) — verificar com `pytest backend/tests/test_db.py`

## 2. Biblioteca de skills (serviço e API)

- [x] 2.1 Criar `backend/app/services/agent_skills.py` com CRUD da biblioteca (`create_skill`, `update_skill`, `delete_skill`, `list_skills`, `get_skill`), validando nome único e `(owner, repo, subpath)` único (`ConflictError`), no padrão de `agents_md.py` — verificar com testes unitários novos em `backend/tests/test_agent_skills.py`
- [x] 2.2 Implementar `delete_skill` removendo em cascata as linhas de `image_skills` da skill (sem recusar por vínculo ativo, ao contrário de `agents_md.delete_document`) e sem disparar rebuild — verificar com teste que remove skill vinculada a 2 imagens e confere que ambas ficam sem o vínculo
- [x] 2.3 Criar `backend/app/api/agent_skills.py` com rotas admin de CRUD (`GET/POST/PATCH/DELETE /admin/agent-skills`), restritas por `require_admin` como o restante do admin router — verificar com `backend/tests/test_agent_skills_api.py` cobrindo 403 para não-admin e CRUD feliz
- [x] 2.4 Registrar o router novo em `backend/app/main.py` — verificar que `GET /admin/agent-skills` responde 200 autenticado como admin

## 3. Vínculo N:N entre skill e imagem

- [x] 3.1 Implementar `set_image_skills`/`link_skill`/`unlink_skill` em `agent_skills.py`, recusando o vínculo quando `images.provision_kind != 'build'` (`ValidationFailedError`) — verificar com teste que tenta vincular skill a imagem `pull` e recebe recusa
- [x] 3.2 Adicionar rotas `POST/DELETE /admin/images/{image_id}/skills/{skill_id}` (ou equivalente) em `agent_skills.py`/`api` retornando o estado atualizado da imagem — verificar com teste de vínculo e desvínculo via API, incluindo o caso de imagem não encontrada
- [x] 3.3 Endpoint de listagem retorna, por imagem de agente, as skills vinculadas (para a tela de vínculo no admin) e, por skill, as imagens vinculadas (para o contador na biblioteca, como `linked_images` em `agents_md`) — verificar com teste checando os dois formatos de resposta

## 4. Build: protocolo de runtime aceita `buildargs`

- [x] 4.1 Adicionar parâmetro opcional `buildargs: dict[str, str] | None` a `ContainerRuntime.build_image` em `backend/app/runtime/protocol.py` — verificar que a assinatura é consistente entre protocolo e implementações
- [x] 4.2 Propagar `buildargs` em `backend/app/runtime/docker_runtime.py` para `aiodocker` `images.build(..., buildargs=buildargs)` — verificar com teste (ou verificação manual via `docker build --build-arg`) que o valor chega ao daemon
- [x] 4.3 Propagar/simular `buildargs` no dublê `backend/app/runtime/fake.py` usado pelos testes, registrando os args recebidos para inspeção em teste — verificar com teste que chama `build_image(..., buildargs={...})` no fake e confere o valor capturado

## 5. Build: resolver e aplicar as skills vinculadas

- [x] 5.1 Em `backend/app/services/agent_images.py` (ou `agent_skills.py`), adicionar função que resolve a lista ordenada de skills vinculadas a uma imagem (`owner/repo` ou `owner/repo:nome-da-skill` — `:` delimitando o valor de `--skill`, sintaxe real confirmada em design.md; join `image_skills`+`agent_skills`) e monta o dict de `ARG SKILLS` — verificar com teste unitário da função pura (sem Docker)
- [x] 5.2 Estender `context_hash`/`build_hash_for` para incluir essa lista resolvida, além do conteúdo em disco já coberto — verificar com teste que muda só o vínculo de skills (sem tocar arquivo) e confere que o hash resultante muda
- [x] 5.3 Atualizar `_provision_agent`/`run_build` para sempre calcular o `buildargs` a partir do estado atual do banco (não de um valor armazenado) e passá-lo para `runtime.build_image`, tanto no seed de startup quanto em qualquer chamada futura — verificar com teste que dispara dois builds seguidos com vínculos diferentes e confere que cada um recebeu os buildargs certos
- [x] 5.4 Adicionar `ARG SKILLS=""` e um `RUN` com loop best-effort em cada um dos 5 Dockerfiles de agente, cada um com seu próprio slug `--agent` fixo (`claude-code`→`claude-code`, `hermes`→`hermes-agent`, `agy`→`antigravity`, `opencode`→`opencode`, `oh-my-pi`→`pi` — slugs confirmados via `npx skills --help`/teste real) e `-y -g`; o loop faz split de cada item em `src`/`skill` pelo `:` e só passa `--skill "$skill"` quando presente (sintaxe completa em design.md) — verificar com `docker build --build-arg SKILLS="vercel-labs/agent-skills:vercel-optimize"` local e inspecionando que a skill apareceu em `/config` sem quebrar o build sem nenhum `SKILLS` definido

## 6. Gatilho de rebuild sob demanda

- [x] 6.1 Nas rotas de vínculo/desvínculo (tarefa 3.2), chamar `spawn(request.app, run_build(...))` com o `context_dir`/`build_hash` recalculados após o vínculo mudar, no mesmo padrão de `create_image_endpoint`/`retry_pull_endpoint` em `backend/app/api/images.py` — verificar que a resposta da rota retorna antes do build terminar e que `pull_state` passa a `pulling`/em progresso
- [x] 6.2 Teste de integração cobrindo o ciclo completo: vincular skill → imagem entra em build → build conclui → skill resolvida aparece no `buildargs` recebido pelo runtime fake — verificar com `backend/tests/test_agent_skills_build.py`

## 7. Falha isolada por skill

- [x] 7.1 Garantir (via o `|| true` da tarefa 5.4, e um teste de runtime fake que simula uma skill "falha") que uma skill com instalação simulada como falha não marca a imagem inteira como `failed` nem impede as demais skills — verificar com teste que injeta uma falha parcial no fake e confere que a imagem termina `ready`

## 8. Admin: painel de Skills no frontend

- [x] 8.1 Adicionar chamadas novas em `frontend/src/api/client.js` (listar/criar/editar/remover skills, listar vínculo por imagem, vincular/desvincular) — verificar com os testes de cliente existentes, se houver, ou checagem manual de contrato com a API
- [x] 8.2 Criar `frontend/src/features/admin/SkillsPanel.jsx` no padrão do `AgentsMdPanel.jsx`: tabela da biblioteca (nome, `owner/repo`, imagens vinculadas, ações) + tabela de vínculo por imagem com seleção múltipla (checkboxes) em vez do dropdown único — verificar com `frontend/src/features/admin/SkillsPanel.test.jsx` cobrindo criação, remoção e toggle de vínculo
- [x] 8.3 Adicionar a aba "Skills" na navegação do admin (onde `AgentsMdPanel` já está registrada) — verificar manualmente no navegador que a aba aparece e carrega a biblioteca

## 9. Verificação final

- [x] 9.1 Rodar a suíte completa de backend (`pytest`) e frontend (`npm test`) e confirmar que passam — verificar pela saída dos comandos
- [x] 9.2 Build manual de uma imagem de agente com uma skill real do skills.sh vinculada, confirmando que o conteúdo instalado aparece em `/config` dentro do container (`docker run --rm --entrypoint sh <imagem> -c 'ls -la /config'`) — verificar visualmente a presença dos arquivos da skill

## Workflow follow-up

- Arquivar a change depois que as tasks acima estiverem concluídas e revisadas.
- Atualizar `openspec/specs/agent-skills/spec.md` (criado no archive) se o comportamento real divergir do planejado durante a implementação.
