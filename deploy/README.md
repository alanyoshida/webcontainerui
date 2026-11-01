# Implantação

Ver também [`SECURITY.md`](SECURITY.md) — leitura obrigatória antes de expor
o portal além da sua própria máquina.

Caminho rápido: `./install.sh` na raiz do repositório automatiza tudo nesta
seção (pré-requisitos, coleta de configuração, geração da chave de cifra e
subida da composição). O que segue é a versão manual, útil para entender o
que o script faz ou para rodar passo a passo.

## Ordem de subida (produção)

```bash
cd deploy
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="uma senha com pelo menos 12 caracteres"
docker compose up -d --build
```

A composição cria a rede `wcui_net` e o volume do banco automaticamente. O
`portal` aplica o schema e provisiona o primeiro administrador na própria
inicialização (ver `specs/user-management/spec.md`); o `caddy` depende do
`portal` já estar de pé antes de começar a aceitar tráfego externo.

O catálogo também é provisionado no startup: os 5 agentes de código (build)
e as 4 entradas de desktop — Webtop XFCE, Ubuntu KDE, Alpine MATE e VS Code
— começam a baixar em segundo plano. As imagens de desktop somam vários GB
de disco e rede no primeiro deploy. Entradas que já existem no catálogo
nunca são duplicadas nem sobrescritas pelo seed: estado, limites editados,
desabilitação e capa manual do administrador prevalecem. Para um usuário
ver qualquer imagem, conceda-a a um grupo do qual ele participe.

> **Atualizando um deploy existente**: a subnet da `wcui_net` é fixada por
> IPAM (ver variáveis abaixo), e o Docker não aplica IPAM novo em rede já
> criada — o `docker compose up -d` recria a rede, o que desconecta os
> containers de instância conectados a ela. Planeje janela de manutenção,
> como para qualquer atualização que recria rede; o portal reconcilia o
> estado das instâncias no próprio start.

Depois de subir, entre com `WCUI_ADMIN_EMAIL`/`WCUI_ADMIN_PASSWORD`, registre
as imagens do catálogo, crie grupos e usuários, e conceda acesso. O download
de cada imagem roda em segundo plano — acompanhe o estado na aba Catálogo do
painel administrativo antes de esperar que um usuário consiga iniciá-la.

### Checklist pós-deploy

Duas checagens de dois minutos que pegam as duas falhas silenciosas desta
área (change `harden-login`):

```bash
# 1. HSTS presente na borda (resposta do Caddy)
curl -sI https://$WCUI_DOMAIN | grep -i strict-transport-security

# 2. Cookie de sessão com Secure via HTTPS (fazer login e inspecionar o header)
curl -sD - -o /dev/null -X POST https://$WCUI_DOMAIN/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$WCUI_ADMIN_EMAIL\",\"password\":\"...\"}" | grep -i set-cookie
```

Se o `Set-Cookie` vier sem `Secure`, o `UVICORN_FORWARDED_ALLOW_IPS` não está
casando com a subnet real da `wcui_net` — confira com
`docker network inspect wcui_net` (o IPAM da composição é a fonte da verdade).

## Variáveis de ambiente

As três abaixo são obrigatórias; a composição recusa subir sem elas
(`docker compose` falha cedo com uma mensagem clara em vez de o portal
quebrar na inicialização).

| Variável | Uso |
|---|---|
| `WCUI_DOMAIN` | Domínio público; o Caddy obtém certificado Let's Encrypt para ele |
| `WCUI_ADMIN_EMAIL` | E-mail do primeiro administrador |
| `WCUI_ADMIN_PASSWORD` | Senha inicial dele (mínimo 12 caracteres) |

### Proxy TLS e cookie `Secure`

Atrás do Caddy, o portal só vê o esquema real da requisição (`https`) e o IP
real do cliente se confiar nos cabeçalhos encaminhados — sem isso, o cookie
de sessão nasce sem a flag `Secure` e o limitador de login só enxerga o IP
do próprio Caddy. A composição de produção já liga isso; as variáveis só
precisam ser tocadas se você trocar a subnet da rede:

