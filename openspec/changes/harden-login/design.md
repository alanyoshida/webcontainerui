# Design

## Context

O login hoje (ver `backend/app/api/auth.py`) responde 401 uniforme para credencial
errada — já com hash dummy contra enumeração por timing de contas ativas — mas
sem qualquer limitação de tentativas; e o cookie de sessão usa
`secure=request.url.scheme == "https"`, que atrás do Caddy nunca é `"https"`
porque o uvicorn roda sem `--proxy-headers` (Dockerfile: CMD fixo). O portal
roda com **um worker** (restrição documentada em AGENTS.md), o que torna estado
em memória viável para limitação — mesmo argumento já usado pelo
`ActivityTracker`. Em produção o portal não publica porta: toda conexão chega
pela `wcui_net` (Caddy ou, indesejadamente, containers de instância).

## Goals / Non-Goals

**Goals:**

- Cookie de sessão com `Secure` de fato aplicado atrás do Caddy, sem mudar a
  lógica do app (o requisito da spec `auth` já está correto; o que falta é o
  portal enxergar o esquema real).
- IP real do cliente disponível ao app quando servido por proxy confiável
  (insumo do limitador).
- Limitação de tentativas de login com falha, por conta e por origem, sem
  dependência nova e sem escrita extra em disco.

**Non-Goals:**

- Origem separada para o proxy de sessão (achado M3) — change própria.
- Rate limit global da API (só o login; as demais rotas exigem sessão e não
  foram apontadas).
- Lockout persistente em banco, CAPTCHA, ou limitação distribuída
  multi-worker.
- Correção do timing de contas desabilitadas (achado B1) — é adjacente ao
  código tocado, mas fora do escopo decidido.

## Decisions

### D1 — Confiança em proxy encaminhado no nível do uvicorn, não no app

Ativar `UVICORN_PROXY_HEADERS=true` + `UVICORN_FORWARDED_ALLOW_IPS=<subnet>`
(env do contêiner; o CMD do Dockerfile não muda). O `ProxyHeadersMiddleware`
do uvicorn resolve duas coisas de uma vez: `request.url.scheme` (cookie
`Secure`) e `request.client.host` (IP real para o limitador).
Alternativa rejeitada: ler `X-Forwarded-Proto`/`X-Forwarded-For` no próprio
app sob um setting `WCUI_TRUSTED_PROXY` — duplicaria middleware existente e
checagem de allowlist à mão, com mais superfície para erro. Default do uvicorn
(permitir só 127.0.0.1) mantém dev e qualquer deploy sem as variáveis exatamente
como hoje: sem confiar em nada.

### D2 — Allowlist por subnet fixada com IPAM no compose de produção

`wcui_net` ganha subnet explícita (ex. `10.213.0.0/24`) e
`UVICORN_FORWARDED_ALLOW_IPS` recebe essa subnet. `*` foi considerado e
rejeitado: em produção o efeito prático seria próximo (toda conexão vem da
`wcui_net`), mas a subnet explícita documenta a intenção e não estende confiança
a eventuais portas/origens futuras. O dev compose permanece **sem** as
variáveis: não há proxy à frente e o risco de falsificar os cabeçalhos é nulo.

### D3 — Limitador em memória, janela deslizante, sem dependência nova

Novo serviço (`backend/app/services/login_throttle.py`): dois mapas
`{chave: deque[timestamps]}` — por e-mail normalizado (minúsculas) e por IP do
cliente — mais um mapa `{chave: liberado_em}` para quem excedeu. Relógio
injetável (`now: Callable[[], float] = time.monotonic`) para testes sem sleep.
Memória limitada: entradas expiradas são podadas a cada verificação (custo por
chave é `O(falhas na janela)`); número de chaves é limitado pela atividade real
de login na janela — despreocupante para o perfil do portal.
Alternativas rejeitadas: `slowapi`/`limits` (dependência nova; o modo útil
delas para multi-worker, com Redis, não se aplica a um worker); colunas
`failed_attempts`/`locked_until` em `users` (migração + escrita em disco por
falha + lockout persistente, que facilita DoS de conta por atacante).

### D4 — Semântica da recusa: antes de qualquer consulta, uniforme, temporária

