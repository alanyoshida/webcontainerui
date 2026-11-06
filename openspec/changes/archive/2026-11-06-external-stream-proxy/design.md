# Design

## Context

Hoje o Caddy só termina TLS e repassa tudo ao portal
(`deploy/Caddyfile`); o transporte de `/i/{uuid}/` é feito dentro do
FastAPI (`api/session_proxy.py`) — autorização manual, injeção de Basic
auth da instância e relay WS dois-por-dois, tudo no worker único. Os
requisitos de comportamento estão em `session-proxy` e permanecem; este
change muda quem transporta. Motivação em proposal.md; contrato em
`specs/stream-data-plane/spec.md`.

Fatos que condicionam: Caddy já está na `wcui_net`; o portal já executa
comandos fixos nos containers via `runtime.exec` (remoção de AGENTS.md);
o webtop usa `SUBFOLDER=/i/{uuid}/`, então o path chega intacto ao
container; `ActivityTracker` já throttleia a persistência de atividade.

## Goals / Non-Goals

**Goals:**

- Frames fora do processo do portal em produção, com autorização e
  credencial mantendo as três camadas atuais.
- Caddy imagem oficial (`caddy:2-alpine`), sem builds customizados.
- Dev, testes e o stack e2e continuam sem proxy externo.

**Non-Goals:**

- Trocar o Caddy por outro proxy (Traefik) — decidido na conversa: Caddy
  já está na frente e tem `forward_auth` nativo.
- Multi-host / balanceamento entre hosts.
- Métricas de tráfego por sessão no portal (o portal deixa de ver frames;
  observação de tráfego passa a ser do plano de dados).

## Decisions

### D1 — Caddy existente como plano de dados, via `forward_auth`

`forward_auth` consulta o portal antes de cada requisição e do upgrade WS
(um upgrade é uma requisição HTTP); WS é repassado nativamente. Alternativa
Traefik descartada: adicionaria um componente novo no caminho quente sem
ganho funcional (decisão registrada pelo usuário).

### D2 — Rotas por arquivo importado + `caddy reload`

O Caddyfile importa `deploy/caddy-routes/*.caddy` (volume compartilhado
com o portal); o portal escreve um arquivo por instância viva e executa
`caddy reload` **via `runtime.exec` no container do Caddy** — comando fixo
no código, mesmo padrão já usado para remover AGENTS.md. O `reload` do
Caddy valida a nova config e mantém a última boa em caso de erro.

Alternativas consideradas:

- *Admin API (`POST /load`)*: substitui a config **inteira** — o portal
  teria que replicar a automação TLS do Caddyfile; rejeitado.
- *caddy-docker-proxy (labels)*: exige imagem custom com plugin
  (supply chain própria) para eliminar um `docker exec`; rejeitado.

O portal publica no startup (instâncias vivas) e em cada transição de
`state=running` ↔ parada/exclusão, serializado — o portal é single worker.

### D3 — Autorização: endpoint interno com segredo de plano de dados

Endpoint no portal (mesmo processo, rota interna — ex. `/internal/data-plane/authorize`)
que executa exatamente a tríade atual (sessão válida, dono, `running`) e
responde 200 com `Authorization: Basic <credencial-da-instância>` em
cabeçalho; recusas espelham os códigos atuais (401/404/409). O Caddy:
`forward_auth` com `copy_headers Authorization` (substitui o do cliente —
que já não repassa nada do cliente) e `header_up` limpo.

O endpoint exige um **segredo compartilhado** (`WCUI_DATA_PLANE_SECRET`,
env de portal e Caddy) enviado em header fixo pelo `forward_auth` — é o
que materializa "não responde a decisões para quem não é o plano de
dados". A resposta nunca vai ao cliente: o `forward_auth` só copia os
headers configurados.

### D4 — Atividade: toque na autorização + heartbeat da visão de sessão

O endpoint de autorização dá `tracker.touch(instance_id)` (requisições
HTTP e upgrades WS continuam sendo sinais). Para o uso que fica invisível
— CLI de agente trafegando só por WS com a visão aberta — a **visão de
sessão no front-end emite heartbeat throttled** (ex.: 1×/min enquanto
montada) a um endpoint autenticado existente-like que toca o mesmo
tracker. Semântica honesta: "usuário com a sessão aberta" — fechou a aba,
o WS morre e a ociosidade progride como hoje. `ActivityTracker` e reaper
não mudam.

### D5 — Sem chave de modo: o proxy in-process permanece registrado

Nenhuma variável liga/desliga: as rotas FastAPI de `/i/{uuid}/` continuam
registradas sempre. Em produção a borda roteia `/i/*` aos containers, e o
caminho no portal fica sombreado (inalcançável de fora); em dev/testes é
o caminho usado. Evita branching de configuração e preserva o caminho de
defesa: se alguém alcançar o portal direto, a autorização continua lá.

### D6 — Timeouts e recusa mantidos na borda

Os snippets de rota carregam `transport http { read_timeout 3600s;
write_timeout 3600s }` (mesmo contrato do Caddyfile atual) e o
`forward_auth` falha fechado (portal ausente ⇒ 502/recusa, nada
encaminhado). `SUBFOLDER` do container inalterado — o path chega igual.

## Risks / Trade-offs

- **Janela entre `state=running` e rota publicada** → publicação faz parte
  da mesma transição pós-start; até lá a borda devolve recusa (sem
  encaminhar), mesmo contrato de instância não pronta.
- **Falha de `caddy reload`** → Caddy segue com a última config boa; o
  portal loga e a rota é reescrita no próximo evento de ciclo de vida da
  instância. Rota faltante rejeita (não vaza), nunca encaminha errado.
- **Atividade mais grosseira** (heartbeat 1×/min vs. toque por mensagem) →
  reaper com janela de ociosidade em minutos não percebe a diferença;
  documento em `deploy/README.md` que o parâmetro de ociosidade não deve
  baixar abaixo da granularidade do heartbeat.
- **Superfície do Caddy cresce** (alcança containers diretamente) → o
  Caddy já vive na `wcui_net`; `deploy/SECURITY.md` ganha seção sobre o
  plano de dados e o segredo compartilhado.
- **Coordenação com `postgres-for-production`** → ambos mudam
  `deploy/docker-compose.yml`; aplicar em ordes separadas, resolvendo o
  conflito de compose na segunda merge (sem dependência funcional).

## Migration Plan

1. Deploy da versão nova: portal sobe, publica rotas das instâncias vivas
   e recarrega o Caddy; Caddyfile novo assume `/i/*` na borda.
2. Sessões abertas no momento da troca: o relay in-process delas termina
   quando o Caddy recarrega — o cliente reconecta pelo novo caminho (o
   front-end já reconecta WS).
3. **Rollback**: restaurar o Caddyfile anterior (tudo volta a atravessar o
   portal) — nenhum dado ou schema muda nesta change.

## Open Questions

Nenhuma bloqueante: nome/path do endpoint interno e granularidade do
heartbeat são escolhas de implementação reversíveis em tasks.
