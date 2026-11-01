# Design

## Context

A API do catálogo hoje só cria e executa ações pontuais (retry-pull,
update-image, capa, disable). `create_image` aceita limites no cadastro, mas
nada os altera depois. O disable é one-way: não há enable. `harden_desktop`
existe em `CreateImageRequest`, `ImageResponse`, `create_image` e na coluna
NOT NULL de `images` — nunca lido por `_build_spec`, runtime ou entrypoint
(achado I1 do pentest). O frontend nem o expõe no formulário de criação.
Modelo dos módulos vizinhos para edição parcial: `mcp_servers.update_mcp_server`
e `agents_md.update_document` (só as colunas recebidas).

## Goals / Non-Goals

**Goals:**

- Edição parcial e segura dos campos de apresentação/recurso, com validação.
- Reativação simétrica ao disable.
- `harden_desktop` fora da superfície da API, sem migração de schema.

**Non-Goals:**

- Edição de `repository`/`tag`/`provision_kind` (decisão do usuário: mudar
  identidade é "recriar entrada"; `update-image` já cobre tags móveis).
- Recriação automática de instâncias vivas após edição — o dono aplica pelo
  próprio botão "atualizar imagem", fluxo existente.
- Implementação de endurecimento real (`harden_desktop`) — change própria,
  se um dia houver semântica definida.
- Auditoria das edições — coberta pela trilha da change `security-audit-log`
  (o evento `admin.image.changed` com `detail=op=editar` passa a ser emitido
  no novo endpoint).

## Decisions

### D1 — `update_image` com semântica "só as colunas recebidas"

`services/images.py` ganha `update_image(conn, image_id, *, settings,
display_name=None, shm_size_mb=None, mem_limit_mb=None, cpu_limit=None,
port=None)`: valida os campos recebidos (`> 0`; `port` entre 1 e 65535),
levanta `NotFoundError` se a entrada não existe e aplica `UPDATE` só das
colunas presentes. Rota `PATCH /api/admin/images/{id}` com corpo
`UpdateImageRequest` (todos os campos opcionais) devolvendo `ImageResponse`.
Sem campos recebidos → 400 (edição vazia é erro do cliente, não no-op
silencioso).
Alternativa rejeitada: `PUT` com objeto completo — obriga o front a
reenviar tudo e cria risco de sobrescrever limites com stale data.

### D2 — Identidade imutável por omissão, não por filtro

`UpdateImageRequest` nem declara `repository`/`tag`/`provision_kind`: o
Pydantic descarta campo desconhecido e o endpoint não tem como alterá-los —
imutabilidade estrutural, não uma checagem que alguém esquece de chamar.
`pull_state`, `enabled` e `icon_path` também ficam fora (têm endpoints
próprios com semântica própria).

### D3 — `enable` espelha o disable, idempotente

`POST /api/admin/images/{id}/enable`: `UPDATE images SET enabled = 1 WHERE
id = ?`, 204; ativar entrada já ativa é no-op feliz (spec exige idempotência)
— diferente do disable, que exige `confirm` porque causa perda de oferta;
reativar só devolve. Emite `admin.image.changed` com `detail=op=reativar`
(hábito da trilha de auditoria).

### D4 — `harden_desktop`: fora da API, coluna dormente

Remover de `CreateImageRequest`, `ImageResponse` e do `INSERT`/assinatura de
`create_image` (a coluna NOT NULL DEFAULT 0 aceita a omissão sem migração).
Linhas existentes mantêm o valor — irrelevante, nunca lido. Testes que
afirmam o campo na resposta são atualizados. Registro no design basta como
rastro; o pentest (I1) fica fechado com o link para esta change.

### D5 — Frontend: diálogo reutilizando o formulário de criação

`ImagesPanel` ganha estado de edição: o mesmo diálogo/formulário de criação,
pré-preenchido com a linha clicada, submetendo `adminEditImage(imageId,
payload)` → PATCH com só os campos alterados. Botão "editar" na linha (ícone
de lápis) ao lado dos existentes; botão "reativar" aparece só em entradas
desabilitadas, no lugar do "desabilitar". `ImageResponse` de sempre alimenta
a tabela — sem tipagem nova.

## Risks / Trade-offs

- [Limite editado durante pull em curso] → inofensivo: limites só são lidos
  na criação de container; o pull em curso continua e termina.
- [Admin espera que editar limite aplique em instâncias vivas na hora] →
  mitigado na UI: após salvar, o diálogo informa que instâncias existentes
  aplicam ao serem atualizadas pelo dono (texto curto de confirmação).
- [`port` editado com instâncias vivas na porta antiga] → mesmo fluxo do
  limite: vale na criação/atualização; o proxy usa a porta da linha do
  catálogo, então instâncias antigas só voltam a funcionar após atualizadas —
  comportamento idêntico ao de uma imagem cadastrada com outra porta, sem
  estado novo.
- [PATCH com campos desconhecidos] → Pydantic descarta; sem erro (tolerante
  a evolução do cliente).

## Migration Plan

Deploy único, aditivo (dois endpoints novos + campo a menos). Rollback:
`git revert`. A coluna `harden_desktop` permanece no banco — nenhuma
migração para reverter.
