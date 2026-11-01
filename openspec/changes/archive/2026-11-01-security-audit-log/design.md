# Design

## Context

O portal já usa `logging` da stdlib em dois serviços de fundo (reaper,
activity_flusher) sem configuração própria — o uvicorn imprime na saída
padrão e o compose coleta com `docker logs`. Não há request-id, corrente de
auditoria nem persistência dedicada; adicionar qualquer dependência ou
tabela para isto seria desproporcional ao perfil do produto (um worker,
SQLite, deploy compose único).

## Goals / Non-Goals

**Goals:**

- Trilha de eventos de segurança consumível por máquina (uma linha JSON por
  evento) sem dependência nova nem migração.
- Cobertura das quatro famílias: autenticação, gestão de acesso, bibliotecas
  que propagam aos containers, ciclo de vida de instâncias.
- Contrato explícito de o que nunca é registrado.

**Non-Goals:**

- Persistência em banco, alertas, retenção configurável — o operador aponta
  seu coletor no stdout (12-factor).
- Log de acesso HTTP genérico (cada request) — só eventos de segurança; o
  access log do Caddy cobre o resto quando necessário.
- Trilha imutável/assinada (não há ameaça de administrador local alterando
  log neste modelo de ameaça — o admin já equivale a root no host, ver
  `deploy/SECURITY.md`).

## Decisions

### D1 — Emissor único, logger dedicado, linha JSON no stdout

`backend/app/services/audit_log.py`: `audit(event: str, **fields)` que
escreve `json.dumps({"event": ..., **fields}, ensure_ascii=False)` num
logger dedicado `wcui.audit` (nível INFO, handler próprio criado no lifespan
de `main.py`, `propagate=False` para não duplicar no logger raiz). Campos
convencionais: `actor_id`, `actor_email`, `ip`, `target`, `outcome`
(`"success"`/`"failure"`/`"denied"`), `detail` (curto, sem segredo).
Timestamp vem do formatter do logging. JSON linha-a-linha: `docker logs`
mostra direto e qualquer coletor (Loki, Vector, CloudWatch) parseia sem
configuração.

Alternativas rejeitadas: tabela `audit_events` no SQLite (esquema +
purga + concorrência para um consumidor que ainda não existe — stdout primeiro,
persistência quando houver caso de uso); biblioteca structlog (dependência
para formatar o que `json.dumps` resolve).

### D2 — Nomes de evento fixos, emitidos no ponto da decisão

Catálogo kebab-case estável (contrato para quem consome): `auth.login`,
`auth.login.throttled`, `auth.logout`, `admin.user.created`,
`admin.user.disabled`, `admin.group.changed`, `admin.grant.revoked`,
`admin.image.changed`, `admin.document.changed`, `admin.mcp.changed`,
`admin.skill.changed`, `instance.created`, `instance.stopped`,
`instance.deleted`, `instance.failed`. Emissão **na rota/serviço que decide**
(não em middleware): cada ponto conhece ator/alvo corretos e o
`request.client.host` — disponível com IP real desde a change `harden-login`
(uvicorn proxy-headers em produção). Login emite também o desfecho
(`success`/`failure`) e, no fracasso, só o e-mail tentado — nunca distinguir
no *registro* os motivos internos (inexistente/desabilitada/senha) seria
perder informação perícial; o corpo da resposta HTTP continua uniforme
(anti-enumeração vale para o atacante externo, não para o operador do log).

### D3 — IP sempre que houver request; ator sempre que houver sessão

Rotas autenticadas têm ambos (sessão → ator; request → IP). Eventos de fundo
(provisionamento que falha no reaper, reconciliação) emitem sem IP e com
ator do sistema omitido — `actor_id` ausente já sinaliza evento interno.
`instance.failed` carrega `detail` com a mensagem de erro do runtime
(truncada), que hoje já vai para `error_message` visível ao dono — nada novo
é exposto.

### D4 — Segredos fora por construção

O emissor só aceita campos explícitos (sem `**kwargs` cegos capturando
objetos acidentais), e os pontos de emissão passam apenas os campos do
catálogo. Teste dedicado (capLogFixture) afirma que senhas/tokens/valores de
env MCP nunca aparecem nas linhas emitidas pelas rotas cobertas.

## Risks / Trade-offs

- [stdout não é armazenamento durável] → aceito por design: é a interface
  com o coletor do operador; a change registra o formato no SECURITY.md para
  estabilizar o contrato.
- [Volume: eventos de login sob ataque de força bruta] → um evento por
  tentativa é exatamente o sinal desejado; o limitador (harden-login) corta o
  ritmo. Rota de piora: spray massivo enche o disco do daemon Docker —
  mitigação do operador (rotação de log do daemon), anotada na doc.
- [Emissão em rotas esquecidas] → cobertura por família de rota é tarefa
  com teste de asserção por categoria (login, admin, instância), não lista
  exaustiva por endpoint; a revisão do diff confere os pontos chamados no
  design.

## Migration Plan

Deploy único, efeito aditivo (linhas novas no log). Rollback: `git revert`
sem estado envolvido.
