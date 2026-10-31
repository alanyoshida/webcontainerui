# Design

## Context

Ver `proposal.md` para a motivação e o delta em `specs/agents-md/spec.md`
para o contrato. Estado atual relevante:

- A identidade SSH já é injetada em toda instância criada via
  `runtime.put_archive(container_id, "/config", tar_bytes)`
  (`backend/app/services/instances.py`, `_inject_ssh_identity`), com tar
  montado por `build_ssh_archive` (`backend/app/services/ssh_identity.py`)
  — dono e permissões por membro, root para imagens de agente
  (`provision_kind = "build"`) e PUID/PGID para webtop (`_ssh_owner_uid_gid`).
  `/config` é o `HOME` dos dois tipos de imagem (fixado no
  `agent-images/_base/Dockerfile`; o webtop LinuxServer já nasce assim).
- A regeneração de chave SSH propaga para instâncias vivas em
  `propagate_ssh_identity_to_live_instances`: percorre instâncias com
  container criado (vivas ou paradas), best-effort por instância, devolve
  falhas para o chamador reportar — o padrão exato que a edição de
  documento deve seguir.
- O painel admin já é organizado em abas (`frontend/src/pages/AdminPage.jsx`),
  com um componente por funcionalidade em `frontend/src/features/admin/`.
- Migrações são idempotentes em `init_db` (`backend/app/db.py`):
  `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` guardado por
  `PRAGMA table_info`.
- O protocolo `ContainerRuntime` (`backend/app/runtime/protocol.py`) hoje não
  tem operação de executar comando nem de remover arquivo em container vivo.

## Goals / Non-Goals

**Goals:**

- Biblioteca de documentos nomeados com vínculo 0..1 por entrada do catálogo.
- Injeção do documento como `/config/AGENTS.md` na criação/reinício da
  instância, junto da identidade SSH, com dono correto por tipo de imagem.
- Propagação ao salvar (editar conteúdo ou vínculo) para instâncias vivas,
  com isolamento de falha por instância e resultado reportado ao admin.
- Remoção real do arquivo ao desvincular, via nova operação de runtime.
- Falha de injeção/remoção nunca impede a instância nem o restante da
  operação (best-effort, como a identidade SSH).

**Non-Goals:**

- Editor Markdown com preview — textarea simples, como o restante do painel.
- Múltiplos documentos combinados por imagem (stack de documentos).
- Outros nomes de arquivo além de `AGENTS.md`.
- Documentos por usuário — a biblioteca é global, do administrador.
- Versionamento/histórico de documento.

## Decisions

### D1: Biblioteca em tabela própria, vínculo como coluna nullable em `images`

```text
agent_md_documents          images
+---------------+          +----------------+
| id            |          | id             |
| name     UNIQUE|  0..1   | agents_md_id ---+--> agent_md_documents.id
| content       |<---------+ (nullable)     |
| created_at    |          | ...             |
| updated_at    |          +----------------+
+---------------+
```

`agents_md_id NULL` significa "sem documento" — a consulta de instância já
usa `SELECT i.*, ...` e ganha `i.agents_md_id` de graça, sem JOIN.

Alternativa considerada: coluna de conteúdo direto em `images`. Rejeitada —
repetir o mesmo texto em N imagens viraria N cópias a manter; o requisito
aprovado é justamente biblioteca + vínculo.

### D2: Injeção na criação junto da identidade SSH, reusando `put_archive`

`_inject_ssh_identity` passa a também gravar o documento vinculado (quando
há): um único `put_archive` adicional com o tar de um membro
`AGENTS.md` (0644, dono conforme `_ssh_owner_uid_gid`). Best-effort igual ao
SSH: falha engolida, instância fica pronta sem o documento.

Alternativa considerada: montar o conteúdo como env/label. Rejeitada —
arquivo em disco é o que a ferramenta de IA lê; env não serve.

### D3: Nova operação de runtime: `exec` (comando arbitrário), não `remove_file`

