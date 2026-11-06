# Design

## Context

A persistência hoje é `sqlite3` nativo: conexão por requisição
(`deps._open_db`), SQL cru com placeholders `?`, linhas como `sqlite3.Row`,
DDL com `datetime('now')` e migrações guardadas por `PRAGMA table_info`
(`db.py`). Nenhum requisito de spec fixa o motor — ver proposal.md para a
motivação e `specs/database-persistence/spec.md` para o contrato.

## Goals / Non-Goals

**Goals:**

- Um único corpo de código de acesso a dados que roda nos dois dialetos.
- Dev local continua subindo sem nada além do Docker (SQLite, compose dev
  inalterado).
- Produção com PostgreSQL provido pela própria composição, banco novo.
- Rollback trivial para a versão SQLite anterior.

**Non-Goals:**

- Migração de dados SQLite → Postgres (produção nasce do zero; decidido na
  proposição).
- Reescrever o acesso a dados como ORM com modelos de domínio.
- Suporte a bancos além de SQLite e PostgreSQL.
- Pool externo (pgbouncer) ou alta disponibilidade do banco.

## Decisions

### D1 — SQLAlchemy Core síncrono como camada portável

Query language do Core (não ORM), engine síncrono com pool. O formato das
funções atuais (`def f(conn, ...)`, SQL explícito) se preserva: os textos
SQL migram para `text()` com parâmetros nomeados `:nome`, revisáveis por
diff, e as linhas voltam como mapeamentos nos dois dialetos.

Alternativas consideradas:

- *Adaptador fino sobre `sqlite3` + `psycopg`*: traduzir `?`/`:nome` →
  `%(nome)s`, unificar `sqlite3.Row` com `dict_row`, duplicar DDL e
  migrações por dialeto. Rejeitado: duas sintaxes vivas para manter
  indefinidamente, e o bootstrap idempotente (parte mais sutil de `db.py`)
  existiria em duas versões.
- *SQLAlchemy async + asyncpg*: rejeitado — obrigaria converter toda a
  cadeia de endpoints/services para async de uma vez, multiplicando o
  refactor sem ganho prático: o banco fica na mesma rede interna, as
  queries são pontuais e o pool elimina o custo de conexão por requisição
  que o SQLite tinha.

O tipo público das dependências (`get_db`) muda de `sqlite3.Connection`
para `Connection` do SQLAlchemy; os services continuam recebendo uma
conexão por requisição, devolvida ao pool ao final.

### D2 — Schema único em `MetaData`, migrações por Inspector

Um único `MetaData` descreve tabelas, índices (inclusive os parciais, que
o Postgres suporta) e chaves; `create_all` compila para cada dialeto.
Defaults de timestamp viram `server_default=func.now()` — `CURRENT_TIMESTAMP`
nos dois motores, com o mesmo formato UTC `YYYY-MM-DD HH:MM:SS` que o
SQLite grava hoje, preservando o parsing existente em `usage_metrics`.

As migrações idempotentes trocam `PRAGMA table_info` por
`sqlalchemy.inspect(conn).get_columns(...)`; `ALTER TABLE ADD COLUMN`
com `DEFAULT` é aceito pelos dois dialetos. `init_db` roda
`create_all` + migrações dentro de uma transação.

### D3 — Tipos explícitos nas fronteiras de dialeto

- `DateTime` (naive, UTC — como hoje): guarda string ISO idêntica no
  SQLite e `timestamp` no Postgres. Pontos que manipulam timestamps como
  string normalizam na borda (`str(valor)[:19]` quando o valor já vem
  como `datetime`).
- `Boolean` para `is_admin`, `enabled`, `harden_desktop`: o Core devolve
  `bool` nos dois motores; comparações `== 1` existentes seguem válidas
  (`True == 1`).
- `LargeBinary` para os BLOBs Fernet (chaves SSH, env/headers de MCP).
- Chave inteira auto-incremento vira identity/serial no Postgres; o
  código que lê `last_insert_rowid`/`rowid` migra para o retorno do
  `insert().` do Core.

### D4 — Seleção por `WCUI_DATABASE_URL`

`config.py` ganha `database_url: str | None` (default `None`). Presente →
engine PostgreSQL (`postgresql+psycopg://`); ausente → engine SQLite em
`WCUI_DB_PATH`. O compose de produção monta a URL a partir de
`WCUI_POSTGRES_PASSWORD`; dev e testes não definem a variável e seguem em
SQLite.

### D5 — Postgres 17 na composição de produção

Serviço `postgres:17-alpine` na `wcui_net`, sem `ports`, volume nomeado
`wcui_pg_data`, `restart: unless-stopped`, healthcheck `pg_isready`; o
portal passa a depender com `condition: service_healthy` (composição já
usa healthcheck no portal). Credencial via `WCUI_POSTGRES_PASSWORD` em
`deploy/.env` (mesmo padrão das demais `WCUI_*`).

### D6 — Verificação contra Postgres real na suíte e2e

A suíte padrão (`pytest`, sem Docker) continua 100% sobre SQLite — é o
modo dev, e é o que roda rápido. A suíte e2e (que já exige Docker) ganha
um serviço Postgres efêmero e executa o bootstrap + operações de service
contra ele, cobrindo o requirement de equivalência de comportamento.
Testes unitários de migração idempotente rodam nos dois motores (Postgres
quando disponível).

## Risks / Trade-offs

- **Conversão de ~150 queries em ~35 arquivos** → migração arquivo por
  arquivo com a suíte verde a cada passo; SQL permanece texto revisável em
  `text()`, não expressões opacas.
- **Timestamps como `datetime` no Postgres vs string no SQLite** →
  normalização na borda (D3); e2e de métricas cobre o caminho que antes
  quebrou com fuso (`last_seen_at`).
- **Queries síncronas em endpoints async com rede no caminho** → pool de
  conexões do engine; queries pontuais sem varreduras; portal já roda com
  um worker e o padrão atual (SQLite síncrono) não muda de forma.
- **Diferenças sutis de SQL** (`LIKE`, ordenação, `substr`) → a suíte de
  services roda inteira sobre SQLite e os fluxos críticos repetem na e2e
  de Postgres; nada de dialeto-specific novo entra sem os dois testes.
- **Instâncias órfãs ao migrar produção** (containers vivos sem registro
  no banco novo) → procedimento documentado: encerrar instâncias antes de
  atualizar; `deploy/README.md` cobre o passo.

## Migration Plan

1. Backup do arquivo SQLite existente (passo já documentado em
   `deploy/README.md`).
2. Preencher `WCUI_POSTGRES_PASSWORD` em `deploy/.env`; `down` da
   composição antiga; encerrar instâncias vivas antes do `down`.
3. `up -d --build`: Postgres sobe, bootstrap cria o schema, admin inicial
   é provisionado das `WCUI_ADMIN_*` e o catálogo é re-semeado (fluxos
   já existentes no startup).
4. **Rollback**: remover `WCUI_DATABASE_URL`/serviço postgres e voltar à
   imagem anterior — o arquivo SQLite nunca é tocado pela versão nova
   quando a URL está definida, então o estado antigo está intacto.

## Open Questions

Nenhuma — versão/tag do Postgres (17-alpine) e formato da URL são
decididos aqui e reversíveis em tasks.
