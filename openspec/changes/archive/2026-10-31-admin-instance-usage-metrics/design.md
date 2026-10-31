# Design

## Context

Hoje `instances.state` é sobrescrito a cada transição (`backend/app/services/instances.py`
`stop_instance`/`_provision_and_start`/`_resume_existing`, `backend/app/services/reaper.py`
`reap_idle_instances`/`reconcile_instance_states`), sem nenhum timestamp de
"quando entrou nesse estado". `stop_instance` é idempotente e é a mesma função
chamada tanto pela ação do usuário quanto pelo reaper de ociosidade — hoje ela
não sabe diferenciar os dois motivos. Ver `proposal.md` para a motivação.

## Goals / Non-Goals

**Goals:**
- Um registro histórico (`instance_runs`) correto mesmo sob as idempotências e
  caminhos já existentes (parar uma instância já parada, religar sem recriar
  container, reconciliação, exclusão).
- Instâncias já em execução no momento em que este change for implantado devem
  aparecer na visão "rodando agora" — não só as que iniciarem depois.
- Agregações (por usuário, por grupo, por imagem, por motivo, série diária,
  pico de simultaneidade) sobre um período fixo de 30 dias.

**Non-Goals:**
- Seletor de período customizado na UI (fica fixo em 30 dias nesta change;
  o endpoint pode aceitar parâmetros no futuro sem quebrar o formato atual).
- Exportação (CSV ou outro formato) — descartada na exploração.
- Retenção/poda automática do histórico — decidido explicitamente que não há.
- Métricas de custo (CPU/memória) — fora do escopo, ficou para uma change futura.

## Decisions

### Schema de `instance_runs`

```sql
CREATE TABLE IF NOT EXISTS instance_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    image_id INTEGER NOT NULL REFERENCES images(id),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    ended_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_instance_runs_open
    ON instance_runs(instance_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_instance_runs_started_at ON instance_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_instance_runs_user_id ON instance_runs(user_id);
```

`user_id`/`image_id` são desnormalizados a partir de `instances` no momento da
abertura do run, em vez de só `instance_id` com join. Alternativa descartada:
só guardar `instance_id` e sempre dar join com `instances` — funciona para
instâncias vivas, mas `instances` é a mesma linha mutável (nunca recriada por
imagem/usuário diferentes, então na prática não mudaria); a desnormalização
existe principalmente para deixar as consultas de agregação (por usuário, por
imagem) diretas sem depender de `instances` continuar com os mesmos valores.
`ended_reason` é um dos quatro valores já definidos na spec: `user_stop`,
`idle_timeout`, `reconciled`, `deleted`. Nenhum enum nativo — SQLite não tem;
validado na camada de serviço, igual ao resto do projeto (`state` em
`instances` também é `TEXT` livre).

### Abrir e fechar runs nos pontos de transição existentes

Dois helpers novos em `backend/app/services/instances.py`:

```python
def _open_run(conn, instance_id, user_id, image_id) -> None:
    conn.execute(
        """INSERT INTO instance_runs (instance_id, user_id, image_id)
           SELECT ?, ?, ? WHERE NOT EXISTS (
               SELECT 1 FROM instance_runs WHERE instance_id = ? AND ended_at IS NULL
           )""",
        (instance_id, user_id, image_id, instance_id),
    )

def _close_run(conn, instance_id, reason) -> None:
    conn.execute(
        "UPDATE instance_runs SET ended_at = datetime('now'), ended_reason = ? "
        "WHERE instance_id = ? AND ended_at IS NULL",
        (reason, instance_id),
    )
```

O `WHERE NOT EXISTS` em `_open_run` e o `WHERE ended_at IS NULL` em
`_close_run` tornam os dois idempotentes por construção — chamar duas vezes
não duplica nem fecha um run já fechado. Isso é necessário porque
`stop_instance` já é documentado como idempotente, e `create_instance`/
`_resume_existing` têm caminhos que não recriam o container.

Pontos de chamada:
- `_provision_and_start`: `_open_run` logo após o `UPDATE ... state = 'running'`
  de sucesso. Não é chamado nos dois ramos de erro (criação/start falhos não
  viram "run" nenhum — coerente com a spec `desktop-instances` de que falha
  não deixa instância em execução).
- `_resume_existing`: `_open_run` no ramo de sucesso que só reinicia o
  container existente (sem recriar) — o ramo que recria já cai em
  `_provision_and_start`, que já abre.
- `stop_instance`: ganha um parâmetro `reason: str = "user_stop"`. A rota
  HTTP de parada chama sem o argumento (motivo padrão); `reap_idle_instances`
  passa `reason="idle_timeout"`. `_close_run(conn, instance_id, reason)`
  substitui o `UPDATE instances SET state = 'stopped'` isolado — os dois
  updates (estado da instância e fechamento do run) ficam na mesma função.
- `reconcile_instance_states`: `_close_run(conn, row["id"], "reconciled")`
  junto do `UPDATE instances SET state = 'stopped'` já existente.
