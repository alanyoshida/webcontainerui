---
title: Endurecimento do login
description: Como o portal protege o login e a sessão — cabeçalhos encaminhados, limitador de tentativas, hash de senha, cookie e cabeçalhos HTTP — e os trade-offs assumidos.
sidebar:
  order: 3
---

O login é a porta de entrada para um shell com root dentro da rede de containers (ver [Superfície de confiança](/security/trust-surface/)). Esta página descreve os controles em torno dele: em quem o portal confia para saber o esquema e o IP da requisição, como as tentativas com falha são limitadas, como senha e sessão são guardadas e quais cabeçalhos de segurança as respostas carregam. Cada controle vem acompanhado do que ele deixa de fora.

## Cabeçalhos encaminhados e allowlist de subnet

Em produção o Caddy termina TLS e fala HTTP com o portal pela rede interna. Para saber que o cliente usou HTTPS e qual é o IP real dele, o portal depende de `X-Forwarded-Proto` e `X-Forwarded-For`. Sem isso o portal sempre se veria como `http` — e o cookie de sessão nasceria sem `Secure` — e o limitador de login só enxergaria o IP do Caddy.

O portal só honra esses cabeçalhos quando vêm de IPs na allowlist `UVICORN_FORWARDED_ALLOW_IPS`, casada com a subnet fixa da `wcui_net` no IPAM da composição — não `*`:

```yaml
# deploy/docker-compose.yml (trecho)
services:
  portal:
    environment:
      UVICORN_PROXY_HEADERS: "true"
      UVICORN_FORWARDED_ALLOW_IPS: ${WCUI_FORWARDED_ALLOW_IPS:-10.213.0.0/24}

networks:
  wcui_net:
    name: wcui_net
    ipam:
      config:
        - subnet: 10.213.0.0/24
```

Em produção o efeito prático de `*` seria próximo (toda conexão chega pela rede interna), mas a subnet explícita não estende confiança a portas ou origens futuras.

:::caution[A allowlist precisa casar com a subnet real]
Se você mudar a subnet da `wcui_net`, ajuste `WCUI_FORWARDED_ALLOW_IPS` junto. Quando as duas divergem, a falha é silenciosa: o login funciona, mas o cookie sai sem `Secure`. O [Checklist pós-deploy](/operations/post-deploy-checklist/) tem a verificação de dois minutos que pega esse caso.
:::

### O que um falsificador dentro da subnet consegue

Os containers de instância estão na mesma subnet, portanto dentro da allowlist. Um usuário, de dentro do próprio container, pode falar direto com o portal em `portal:8000` e forjar os cabeçalhos. O que ele ganha com isso:

- Anunciar `X-Forwarded-Proto: https`: o único efeito é o cookie ganhar `Secure` — inócuo.
- Rotacionar `X-Forwarded-For`: bifurca o contador **por IP** do limitador de login, e faz o IP forjado aparecer no campo `ip` da [trilha de eventos](/security/audit-log/).

Por isso a linha principal da limitação é o bucket **por conta** (e-mail normalizado), que não depende de cabeçalho; o bucket por IP é best-effort atrás de proxy. E por isso o campo `ip` da trilha deve ser lido como "o que o proxy confiável informou", não como prova de origem quando a requisição pode ter partido de dentro da rede interna.

### HSTS

A borda envia `Strict-Transport-Security: max-age=31536000`. Com o cookie marcado `Secure`, isso elimina o downgrade para HTTP como vetor de roubo do cookie por um atacante na rede. A diretiva não inclui `includeSubDomains` nem `preload`: o domínio pode hospedar outros serviços, e HSTS agressivo é difícil de reverter. Cada implantação decide se quer ir além, editando o `Caddyfile`.

Em desenvolvimento não há Caddy nem TLS: o portal responde em `http://127.0.0.1:8000`, o cookie sai sem `Secure` e não há HSTS. Isso é esperado e é um dos motivos pelos quais a composição de desenvolvimento só publica a porta em `127.0.0.1`.

## Limitador de tentativas de login

Tentativas de login com falha são contadas em janela deslizante, em duas chaves independentes:

- **por conta** — o e-mail normalizado (sem espaços nas pontas, em minúsculas), para que variações de caixa não bifurquem o contador;
- **por IP** — a origem do cliente como o portal a enxerga.

Excedido o limiar em qualquer das duas chaves, o portal responde `429` com `Retry-After` a toda nova tentativa naquela chave, pelo período de recusa.