| Variável | Padrão | Uso |
|---|---|---|
| `WCUI_FORWARDED_ALLOW_IPS` | `10.213.0.0/24` | Subnet confiável (a da `wcui_net` no IPAM) aceita falar `X-Forwarded-*`; alimenta o uvicorn via `UVICORN_FORWARDED_ALLOW_IPS` |
| `UVICORN_PROXY_HEADERS` | `true` (composição) | Liga o `ProxyHeadersMiddleware` do uvicorn |

O compose de desenvolvimento não define essas variáveis: sem proxy à frente,
cabeçalhos encaminhados seguem sendo ignorados (origem não confiável).

### Cabeçalhos de segurança e documentação interativa

O portal adiciona a toda resposta própria (`X-Content-Type-Options`,
`Referrer-Policy`, `X-Frame-Options: SAMEORIGIN` e uma Content-Security-Policy
restritiva com `default-src 'self'`) — exceto ao caminho de sessão `/i/...`,
cujo conteúdo vem do container do usuário e não deve receber a política do
portal. O `style-src 'unsafe-inline'` da CSP é requisito do MUI/Emotion
(estilos injetados inline); scripts, fontes e conexões são todos de origem
própria.

| Variável | Padrão | Uso |
|---|---|---|
| `WCUI_DOCS_ENABLED` | `false` | Liga `/docs`, `/redoc` e `/openapi.json` (desligados por padrão para não entregar o mapa da API a anônimos; útil em desenvolvimento) |

### Limitação de tentativas de login

O portal limita tentativas de login com falha por conta (e-mail) e por
origem (IP), com recusa temporária (`429` + `Retry-After`) — estado em
memória, zerado por restart (janelas curtas; ver
`backend/app/services/login_throttle.py`):

| Variável | Padrão | Uso |
|---|---|---|
| `WCUI_LOGIN_MAX_FAILURES` | `10` | Falhas que disparam a recusa, por chave, dentro da janela |
| `WCUI_LOGIN_WINDOW_SECONDS` | `300` | Janela deslizante de contagem |
| `WCUI_LOGIN_LOCK_SECONDS` | `300` | Duração da recusa depois do limiar |

As demais têm padrão razoável e só precisam ser tocadas para calibração —
ver `app/config.py` no backend para a lista completa (limite de
inatividade, limites de recurso padrão por imagem, PUID/PGID/timezone dos
containers).

## Desenvolvimento

Sem Caddy: `http://localhost` já é secure context, que é o que o cliente
Selkies exige para WebCodecs funcionar — TLS não faz falta em dev.

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

O front-end roda fora dessa composição, com `npm run dev` dentro de
`frontend/`; o proxy do Vite (`frontend/vite.config.js`) encaminha `/api` e
`/i` para o portal, fazendo o papel de origem única que em produção é o
próprio FastAPI servindo o build do React.

## Reversão

Os volumes `wcui_db` (ou `wcui_db_dev`) e o volume Docker de cada desktop de
usuário são nomeados e sobrevivem a `docker compose down`. Derrubar a
composição não apaga nada.

**Antes de aplicar qualquer migração de schema**, copie o arquivo SQLite —
é um único arquivo, então a cópia é trivial e a reversão é só restaurá-lo:

```bash
docker compose cp portal:/data/webcontainerui.db ./webcontainerui.db.backup
```

Para reverter uma migração já aplicada, pare o portal, restaure o backup no
volume e suba de novo:

```bash
docker compose stop portal
docker compose cp ./webcontainerui.db.backup portal:/data/webcontainerui.db
docker compose up -d portal
```

## Limitações desta verificação

Este ambiente de desenvolvimento não tem acesso ao daemon Docker (erro de
permissão no socket). O que foi possível validar aqui:

- `docker compose config` em ambas as composições (sintaxe e interpolação
  de variáveis corretas, sem contato com o daemon).
- `caddy validate --config Caddyfile` (binário oficial baixado só para
  esta checagem): `Valid configuration`.
- O `Dockerfile` foi revisado por inspeção — a etapa de build do front-end,
  a instalação do pacote Python e a cópia do build para
  `app/config.py:frontend_dist` foram conferidas manualmente, mas
  `docker build` em si não rodou neste ambiente.

Rode isto num ambiente com Docker disponível antes do primeiro deploy real:

```bash
docker build -t webcontainerui -f Dockerfile .
```