- `delete_instance`: `_close_run(conn, instance_id, "deleted")` antes do
  `UPDATE instances SET deleted_at = ...` — no-op se não havia run aberto
  (instância já estava parada).

### Backfill de runs abertos na inicialização

Instâncias já `state = 'running'` no banco quando esta change for implantada
não têm run aberto (ninguém chamou `_open_run` para elas). Sem tratar isso, a
visão "rodando agora" as omitiria até a próxima parada/início. Mitigação: no
`lifespan` de `main.py`, no mesmo lugar onde já roda a reconciliação
one-shot histórica, adicionar um passo que abre um run para toda instância
`running` sem run aberto, usando `COALESCE(last_seen_at, created_at)` como
`started_at` (melhor aproximação disponível — o instante real de início não
foi registrado). Mesmo idempotência do `_open_run`: rodar esse passo de novo
em reinícios futuros não duplica nada.

### Agregações calculadas em código, não em SQL puro

Duração de um run (aberto ou fechado) usa
`COALESCE(ended_at, datetime('now')) - started_at`, incluindo runs em curso
nos totais do período — um usuário com sessão aberta há 2h conta essas 2h no
agregado mesmo antes de parar.

- **Por usuário / por imagem / por motivo**: uma consulta agregada (`GROUP BY`)
  sobre `instance_runs` filtrada por `started_at`/`ended_at` sobrepondo o
  período de 30 dias, com a duração calculada acima somada em Python (SQLite
  não tem funções de data/hora com precisão de segundos prontas para subtração
  direta em agregação — mais simples e testável calcular em Python após
  buscar as linhas cruas do período).
- **Por grupo**: join `instance_runs → users → user_groups → groups`. Um
  usuário em múltiplos grupos tem suas horas contadas uma vez em cada grupo a
  que pertence — é a semântica mais simples e consistente com como
  `group_images`/`user_groups` já tratam pertencimento múltiplo no projeto;
  não deve ser interpretado como as somas dos grupos batendo com o total
  geral.
- **Série diária**: para cada dia do período (30 iterações), conta runs cujo
  intervalo `[started_at, COALESCE(ended_at, now)]` sobrepõe aquele dia.
  Trinta queries pequenas por carregamento do painel é aceitável (operação
  admin, não hot path).
- **Pico de simultaneidade**: varredura (sweep-line) em Python sobre os
  intervalos `(started_at, COALESCE(ended_at, now))` dos runs do período —
  gera eventos +1 no início e -1 no fim, ordena por instante e acompanha o
  máximo acumulado. Alternativa descartada: calcular via window function no
  SQLite — possível (3.25+), mas bem menos legível que o sweep em Python para
  o volume de dados esperado (instalação self-hosted, não multi-tenant em
  larga escala).

### Endpoints administrativos novos

Novo router `backend/app/api/usage_metrics.py`, montado sob `/api/admin`
com `Depends(require_admin)` no nível do router, igual aos routers admin
existentes:
- `GET /api/admin/usage/live` — instâncias com run aberto agora (join com
  `instances`/`images`/`users`), duração calculada no momento da resposta.
- `GET /api/admin/usage/runs` — histórico paginado dos últimos 30 dias
  (usuário, imagem, início, fim, duração, motivo).
- `GET /api/admin/usage/summary` — um único payload com os agregados: por
  usuário, por grupo, ranking de imagens, distribuição por motivo, série
  diária e pico de simultaneidade. Um endpoint só evita múltiplas idas ao
  backend para montar um painel que é sempre visto como um todo.

### Frontend: biblioteca de gráfico

O projeto não tem biblioteca de charting. Para a série diária, adiciono
`@mui/x-charts` — é o pacote de gráficos da própria família MUI (mesma major
version já usada, v6), então herda o tema sem configuração extra e evita
introduzir um sistema de design paralelo (Recharts/Victory/Nivo trariam
estilo próprio para reconciliar com o MUI existente).

## Risks / Trade-offs

- [Instâncias já rodando no deploy não têm run aberto] → mitigado pelo passo
  de backfill no `lifespan` descrito acima.
- [Série diária com 30 queries pequenas por carregamento do painel] → aceitável
  dado o uso administrativo pouco frequente; se virar problema real de
  desempenho, dá para reescrever como uma única query com CTE recursiva de
  dias sem mudar o contrato do endpoint.
- [Horas por grupo não somam para o total geral quando há sobreposição de
  membros entre grupos] → documentado na decisão acima; é comportamento
  esperado, não um bug a corrigir depois.
- [`ended_reason` como texto livre, sem enum do banco] → consistente com
  `instances.state` já existente no projeto; validação fica na camada de
  serviço, não no schema.

## Migration Plan

`instance_runs` e seus índices são criados via `CREATE TABLE IF NOT EXISTS` /
`CREATE INDEX IF NOT EXISTS` em `backend/app/db.py`, no mesmo padrão das
tabelas existentes — criada automaticamente na próxima inicialização do
backend, sem passo manual. É puramente aditiva: nenhuma coluna ou tabela
existente é alterada. Rollback é reverter o código e, se necessário,
`DROP TABLE instance_runs` — não há dado pré-existente em risco.
