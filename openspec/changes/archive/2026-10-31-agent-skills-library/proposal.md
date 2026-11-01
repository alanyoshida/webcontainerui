# Proposal

## Why

As imagens de agente de código (Claude Code, Hermes, Agy, OpenCode, oh-my-pi)
hoje só trazem a CLI instalada. Para essas ferramentas usarem "skills"
(conhecimento procedural reutilizável, no formato distribuído pelo diretório
skills.sh) falta uma forma do administrador cadastrar quais skills existem e
anexá-las a cada imagem, sem depender do usuário instalar manualmente dentro
de cada instância, sessão após sessão.

## What Changes

- Nova biblioteca de skills no admin: cada entrada tem nome de exibição
  único, repositório do GitHub (`owner/repo`) e um caminho opcional dentro
  dele (quando o repositório empacota várias skills), com o par
  repositório+caminho também único na biblioteca.
- Vínculo N:N entre skills e as 5 imagens de agente de código
  (`provision_kind = 'build'`): uma imagem pode ter N skills vinculadas, uma
  skill pode estar vinculada a N imagens. Imagens webtop (`provision_kind =
  'pull'`) não participam — ficam fora de escopo.
- Vincular ou desvincular uma skill numa imagem dispara o rebuild imediato
  dessa imagem em background, com o mesmo progresso consultável de qualquer
  build hoje.
- O build instala cada skill vinculada dentro da imagem com o CLI do
  skills.sh (`npx skills add <owner>/<repo>`, com `--skill <nome>` quando o
  cadastro tem um caminho dentro do repositório — ver design.md para a
  sintaxe exata, confirmada testando as 5 ferramentas). Falha ao instalar
  uma skill é isolada: a imagem termina de buildar com as demais skills e a
  ferramenta do agente, só sem a que falhou.
- Remover uma skill da biblioteca é permitido mesmo vinculada a imagens: o
  sistema desvincula automaticamente de todas elas. Essa remoção, por si só,
  não dispara rebuild — só o vincular/desvincular explícito dispara.
- Instâncias já em execução continuam na imagem com que foram criadas até
  serem paradas e reiniciadas: skills são parte da imagem, não são injetadas
  no volume da instância como o `AGENTS.md` é hoje.
- Novo painel administrativo "Skills", no mesmo padrão do painel de
  documentos `AGENTS.md`: uma tabela com a biblioteca (CRUD) e uma tabela de
  vínculo por imagem — aqui com seleção múltipla por imagem, já que a
  relação é N:N em vez do vínculo único do `AGENTS.md`.

Fora de escopo: skills em imagens webtop, qualquer integração com API do
skills.sh para buscar ou listar skills (o cadastro é sempre manual, digitando
`owner/repo`), fixar a skill numa versão/commit específico do repositório
(o build sempre instala o que `npx skills add` resolver na hora), e propagar
skills para instâncias já vivas.

## Capabilities

### New Capabilities

- `agent-skills`: mantém uma biblioteca de skills cadastradas pelo
  administrador, o vínculo N:N entre skills e imagens de agente de código, e
  a instalação das skills vinculadas no build de cada imagem, disparando
  rebuild imediato quando o vínculo muda.

### Modified Capabilities

Nenhuma. Como em `agents-md` e `instance-ssh-keys`, a capability nova é dona
de ponta a ponta do comportamento (biblioteca, vínculo e efeito no build),
sem fragmentar em `coding-agent-images` ou `image-catalog`.

## Impact

- Backend: `backend/app/db.py` (tabelas `agent_skills` e `image_skills`),
  `backend/app/services/agent_skills.py` (novo: CRUD da biblioteca, vínculo,
  geração do passo de build por skill), `backend/app/api/agent_skills.py`
  (novo: rotas admin de CRUD e vínculo), `backend/app/services/agent_images.py`
  (hash de build passa a incluir as skills vinculadas; novo gatilho de
  rebuild sob demanda, fora do seed de startup), `backend/app/main.py`
  (router novo).
- Frontend: `frontend/src/features/admin/SkillsPanel.jsx` (novo),
  `frontend/src/api/client.js` (chamadas novas), aba nova na página de admin.
