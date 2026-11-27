---
title: Banco de dados
description: SQLite em desenvolvimento e testes, PostgreSQL em produção, e as convenções de SQLAlchemy Core que mantêm o comportamento igual nos dois motores.
sidebar:
  order: 3
---

O portal usa dois motores de banco, escolhidos por ambiente: SQLite em desenvolvimento e testes locais, sem nenhuma dependência extra, e PostgreSQL em produção. O acesso a dados é escrito uma única vez, em SQLAlchemy Core, para rodar igual nos dois.

## Seleção do motor

A escolha depende de uma única variável:

| Situação | Motor | Onde ficam os dados |
|---|---|---|
| `WCUI_DATABASE_URL` ausente ou vazia | SQLite | Arquivo em `WCUI_DB_PATH` (padrão `/data/webcontainerui.db`) |
| `WCUI_DATABASE_URL` definida | PostgreSQL | Banco apontado pela URL, no formato `postgresql+psycopg://usuario:senha@host:5432/banco` |

Nenhuma outra configuração nem mudança de código é necessária.

## SQLite em desenvolvimento

Cada conexão SQLite é aberta com `journal_mode = WAL`, `busy_timeout` de 5 segundos e `foreign_keys` ligado. Na composição de desenvolvimento, o arquivo fica no volume `wcui_db_dev`.

## PostgreSQL em produção

A própria composição de produção provê o banco:

- imagem `postgres:17-alpine`, banco e usuário `wcui`;
- senha em `WCUI_POSTGRES_PASSWORD`; a URL de conexão é montada no [`docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml);
- apenas na rede interna `wcui_net`, sem porta publicada no host;
- dados no volume nomeado `wcui_pg_data`, que sobrevive à recriação dos containers;
- verificação de prontidão com `pg_isready`; o portal só inicia depois que o banco responde como saudável.

:::note
A produção nasce com banco vazio. Não há migração automática de um banco SQLite existente para o PostgreSQL.
:::

Procedimentos de backup e de retorno a uma versão anterior estão em [Backup e restauração](/operations/backup-and-restore/) e [Reversão](/operations/rollback/).

## Acesso a dados

Tudo passa por SQLAlchemy Core, em [`backend/app/db.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/db.py), com SQL explícito e parâmetros nomeados. Não há ORM.

### Schema e migrações

O schema vive num único `MetaData` e é criado com `create_all`. Como `create_all` não altera tabelas já existentes, as migrações são idempotentes e feitas via `Inspector`: quando uma coluna falta, o portal executa `ALTER TABLE ADD COLUMN`. Nenhuma migração depende de `PRAGMA`.

O resultado é que iniciar contra um banco vazio cria o schema completo, e reiniciar sobre um banco já migrado é uma operação nula.

:::caution
Em produção, faça backup com `pg_dump` antes de atualizar para uma versão que altere o schema.
:::

### Conexões

As conexões expostas aos serviços são `DbConnection`, um wrapper em que:

- `execute` recebe SQL em `text()` com parâmetros nomeados no formato `:nome`;
- as linhas do resultado são acessíveis por nome de coluna;
- inserts que precisam do identificador gerado usam `RETURNING id`.

### Timestamps

Timestamps são `DateTime` naive em UTC, gravados com precisão de segundo nos dois motores. Como `text()` não carrega informação de tipo, uma coluna de data volta como `str` no SQLite e como `datetime` no PostgreSQL. Por isso:

- binds usam `format_ts` ou `ts_param`;
- ao consumir uma coluna de data, o código normaliza com `as_datetime` ou `format_ts`.

### Booleanos

Colunas como `is_admin`, `enabled` e `harden_desktop` são `Boolean`. As comparações são feitas por parâmetro (`= :flag`), nunca com literal `= 1`, que não é portável entre os motores.

## Testes

| Suíte | Comando | Banco |
|---|---|---|
| Padrão | `pytest` | SQLite; não exige Docker |
| e2e | `pytest -m e2e` | Sobe um PostgreSQL efêmero em Docker |

A suíte e2e valida bootstrap, login, usuários, ciclo de instância e métricas contra o PostgreSQL, cobrindo o que é específico do dialeto. Os comandos completos estão em [Desenvolvimento](/reference/development/).

## Referência formal

O contrato de comportamento está na spec [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md).