| Variável | Padrão | Significado |
|---|---|---|
| `WCUI_LOGIN_MAX_FAILURES` | `10` | Falhas na janela que disparam a recusa |
| `WCUI_LOGIN_WINDOW_SECONDS` | `300` | Tamanho da janela deslizante |
| `WCUI_LOGIN_LOCK_SECONDS` | `300` | Duração da recusa |

Detalhes do comportamento:

- A consulta ao limitador acontece **antes** de qualquer acesso ao banco ou cálculo de Argon2. A recusa é idêntica para conta existente e inexistente (não vira oráculo de enumeração) e poupa a CPU do hash, que seria um vetor de exaustão.
- A tentativa que atinge o limiar ainda é processada; a seguinte encontra a recusa.
- Login bem-sucedido zera apenas a chave da conta. A chave do IP permanece, para conter a tentativa de uma mesma senha contra várias contas a partir de um mesmo endereço.
- Vencida a recusa, a chave recomeça do zero.
- Tentativas contra conta desabilitada também contam como falha.
- Cada recusa gera um evento `auth.login.throttled` na [trilha de eventos](/security/audit-log/).

### Trade-off do limitador por conta

Excedido o limiar de falhas, a recusa (`429`) vale para qualquer tentativa durante a janela — **inclusive com a senha correta**: verificar a senha sob recusa viraria oráculo.

:::caution[Negação de serviço temporária é uma consequência assumida]
Um atacante pode manter a conta de uma vítima "trancada" renovando falhas — basta conhecer o e-mail. A mitigação é a recusa ser curta e configurável (`WCUI_LOGIN_LOCK_SECONDS`, padrão 300s), nunca permanente. É o mesmo trade-off de qualquer limitador por conta. Não há mecanismo de desbloqueio manual além de esperar a recusa vencer ou reiniciar o portal.
:::

### Limites do limitador

- **O estado vive em memória**, no processo do portal (que roda com um único worker). Reiniciar o portal zera as contagens e as recusas. Para janelas de cinco minutos isso é aceitável, mas significa que o limitador não é um registro durável de ataques — a trilha de eventos é.
- **Não há atraso crescente** nem bloqueio permanente. Um atacante paciente mantém cerca de dez tentativas a cada cinco minutos por conta, indefinidamente. Senhas fortes continuam sendo a defesa real contra força bruta lenta.
- **O bucket por IP é contornável** por quem controla o cabeçalho `X-Forwarded-For` de dentro da rede interna, como descrito acima.
- **Não há segundo fator** nem integração com provedor de identidade externo.

Especificação: [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md).

## Hash de senha

Senhas são armazenadas apenas como hash Argon2 (biblioteca `argon2-cffi`, parâmetros padrão do `PasswordHasher`), com sal por senha. Não há senha em texto plano nem cifragem reversível.

- Tamanho mínimo: 12 caracteres (`WCUI_PASSWORD_MIN_LENGTH`). O portal recusa subir se a senha do primeiro administrador for menor que isso. Não há outras regras de composição nem verificação contra listas de senhas vazadas.
- O primeiro administrador é provisionado a partir de `WCUI_ADMIN_EMAIL` e `WCUI_ADMIN_PASSWORD` apenas quando o banco está vazio; um segundo boot nunca sobrescreve a senha existente.

### Resposta indistinguível entre os casos de falha

E-mail inexistente, senha errada e conta desabilitada produzem a mesma resposta (`401`, mesma mensagem) e o mesmo custo de CPU:

- para e-mail inexistente, o portal verifica a senha contra um hash de referência, para que o Argon2 rode de qualquer forma;
- para conta desabilitada, a senha é verificada **antes** da checagem de desabilitação, de modo que o tempo de resposta não distingue esse caso dos demais.

Isso fecha a enumeração de contas por corpo e por tempo de resposta. Não fecha a enumeração por outros canais que o seu ambiente possa oferecer (convites por e-mail, por exemplo — o portal não envia nenhum).

## Tokens de sessão

- O token é gerado com `secrets.token_urlsafe(32)` — 256 bits de entropia.
- O banco guarda apenas o SHA-256 do token. O valor em claro existe só no momento da criação, para ir no cookie.
- Validade: 12 horas (`WCUI_SESSION_TTL_HOURS`). Não há renovação deslizante; vencido o prazo, é preciso entrar de novo.
- Logout revoga a sessão no servidor: o mesmo token deixa de autenticar na hora.
- Desabilitar uma conta revoga todas as sessões dela, e uma sessão de conta desabilitada é recusada mesmo que não tenha sido revogada.
- Sessões expiradas ou revogadas há mais que a carência (`WCUI_SESSION_PURGE_GRACE_HOURS`, padrão 24h) são removidas do banco pelo ciclo periódico do portal. Sessões ativas nunca são tocadas.

