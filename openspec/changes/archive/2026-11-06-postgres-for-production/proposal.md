# Proposal

## Why

SQLite em arquivo local atende o desenvolvimento, mas em produção limita operação: backup quente, inspeção ad-hoc, retenção de métricas e ferramentas maduras de administração ficam artificiais em um arquivo no volume do portal. O PostgreSQL como serviço na composição de produção dá ao operador backup, observabilidade e evolução de schema sem parar o portal — enquanto o dev local continua subindo com zero dependência externa.

## What Changes

- A camada de persistência passa a suportar dois dialetos — **SQLite** (padrão, dev local) e **PostgreSQL** (produção) — selecionados por variável de ambiente (`WCUI_DATABASE_URL` presente → Postgres; ausente → SQLite em `WCUI_DB_PATH`).
- O bootstrap de schema e as migrações idempotentes passam a rodar em ambos os dialetos; o padrão atual (`PRAGMA table_info`, `datetime('now')`, placeholders `?`) é SQLite-específico e é abstraído.
- **BREAKING**: `deploy/docker-compose.yml` (produção) ganha um serviço `postgres` (rede interna, sem porta publicada, volume próprio, healthcheck) e o portal passa a exigir o banco pronto antes de iniciar. Não há migração de dados do SQLite — produção existente migra recriando usuários/catálogo em banco novo, ou permanece na versão anterior.
- O backend ganha dependência do driver `psycopg` (v3) e de SQLAlchemy Core como camada portável de conexão/DDL.
- Compose de dev (`docker-compose.dev.yml`) não muda: continua só SQLite.

## Capabilities

### New Capabilities

- `database-persistence`: qual banco de dados o portal usa por ambiente, como é configurado via ambiente, como o schema é criado e migrado de forma idempotente nos dois dialetos, e como a composição de produção provê e condiciona a subida ao PostgreSQL.

### Modified Capabilities

Nenhuma — nenhum requisito existente fixa o motor de banco; os comportamentos de auth, catálogo, instâncias, métricas etc. permanecem os mesmos.

## Impact

- **Backend**: `backend/app/db.py` (conexão, DDL e migrações — reescrito), `backend/app/config.py` (nova `database_url`), `backend/app/deps.py` (tipo da conexão); todos os services e rotas que usam SQL cru com `?` (~35 arquivos) migram para SQL portável com parâmetros nomeados.
- **Deploy**: `deploy/docker-compose.yml` (serviço `postgres` + credenciais + `depends_on` com healthcheck), `deploy/.env.example` (novas variáveis), `deploy/README.md` (backup/reversão), `deploy/SECURITY.md` (superfície do Postgres).
- **Documentação**: `README.md` e `AGENTS.md` (seções de banco, testes e subida).
- **Testes**: suíte padrão continua em SQLite (sem Docker); verificação contra Postgres real entra na suíte e2e, que já exige Docker.
- **Dependências**: `sqlalchemy`, `psycopg` (extras de produção) em `backend/pyproject.toml`.
