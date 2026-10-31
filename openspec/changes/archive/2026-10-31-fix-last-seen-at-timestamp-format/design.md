# Design

## Context

Ver `proposal.md` para a motivação. Hoje três lugares geram timestamps
para colunas do banco:
- `backend/app/db.py` (schema): `DEFAULT (datetime('now'))` para
  `created_at` etc. — formato SQLite `YYYY-MM-DD HH:MM:SS`.
- `backend/app/services/instances.py` (`_open_run`/`_close_run`): mesma
  convenção, via `datetime('now')` nas próprias queries.
- `backend/app/services/activity.py` (`_now_iso`) e
  `backend/app/services/reaper.py` (`_cutoff_iso`): Python,
  `datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")`,
  que inclui `+00:00` por o datetime ser "aware".

`last_seen_at` e o cutoff de ociosidade usam a terceira convenção;
tudo mais usa a primeira. O projeto já tem um precedente de migração de
schema rodada a cada `init_db` (`_migrate_add_icon_path`), mas nenhuma
migração de *dados* (corrigir valores já gravados, não a forma da coluna).

## Goals / Non-Goals

**Goals:**
- Uma única convenção de formato de timestamp em todas as colunas do
  banco, sem exceção.
- Bancos existentes (como o de dev, que já tem linhas no formato antigo)
  saem corrigidos automaticamente na próxima inicialização do backend.
- `usage_metrics` nunca quebra por causa do formato de um timestamp,
  mesmo que uma linha escape da migração por algum motivo não previsto.

**Non-Goals:**
- Mudar o que conta como "ocioso" ou qualquer outro comportamento
  observável — isto é puramente sobre a representação em string do mesmo
  instante UTC.
- Introduzir uma ferramenta de migração genérica; o passo adicionado segue
  estritamente o padrão pontual já existente (`_migrate_add_icon_path`).

## Decisions

### Unificar no formato sem offset (convenção do SQLite), não no formato com offset

Alternativa descartada: fazer todo o resto do banco passar a usar
`isoformat()` com offset (padronizar "para cima", não "para baixo").
Rejeitada porque a maioria dos timestamps (`created_at`, `started_at`,
`ended_at`, `deleted_at`) já é gravada via `datetime('now')` do próprio
SQL, sem depender do lado Python — mudar isso exigiria trocar todo UPDATE/
INSERT que usa a função nativa do SQLite por uma string construída em
Python, uma mudança bem maior para o mesmo resultado. Mais simples fazer
os dois pontos em Python (`activity.py`, `reaper.py`) seguirem a convenção
que já domina o banco.

```python
# backend/app/services/activity.py
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```
Mesma mudança em `reaper.py`'s `_cutoff_iso`.

### Migração de dados para linhas já gravadas, seguindo o padrão de `_migrate_add_icon_path`

```python
# backend/app/db.py
def _migrate_normalize_last_seen_at(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE instances SET last_seen_at = substr(last_seen_at, 1, 19)
           WHERE last_seen_at LIKE '____-__-__ __:__:__+%'"""
    )
```
`substr(..., 1, 19)` corta exatamente nos 19 caracteres de
`YYYY-MM-DD HH:MM:SS`, descartando qualquer sufixo de fuso. O `LIKE` com
`+%` no fim garante que só linhas realmente no formato antigo são tocadas
— idempotente, rodar de novo em cima de dados já normalizados não casa
com o padrão e não faz nada. Chamada em `init_db`, junto de
`_migrate_add_icon_path`.

### `usage_metrics._parse` tolerante aos dois formatos, como proteção adicional

```python
def _parse(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, _TS_FORMAT)
    except ValueError:
        return datetime.fromisoformat(ts).replace(tzinfo=None)
```
Não é a correção principal (a migração já normaliza os dados na origem),
mas cobre qualquer linha que escape dela — por exemplo, um banco restaurado
de um backup externo, ou uma versão futura que reintroduza timestamps com
offset em outro lugar. Custo de manutenção baixo, risco de regressão
silenciosa evitado.

## Risks / Trade-offs

- [`UPDATE` com `LIKE` roda em todo `init_db`, mesmo depois de já ter
  normalizado tudo] → o padrão `+%` não casa mais com nada depois da
  primeira execução, então o custo das execuções seguintes é um table
  scan vazio sobre `instances` — mesma categoria de custo que
  `_migrate_add_icon_path` já paga hoje via `PRAGMA table_info`.
- [Uma linha com fuso diferente de UTC, não `+00:00`, escaparia do
  `LIKE '+%'`] → não é um caso real hoje (`activity.py` sempre usa
  `timezone.utc`), mas fica coberto de qualquer forma pelo parsing
  tolerante em `usage_metrics._parse`, que aceita qualquer offset válido
  via `fromisoformat`.
