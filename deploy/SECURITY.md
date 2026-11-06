# Superfície de confiança do portal

## Por que `socket-proxy` não mitiga este caso

Uma mitigação comum para "não dar o socket do Docker direto a um processo" é
colocar um `socket-proxy` na frente, filtrando quais chamadas da API do Docker
passam. Isso **não funciona aqui**.

O portal precisa criar containers (`POST /containers/create`) para atender ao
requisito central do produto. Qualquer permissão que permita criar container
também permite criar um container com um bind mount de `/` do host:

```
  socket-proxy com CONTAINERS=1, POST=1
        |
        +--> permite container create
                 |
                 +--> permite -v /:/host
                          |
                          +--> root no host de novo
```

Ou seja: a superfície mínima necessária para o portal funcionar é exatamente a
superfície que, nas mãos de quem a controla, equivale a root no host. Um
`socket-proxy` que restringisse o suficiente para bloquear isso também
bloquearia a criação de containers de desktop, que é a função do sistema.

## O que isso significa na prática

**O processo do portal é um componente de confiança do plano de controle.**
Não um sandbox, não um processo isolado do host — um processo que, por
necessidade de produto, tem autoridade equivalente a root no host via Docker.

Isso implica:

- Nenhum código de usuário roda dentro do processo do portal. Ele só orquestra
  containers; não interpreta nem executa nada que venha do usuário final.
- A imagem do portal é mínima, para reduzir a superfície de uma eventual
  vulnerabilidade na própria aplicação.
- O arquivo SQLite do portal é tratado como tão sensível quanto o socket do
  Docker — quem lê um, efetivamente alcança o outro.
- Backups, acesso ao host e rotação de credenciais do ambiente onde o portal
  roda devem seguir a mesma política de um host que hospeda segredos de
  administrador, não a de uma aplicação de usuário comum.

Ver `design.md` da change `webtop-portal`, seção de riscos, para a árvore de
decisão completa e as demais mitigações do projeto (isolamento de rede dos
containers de desktop, credencial interna por instância, desligamento dos
links de compartilhamento do Selkies).

## Plano de dados das sessões (change `external-stream-proxy`)

Em produção o Caddy transporta `/i/{uuid}/` diretamente aos containers das
instâncias; o portal deixa de reenviar os frames e passa a decidir apenas a
autorização. Isso muda a superfície de duas formas:

- **O Caddy alcança os containers das instâncias.** Ele já vivia na
  `wcui_net`; agora o reverse_proxy usa esse acesso. Os containers continuam
  sem porta publicada no host — o isolamento entre usuários segue topológico.
- **Segredo compartilhado.** O `forward_auth` apresenta
  `WCUI_DATA_PLANE_SECRET` ao endpoint interno de autorização. Sem o segredo
  correto, o endpoint responde `401` e nada é encaminhado (falha fechada,
  inclusive com o portal fora do ar). O endpoint não é exposto pela borda: o
  Caddy responde `404` a `/internal/*` vindo de fora.
- **Rotas são configuração, não código.** O portal escreve um snippet por
  instância em `caddy_routes` com id e nome de container validados (apenas
  `[A-Za-z0-9_.-]`); o comando de reload é fixo no portal, nunca derivado de
  input de usuário.

O portal continua sendo o único componente que decide autorização; o Caddy
só transporta o que o portal aprovou.

## Cabeçalhos encaminhados e allowlist de subnet (change `harden-login`)

O portal só honra `X-Forwarded-Proto`/`X-Forwarded-For` vindos de IPs na
allowlist `UVICORN_FORWARDED_ALLOW_IPS`, casada com a subnet fixa da
`wcui_net` no IPAM da composição — não `*`. Em produção o efeito prático
seria próximo (toda conexão chega pela rede interna), mas a subnet explícita
não estende confiança a portas ou origens futuras.

O que um falsificador de cabeçalhos **dentro** da subnet consegue (os
containers de instância estão lá): anunciar `X-Forwarded-Proto: https`, cujo
único efeito é o cookie ganhar `Secure` (inócuo); e rotacionar
`X-Forwarded-For` para bifurcar o contador por IP do limitador de login. Por
isso a linha principal da limitação é o bucket **por conta** (e-mail
normalizado), que não depende de cabeçalho; o bucket por IP é best-effort
atrás de proxy.

## Trade-off do limitador de login por conta

Excedido o limiar de falhas, a recusa (`429`) vale para qualquer tentativa
durante a janela — inclusive com a senha correta: verificar a senha sob
recusa viraria oráculo. Consequência assumida: um atacante pode manter a
conta de uma vítima "trancada" renovando falhas (negação de serviço
temporária). A mitigação é a recusa ser curta e configurável
(`WCUI_LOGIN_LOCK_SECONDS`, padrão 300s), nunca permanente — o mesmo
trade-off de qualquer limitador por conta. Achados M1/M2 do relatório de
pentest de 2026-11-01 (`docs/relatorio-pentest-2026-11-01.md`).

## Trilha de eventos de segurança (change `security-audit-log`)

Um evento = uma linha JSON na saída padrão do portal, capturável com
`docker logs deploy-portal-1-1` (ou o coletor do operador: Loki, Vector,
CloudWatch). Formato e campos:

```json
{"event": "auth.login", "actor_id": 1, "actor_email": "a@x.test", "ip": "203.0.113.9", "outcome": "success"}
```

- Campos: `actor_id`/`actor_email` (via sessão; ausentes em eventos internos
  do sistema), `ip` (IP real do cliente atrás de proxy confiável — ver
  allowlist `UVICORN_FORWARDED_ALLOW_IPS`), `target` (objeto da ação),
  `outcome` (`success` | `failure` | `denied`) e `detail` curto.
- Catálogo de nomes: `auth.login`/`auth.login.throttled`/`auth.logout`,
  `admin.user.created|disabled`, `admin.group.changed`,
  `admin.grant.changed|revoked`, `admin.image.changed`,
  `admin.document.changed`, `admin.mcp.changed`, `admin.skill.changed`,
  `instance.created|updated|stopped|deleted|failed`.
- Nenhum evento carrega segredo: senha, token de sessão, credencial interna
  de instância, chave privada e valores de env/headers de MCP nunca passam
  pelo emissor (`backend/app/services/audit_log.py`).
- Retenção/rotação: responsabilidade do driver de log do Docker
  (`json-file` com `max-size`/`max-file`) ou do coletor externo — o portal
  só escreve no stdout.
