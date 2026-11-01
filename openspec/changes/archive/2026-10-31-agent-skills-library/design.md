# Design

## Context

Hoje o build das 5 imagens de agente é todo estático e disparado só pelo
startup do portal (`backend/app/services/agent_images.py`):
`seed_agent_images` calcula `context_hash` a partir só do conteúdo em disco
de `agent-images/_base/` e `agent-images/<agente>/`, e só chama `run_build`
quando esse hash muda em relação ao `build_hash` gravado na linha da imagem
(`images.build_hash`). Não existe hoje nenhum caminho que dispare um build a
partir de uma ação do admin em runtime — só `retry-pull`/`retry-build`
(`POST /images/{id}/retry-pull`), que repete o build do contexto atual sem
mudar nada nele.

`run_build` já delega para `runtime.build_image(context_dir, repository,
tag)`, que empacota `context_dir` num tar e chama `aiodocker`
`images.build(fileobj=..., tag=..., stream=True)`. O ajuste de `WORKDIR`
feito antes desta change (ver commit `28e4062`) já garante que o processo
de qualquer imagem de agente nasce em `/config` (`$HOME`) — é lá que as
skills instaladas no build precisam cair, no mesmo diretório onde o
`AGENTS.md` da capability `agents-md` é injetado em runtime.

Ver `proposal.md` para o porquê; este documento cobre só o como.

## Goals / Non-Goals

**Goals:**
- Skills vinculadas a uma imagem de agente ficam de fato instaladas dentro
  dela depois de um build, sem exigir mudança nos Dockerfiles por skill.
- Vincular/desvincular uma skill dispara rebuild imediato, reaproveitando a
  infraestrutura de build e de progresso que já existe (`run_build`,
  `pull_state`/`pull_progress`, `spawn`).
- O build siga determinístico em relação ao estado atual do banco: um
  rebuild disparado por qualquer caminho (startup ou ação do admin) sempre
  reflete o conjunto de skills vinculado naquele momento, nunca um estado
  antigo.

**Non-Goals:**
- Não cobre instalar/atualizar skills em instâncias já em execução (ver
  proposal.md — skills são parte da imagem, não do volume).
- Não cobre nenhuma forma de descobrir/buscar skills a partir do site
  skills.sh; o cadastro é sempre manual.
- Não cobre pin de commit/tag do repositório da skill.

## Decisions

### Esquema de dados

Duas tabelas novas, no mesmo padrão de `agent_md_documents` em `db.py`:

- `agent_skills(id, display_name UNIQUE, repo_owner, repo_name, subpath NULL,
  created_at, updated_at)`, com índice único em
  `(repo_owner, repo_name, subpath)` (NULLs tratados como string vazia nesse
  índice, já que SQLite considera cada NULL distinto por padrão).
- `image_skills(image_id, skill_id, PRIMARY KEY (image_id, skill_id))`, FK
  para `images.id` e `agent_skills.id`, join table pura — é a relação N:N
  que o vínculo único de `images.agents_md_id` não comporta.

Migração idempotente seguindo o padrão já usado em `db.py` (checar
`sqlite_master`/`PRAGMA table_info` antes de criar, como as migrações de
`provision_kind` e `build_hash` já fazem).

### Como a skill entra na imagem: build ARG, não contexto de arquivo

Alternativas consideradas:

1. **Gerar um diretório de contexto temporário por build**, com um
   manifesto das skills, copiado para dentro da imagem via `COPY`. Mais
   flexível, mas exige escrever arquivos temporários em disco por build e
   coordenar limpeza; também complica o cálculo de `context_hash`, que hoje
   assume que o contexto é só o que está versionado no repositório.
2. **Build ARG com a lista de skills** *(escolhido)*: cada Dockerfile de
   agente recebe um `ARG SKILLS=""` e um `RUN` que itera a lista
   (space-separated) chamando o CLI real do skills.sh por item. `run_build`
   passa `buildargs={"SKILLS": "<lista resolvida na hora>"}` para
   `runtime.build_image`. `aiodocker` já aceita `buildargs` nativamente
   (`images.build(..., buildargs=...)`), então o protocolo
   `ContainerRuntime.build_image` só precisa ganhar um parâmetro opcional
   novo, propagado também em `docker_runtime.py` e no dublê `fake.py` usado
   nos testes.