A rota de login consulta o limitador **antes** de tocar o banco ou o Argon2:
sobre o limiar, responde `429` com `Retry-After` (segundos até a liberação mais
próxima entre conta e IP) — corpo genérico, idêntico para conta existente ou
não (preserva o anti-enumeração existente e ainda poupa CPU de Argon2, que é o
vetor de exaustão notado no relatório). Falha registra nos dois buckets;
sucesso limpa **apenas** o bucket da conta (o bucket por IP permanece, para
conter spraying de várias contas de uma origem). Durante a recusa, qualquer
tentativa é recusada — inclusive com a senha correta: sem isso, a verificação
vazaria se a senha está certa e a recusa viraria oráculo. Trade-off aceito:
atacante pode manter a conta de uma vítima "trancada" renovando falhas; a
mitigação é o período curto e configurável (default 300s) — DoS limitado,
contra o benefício de travar força bruta.

### D5 — Parâmetros como Settings existentes

`login_max_failures: int = 10`, `login_window_seconds: int = 300`,
`login_lock_seconds: int = 300` em `Settings` (env `WCUI_LOGIN_*`, `gt=0`) —
mesmo padrão dos demais campos; nada de nova infra de configuração.

### D6 — HSTS no Caddy, sem `includeSubdomains`/`preload`

`header Strict-Transport-Security "max-age=31536000"` no site do Caddyfile.
Fecha o downgrade HTTP como vetor de roubo do cookie (par do M1). Sem
`includeSubdomains`/`preload` por enquanto: o domínio pode receber outros
serviços/subdomínios e HSTS agressivo é difícil de reverter; cabe ao deploy
decidir depois.

### D7 — Como cada peça é verificada

- Limitador: testes unitários com relógio fake (podas, limites por bucket,
  liberação) + testes de rota no padrão existente (`TestClient`): N falhas →
  `429` com `Retry-After` na N+1 (inclusive com senha correta), e-mail
  inexistente idêntico, sucesso dentro do limite normal.
- Cookie `Secure` atrás de proxy: efeito do `ProxyHeadersMiddleware` não é
  observável pelo `TestClient` (ele fala ASGI direto, sem uvicorn). Verificação
  no arranjo real: com o dev compose + `UVICORN_FORWARDED_ALLOW_IPS` apontando
  para a subnet dev (a porta mapeada entra pelo gateway da rede, que está na
  subnet), `curl` com `X-Forwarded-Proto: https` deve produzir `Set-Cookie`
  com `Secure`. Tarefa de verificação manual documentada — mesmo espírito da
  seção "E2E e verificação manual" do AGENTS.md; a suíte `e2e` real com proxy
  TLS completo ficaria desproporcional ao risco.

## Risks / Trade-offs

- [Restart do portal zera o limitador] → aceito: janela e recusa são curtas e
  o Argon2 mantém cada tentativa custosa; persistência só valeria com lockout
  em banco (rejeitado em D3).
- [Container de instância na `wcui_net` falsifica `X-Forwarded-For` e rota o
  bucket por IP] → mitigação: o bucket por **conta** é a linha principal e não
  depende de cabeçalho; o por IP é best-effort atrás de proxy. Falsificar
  `X-Forwarded-Proto: https` só faz o cookie ganhar `Secure` (efeito nulo).
- [Atacante tranca a conta da vítima renovando falhas] → recusa curta e
  configurável (`WCUI_LOGIN_LOCK_SECONDS`); sem bloqueio permanente; mesma
  classe de trade-off de qualquer limitador por conta.
- [Subnet IPAM conflita com rede existente no host] → subnet escolhida fora
  das faixas padrão do Docker (`10.213.0.0/24`); se ainda conflitar, o
  `docker compose up` falha alto e explícito — rollback: remover o bloco IPAM.
- [Deploy esquece `UVICORN_FORWARDED_ALLOW_IPS` com `PROXY_HEADERS` ativo] →
  allowlist sem match volta ao comportamento atual (cookie sem `Secure`),
  silenciosamente → mitigação: checklist de verificação pós-deploy (curl do
  M1/D7) incluído nas tarefas e em `deploy/README.md`.

## Migration Plan

1. Merge do código (limiter + settings + testes) — sem efeito de comportamento
   até o deploy acionar as variáveis.
2. Deploy de produção: `docker compose up -d` com o compose novo. **Atenção**:
   fixar IPAM em rede existente exige recriá-la — o compose derruba e recria a
   `wcui_net`, e os containers de instância conectados a ela precisam ser
   religados (o portal já os reconcilia no start; janela de manutenção
   recomendada, igual a qualquer atualização que recria rede).
3. Verificação pós-deploy: `curl -I` no domínio (HSTS presente) e login via
   HTTPS confirmando `Set-Cookie: ...; Secure`.
4. Rollback: `git revert` + `docker compose up -d` — remover o bloco IPAM
   recria a rede sem subnet fixa; o limitador degrada para noop só se as
   variáveis `WCUI_LOGIN_*` forem removidas (defaults seguem ativos por padrão,
   o que é o desejado).