O cookie `wcui_session` é emitido com:

| Atributo | Valor | Efeito |
|---|---|---|
| `HttpOnly` | sempre | Scripts da página não leem o token |
| `SameSite` | `Lax` | Não acompanha requisições de terceiros que alterem estado |
| `Secure` | quando o portal se vê em HTTPS | Não trafega por HTTP puro |
| `Path` | `/` | Vale para o portal e para `/i/{uuid}/` |
| `Max-Age` | igual ao TTL da sessão | Expira junto com a sessão |

O que isso deixa de fora:

- **Não há limite de sessões simultâneas por usuário** nem tela para o usuário listar e encerrar as próprias sessões em outros dispositivos.
- **O cookie vale para `/i/{uuid}/`**, que serve conteúdo vindo do container do usuário na mesma origem do portal. `HttpOnly` impede a leitura do token, mas não impede que um script servido pelo container faça requisições autenticadas à API em nome do usuário. É o achado M3, aceito por decisão de projeto — ver [Auditorias](/security/audits/).
- **Proteção contra CSRF** depende de `SameSite=Lax` e da ausência de CORS permissivo; não há token anti-CSRF dedicado.

## Cabeçalhos de segurança HTTP

Toda resposta gerada pelo próprio portal — interface, API e uploads — carrega:

```http
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: SAMEORIGIN
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'
```

Decisões embutidas nessa política, e o que elas custam:

- `script-src 'self'`: nenhum script inline nem de terceiros. O front-end é totalmente servido pelo portal, sem CDN.
- `style-src 'unsafe-inline'`: exigência do MUI/Emotion, que injeta `<style>` em tempo de execução. Estilo inline injetado continua possível.
- `connect-src 'self' ws: wss:`: os esquemas `ws:` e `wss:` estão liberados para qualquer host, não só para a própria origem.
- `X-Frame-Options: SAMEORIGIN` e `frame-ancestors 'self'`, em vez de `DENY`: o próprio portal embute a sessão em um iframe da mesma origem. Sites de terceiros não conseguem emoldurar o portal.

:::caution[`/i/{uuid}/` não recebe esses cabeçalhos]
As respostas do caminho de sessão vêm do container do usuário e passam sem os cabeçalhos do portal: impor a política do portal quebraria as interfaces de desktop e terminal. Em produção essas respostas nem atravessam o portal — vão do container ao cliente pelo Caddy. Portanto o conteúdo embutido roda na origem do portal **sem CSP**. A CSP acima limita o que o front-end do portal carrega; ela não contém o que um container serve.
:::

Na borda, o Caddy remove o cabeçalho `Server` das respostas, para não anunciar a stack, e acrescenta HSTS. Em desenvolvimento, sem Caddy, `Server: uvicorn` continua aparecendo.

Especificação: [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md).

## Documentação interativa desligada

`/docs`, `/redoc` e `/openapi.json` ficam desligados por padrão e respondem `404`, inclusive quando o front-end está sendo servido pelo portal (os caminhos não caem no catch-all da aplicação de página única). Assim o mapa completo da API, incluindo as rotas administrativas, não é entregue a anônimos.

Para ligar em desenvolvimento:

```bash
export WCUI_DOCS_ENABLED=true
```

Não ligue em produção. As rotas continuariam protegidas por sessão e por papel, mas não há motivo para publicar o inventário delas. O endpoint interno do plano de dados nunca aparece no schema, com a documentação ligada ou não.

## Onde conferir no código

| Controle | Arquivo |
|---|---|
| Rota de login, ordem das checagens, cookie | `backend/app/api/auth.py` |
| Limitador | `backend/app/services/login_throttle.py` |
| Hash de senha | `backend/app/services/passwords.py` |
| Criação, resolução, revogação e purga de sessão | `backend/app/services/sessions.py` |
| Padrões configuráveis | `backend/app/config.py` |
| Cabeçalhos de segurança e documentação interativa | `backend/app/main.py` |
| Allowlist de cabeçalhos encaminhados e subnet | `deploy/docker-compose.yml` |
| HSTS e remoção de `Server` | `deploy/Caddyfile` |

A lista completa de variáveis está em [Variáveis de ambiente](/operations/environment-variables/).