Ganha a opção 2 por não exigir estado em disco fora do repositório
versionado, por isolar a falha por skill com uma simples `|| true` no loop
do shell (igual a qualquer outro `RUN` best-effort), e por ser consistente
com o uso de `ARG` que a `_base/Dockerfile` já faz para `TTYD_VERSION` etc.

O `RUN` do loop de skills entra em cada Dockerfile de agente (não em
`_base/Dockerfile`): a imagem base é compartilhada e cacheada entre as 5
imagens, e skills são por imagem final, não por base.

#### Sintaxe real do CLI (corrigida após testar `npx skills --help` e builds reais)

A suposição inicial — `npx skills add owner/repo/caminho` — está errada. O
CLI real (`vercel-labs/skills`, pacote npm `skills`) não aceita caminho na
URL; a sintaxe testada e confirmada é:

```
npx --yes skills add <owner>/<repo> [--skill <nome>] --agent <slug> -y -g
```

- **`--skill <nome>`** seleciona uma skill específica dentro de um
  repositório que empacota várias (ex: `vercel-optimize` dentro de
  `vercel-labs/agent-skills`). Omitido, o CLI instala **todas** as skills
  do repositório (testado: não é interativo nem falha, só instala mais do
  que o admin pediu) — por isso o campo "subpath" do cadastro (ver
  proposal.md) é passado como valor dessa flag, nunca como parte da URL.
- **`--agent <slug>`** é obrigatório para não cair no comportamento padrão
  de tentar symlinkar para ~50 ferramentas conhecidas de uma vez (lento e
  sem sentido num container de uma ferramenta só). Testado e confirmado um
  slug por imagem — a lista completa de slugs válidos vem do próprio erro
  do CLI quando o slug é inválido:

  | Imagem        | slug `--agent` | destino confirmado          |
  |---------------|-----------------|------------------------------|
  | claude-code   | `claude-code`   | `~/.claude/skills/`          |
  | opencode      | `opencode`      | `~/.agents/skills/`          |
  | hermes        | `hermes-agent`  | `~/.hermes/skills/`          |
  | agy           | `antigravity`   | `~/.agents/skills/`          |
  | oh-my-pi      | `pi`            | `~/.pi/agent/skills/`        |

  O slug é fixo por Dockerfile (cada imagem só roda uma ferramenta), não
  vem do banco — só a lista de skills (`$SKILLS`) é dinâmica.
- **`-y`** evita qualquer prompt de confirmação; **`-g`** instala em
  escopo global (`$HOME`, que é `/config` nas nossas imagens — ver o ajuste
  de `WORKDIR` já aplicado antes desta change) em vez de escopo de projeto.
  Sem as duas, o build trava ou cancela silenciosamente num repositório com
  várias skills.

Como o item da lista `$SKILLS` precisa carregar `owner/repo` e,
opcionalmente, o nome da skill, o formato de cada item passado no
`buildargs` é `owner/repo` ou `owner/repo:nome-da-skill` (`:` como
delimitador interno — nunca aparece num `owner/repo` do GitHub, então é
seguro). O `RUN` de cada Dockerfile faz o split:

```sh
ARG SKILLS=""
RUN for s in $SKILLS; do \
      src="${s%%:*}"; skill="${s#*:}"; \
      if [ "$skill" = "$s" ]; then \
        npx --yes skills add "$src" --agent <slug-fixo-da-imagem> -y -g || true; \
      else \
        npx --yes skills add "$src" --skill "$skill" --agent <slug-fixo-da-imagem> -y -g || true; \
      fi; \
    done
```

`resolve_image_skill_refs` (em `agent_skills.py`) monta cada item nesse
formato a partir de `agent_skills.subpath` — o cadastro do admin não muda;
só a representação interna que chega ao `buildargs` é que usa `:` em vez de
`/` para separar o nome da skill.