Adicionar ao protocolo uma operação de execução genérica:

```python
async def exec(self, container_id: str, command: list[str]) -> tuple[int, bytes]: ...
```

Implementada com `docker exec` via aiodocker (ou o equivalente da API),
retornando código de saída e stdout/stderr combinados. A remoção do
`AGENTS.md` é `exec(container, ["rm", "-f", "/config/AGENTS.md"])` — e a
operação fica disponível para usos futuros, em vez de uma operação
monolítica "remover_arquivo" que não se reutiliza.

Alternativa considerada: `remove_file` dedicada. Rejeitada — não existe na
API do Docker como primitiva direta barata; sempre termina em exec. Ser
genérica evita multiplicar operações pontuais no protocolo.

A validação real precisa de e2e (como `put_archive` tem): teste marcado com
Docker de verdade, criando container da base de agente e conferindo a
remoção.

### D4: Propagação ao salvar segue o padrão do SSH regenerado

Ao salvar conteúdo: buscar imagens vinculadas ao documento → instâncias
vivas dessas imagens → `put_archive` em cada uma, isolando falha, e devolver
a lista de falhas para a resposta da rota admin. Ao trocar vínculo: propagar
novo documento nas vivas da imagem; ao desvincular: `exec rm` nas vivas.

Alternativa considerada: só aplicar no próximo restart. Rejeitada pelo
usuário — o comportamento aprovado é propagar ao salvar.

### D5: Aba admin única, duas seções

Nova aba em `AdminPage.jsx`: lista de documentos (nome, tamanho, imagens
vinculadas, ações) com dialog de criação/edição em textarea; e a lista de
imagens do catálogo com um Select de documento por entrada (valor vazio =
nenhum). Nada de CSS novo — MUI e `sx`, como o resto do painel.

### D6: Rotas sob `/api/admin/agents-md`

- `GET /api/admin/agents-md` — lista documentos (com contagem de imagens).
- `POST /api/admin/agents-md` — cria.
- `PATCH /api/admin/agents-md/{id}` — edita conteúdo/nome.
- `DELETE /api/admin/agents-md/{id}` — 409 se vinculado.
- `GET /api/admin/agents-md/images` — imagens com vínculo corrente.
- `PUT /api/admin/agents-md/images/{image_id}` — `{document_id: int|null}`.

A resposta das rotas de edição/vínculo inclui as falhas de propagação
(instance_id + motivo) no mesmo formato da regeneração SSH, para o admin ver
quais instâncias ficaram desatualizadas.

## Risks / Trade-offs

- [`exec` amplia o poder do runtime para comando arbitrário] → o portal já
  equivale a root no host por causa do socket; `exec` não aumenta a
  superfície de quem compromete o portal, e a operação só é chamada com
  comando fixo e validado pelo código do portal, nunca com input de usuário.
- [Documento grande multiplicado por N instâncias vivas] → limite de tamanho
  único no documento (não por instância) e propagação só nas vivas afetadas.
- [Falha parcial na propagação deixa instâncias desatualizadas] → mesma
  decisão do SSH: best-effort com relatório de falhas; o admin pode repetir
  a ação. Consistência perfeita exigiria rastreio de versão por instância —
  fora de escopo.
- [Instância parada tem container, mas o docker exec nela falha] →
  propagar apenas para instância com state `running` e container existente;
  a parada recebe o documento no próximo start via D2.

## Migration Plan

1. `agent_md_documents` + `images.agents_md_id` em `init_db`, migração
   idempotente no padrão das existentes.
2. Serviço `backend/app/services/agents_md.py` e rota
   `backend/app/api/agents_md.py`; registro no `main.py`.
3. `exec` no protocolo, `docker_runtime` e `fake`; injeção em `instances.py`.
4. Aba admin no frontend.
5. Rollback: sem migração destrutiva; colunas novas ficam inertes e as
   rotas podem ser removidas com o router.