### Gatilho de rebuild: sempre resolve as skills atuais do banco, nunca só o hash de arquivo

`_provision_agent` (chamado tanto pelo seed de startup quanto pelo novo
caminho sob demanda) passa a montar o `buildargs` lendo `image_skills` +
`agent_skills` no momento do build — não guarda a lista resolvida em lugar
nenhum. Isso evita a inconsistência de um rebuild disparado por mudança no
Dockerfile (startup) "esquecer" skills vinculadas que não entraram no
cálculo do hash de arquivo.

`context_hash` (renomeado nos pontos de uso para refletir que agora cobre
mais que arquivos, ou mantido e composto com um segundo hash — detalhe de
implementação) passa a incluir também a lista ordenada de
`(repo_owner, repo_name, subpath)` das skills vinculadas à imagem, para que
uma mudança só nas skills também conte como "contexto alterado" caso o
rebuild sob demanda falhe e só o próximo startup tente de novo.

O vínculo/desvínculo explícito (rota admin nova) dispara o rebuild
imediatamente via `spawn(request.app, run_build(...))`, o mesmo padrão já
usado por `create_image_endpoint`/`retry_pull_endpoint` — sem endpoint
síncrono esperando o build terminar.

### Remoção de skill da biblioteca

Remover uma `agent_skill` com vínculos ativos deleta as linhas
correspondentes de `image_skills` (ON DELETE CASCADE ou exclusão explícita
na mesma transação) e retorna normalmente — ao contrário de
`agents_md.delete_document`, que recusa com `ConflictError` enquanto houver
vínculo. Essa remoção não dispara rebuild: a imagem só reflete a ausência
da skill no próximo build disparado por outro motivo (vínculo de outra
skill na mesma imagem, mudança no Dockerfile, ou retry manual).

## Risks / Trade-offs

- **Build depende de rede para GitHub/npm a cada rebuild** (já é verdade
  hoje para `npm install -g opencode-ai`, `curl install.sh`, etc. nos
  Dockerfiles de agente) → mitigado só pelo isolamento de falha por skill;
  uma skill com repositório fora do ar não derruba as demais nem a
  ferramenta do agente.
- **Não determinístico**: `npx skills add owner/repo` sempre pega o estado
  atual do repositório (sem pin de commit/tag, por decisão explícita do
  escopo) → a mesma lista de skills pode produzir conteúdo diferente em
  builds em datas diferentes. Aceito como trade-off de simplicidade; fica
  registrado como não-objetivo na proposta.
- **Corrida entre dois vínculos quase simultâneos na mesma imagem**
  disparando dois `run_build` concorrentes → o último a terminar grava
  `build_hash`/estado; o build do meio pode ser sobrescrito. Mitigação:
  nenhuma nova nesta change — mesmo risco que já existe hoje entre
  `retry-pull` manual e um seed de startup concorrente, não introduzido por
  skills.
- **Convenção de pasta diferente por ferramenta** (`~/.claude/skills/` para
  Claude Code, `~/.agents/skills/` para OpenCode e Agy/antigravity,
  `~/.hermes/skills/` para Hermes, `~/.pi/agent/skills/` para oh-my-pi) →
  resolvido: cada Dockerfile já passa o `--agent` certo para sua própria
  ferramenta (ver tabela acima, confirmada testando as 5 imagens), então o
  CLI do skills.sh escolhe a pasta certa sozinho — nenhuma lógica nossa
  precisa conhecer essas pastas.

## Migration Plan

Mudança aditiva: duas tabelas novas, nenhuma coluna removida ou
redefinida. Segue o padrão de migração idempotente já usado para
`provision_kind`/`build_hash` em `db.py` — roda automaticamente na próxima
inicialização do portal, sem passo manual. Sem rollback especial: remover a
change reverte só o código; as tabelas novas ficam inofensivas e vazias se
não usadas.

## Open Questions

- Flags exatas do `npx skills add` para rodar não-interativo dentro do
  `RUN` (ex: aceitar prompts automaticamente) — depende de testar o CLI
  real durante a implementação; não muda specs, abordagem ou tasks.
