---
title: Implantação manual
description: Ordem de subida da composição de produção passo a passo, o papel de cada serviço e a subida em desenvolvimento.
sidebar:
  order: 1
---

Esta página descreve a subida manual do portal em produção: os pré-requisitos, a ordem dos comandos, o que cada serviço da composição faz e como diagnosticar o plano de dados das sessões. O caminho rápido é o script [`install.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/install.sh), na raiz do repositório, que automatiza tudo o que está aqui (verificação de pré-requisitos, coleta da configuração, geração dos segredos e subida da composição) e é descrito em [Instalação](/getting-started/installation/). A versão manual serve para entender o que o script faz ou para executar passo a passo.

:::danger
O portal monta o socket do Docker, o que equivale a acesso de root no host. Leia [Superfície de confiança](/security/trust-surface/) antes de expor o portal além da sua própria máquina.
:::

## Pré-requisitos

- Docker Engine com o plugin Compose v2 (`docker compose version` precisa responder) e um usuário capaz de falar com o daemon (`docker info`).
- Um domínio público cujo DNS já aponte para o host. O Caddy solicita um certificado Let's Encrypt para esse domínio na primeira subida.
- Portas `80` e `443` do host livres e alcançáveis de fora. São as únicas portas que a composição publica.
- Espaço em disco e banda para o primeiro deploy: as imagens de desktop do catálogo somam vários GB.
- `python3` para gerar os segredos (opcional: `openssl` serve de alternativa, ver [Variáveis de ambiente](/operations/environment-variables/)).

## Ordem de subida em produção

Defina as seis variáveis obrigatórias e suba a composição a partir do diretório `deploy/`:

```bash
cd deploy
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="uma senha com pelo menos 12 caracteres"
export WCUI_SSH_KEY_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export WCUI_DATA_PLANE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export WCUI_POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d --build
```

:::caution
Os comandos acima geram segredos novos a cada execução. Em um deploy real, gere cada valor uma única vez e guarde-o em `deploy/.env` (modelo em [`deploy/.env.example`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/.env.example)), que o `docker compose` lê automaticamente e que o git ignora. Trocar `WCUI_SSH_KEY_ENCRYPTION_KEY` depois do primeiro uso impede descriptografar as chaves SSH já cifradas no banco, e trocar `WCUI_POSTGRES_PASSWORD` depois que o volume do banco foi inicializado faz o portal deixar de autenticar no PostgreSQL.
:::

A composição recusa subir se alguma variável obrigatória faltar: o `docker compose` falha cedo com uma mensagem clara, em vez de o portal quebrar na inicialização. A descrição de cada variável, obrigatória ou opcional, está em [Variáveis de ambiente](/operations/environment-variables/).

### O que acontece na subida

1. A composição cria a rede `wcui_net` e os volumes nomeados automaticamente.
2. O `postgres` inicia e passa a responder ao healthcheck (`pg_isready`).
3. O `portal` só inicia depois que o banco está saudável. Na própria inicialização ele aplica o schema e provisiona o primeiro administrador a partir de `WCUI_ADMIN_EMAIL` e `WCUI_ADMIN_PASSWORD` (contrato na spec [`user-management`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/user-management/spec.md)).
4. O `caddy` depende do `portal` já estar de pé antes de começar a aceitar tráfego externo.

O catálogo também é provisionado na inicialização do portal: os 5 agentes de código (construídos localmente) e as 4 entradas de desktop — Webtop XFCE, Ubuntu KDE, Alpine MATE e VS Code — começam a ser construídos e baixados em segundo plano. As imagens de desktop somam vários GB de disco e rede no primeiro deploy. Entradas que já existem no catálogo nunca são duplicadas nem sobrescritas pelo provisionamento: estado, limites editados, desabilitação e capa manual definidos pelo administrador prevalecem. Detalhes em [Imagens de agente](/architecture/agent-images/).

### Depois de subir

Entre com `WCUI_ADMIN_EMAIL` e `WCUI_ADMIN_PASSWORD`, registre as imagens adicionais que quiser no catálogo, crie grupos e usuários e conceda acesso. Para um usuário ver qualquer imagem, ela precisa estar concedida a um grupo do qual ele participe.

O download de cada imagem roda em segundo plano. Acompanhe o estado na aba Catálogo do painel administrativo antes de esperar que um usuário consiga iniciar uma instância dela.

Em seguida, execute o [Checklist pós-deploy](/operations/post-deploy-checklist/).

### Atualizando um deploy existente

:::caution
A subnet da `wcui_net` é fixada por IPAM na composição, e o Docker não aplica IPAM novo em uma rede já criada. Ao atualizar um deploy anterior a essa fixação, o `docker compose up -d` recria a rede, o que desconecta os containers de instância conectados a ela. Planeje uma janela de manutenção, como para qualquer atualização que recria rede. O portal reconcilia o estado das instâncias na própria inicialização.
:::

A produção nasce com o banco PostgreSQL vazio: não há migração automática a partir do SQLite usado por versões anteriores. Antes de atualizar um deploy que ainda usava SQLite, encerre as instâncias em execução. O volume `wcui_db` continua montado no portal, intacto, para permitir a [Reversão](/operations/rollback/). Antes de qualquer atualização que altere o schema, faça um [backup](/operations/backup-and-restore/).

## Serviços da composição

A composição de produção está em [`deploy/docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml) e define três serviços, todos na rede interna `wcui_net`.

| Serviço | Imagem | Porta no host | Papel |
|---|---|---|---|
| `caddy` | `caddy:2-alpine` | `80`, `443` | Termina TLS, serve de plano de dados das sessões e encaminha o restante ao portal |
| `portal` | construída do `Dockerfile` da raiz | nenhuma | API, front-end, autenticação, catálogo e ciclo de vida das instâncias |
| `postgres` | `postgres:17-alpine` | nenhuma | Persistência do portal |

### Caddy

O Caddy é o único serviço que publica portas. Ele obtém e renova o certificado Let's Encrypt para `WCUI_DOMAIN`, adiciona o cabeçalho HSTS (`Strict-Transport-Security: max-age=31536000`, sem `includeSubDomains` nem `preload` — cada deploy decide se quer ir além), remove o cabeçalho `Server` das respostas e responde `404` a qualquer requisição externa para `/internal/*`. O container tem nome fixo, `wcui-caddy`, porque o portal executa `caddy reload` nele ao publicar ou retirar rotas de sessão.

Tudo que não é rota de sessão é encaminhado para `portal:8000`, com tempos de leitura e escrita de 3600 segundos para não cortar conexões longas. WebSocket não exige diretiva especial: o `reverse_proxy` do Caddy repassa upgrades de conexão por padrão. A configuração está em [`deploy/Caddyfile`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/Caddyfile).

Volumes: `caddy_data` (certificados), `caddy_config` e `caddy_routes` (rotas de sessão, compartilhado com o portal).

### Portal

O portal é construído a partir do [`Dockerfile`](https://github.com/alanyoshida/webcontainerui/blob/main/Dockerfile) da raiz, que compila o front-end e o serve junto da API. Ele não publica porta: só é alcançado pelo Caddy, de dentro da `wcui_net`. O healthcheck consulta `http://localhost:8000/health` a cada 30 segundos.

O portal monta `/var/run/docker.sock` para criar os containers de instância, que entram na mesma `wcui_net` sem publicar porta alguma no host. O isolamento entre usuários depende dessa topologia, e não só da checagem de dono — ver [Camadas de isolamento](/security/isolation-layers/).

Volumes: `wcui_db` em `/data` (capas enviadas pelo administrador e o arquivo SQLite de versões anteriores) e `caddy_routes` em `/data/caddy-routes`.

### PostgreSQL

Em produção a persistência é o serviço `postgres`, na rede interna e sem porta publicada no host: só o portal o alcança. O portal recebe `WCUI_DATABASE_URL` montada pela composição a partir de `WCUI_POSTGRES_PASSWORD` (banco `wcui`, usuário `wcui`) e só inicia depois do healthcheck do banco, via `depends_on` com `condition: service_healthy`.

- Os dados ficam no volume nomeado `wcui_pg_data` e sobrevivem a `docker compose down` (sem `-v`).
- A produção nasce com banco vazio; não há migração automática do SQLite antigo.
- Desenvolvimento e testes seguem em SQLite (`WCUI_DB_PATH`), sem `WCUI_DATABASE_URL`.

Backup e restauração estão em [Backup e restauração](/operations/backup-and-restore/); o desenho da camada de persistência, em [Banco de dados](/architecture/database/).

## Plano de dados das sessões

O Caddy não é só terminação TLS: ele transporta `/i/{uuid}/` (HTTP e WebSocket) diretamente aos containers das instâncias, sem os frames passarem pelo processo do portal. Para cada instância viva, o portal escreve um snippet de rota no volume nomeado `caddy_routes` — montado no Caddy em `/etc/caddy/caddy-routes` e no portal em `/data/caddy-routes` — e recarrega o Caddy com `docker exec` no container `wcui-caddy`. O comando de recarga é fixo no código do portal.

Antes de encaminhar cada requisição, o Caddy consulta o portal em `/internal/data-plane/authorize` (`forward_auth`), que verifica sessão válida, dono e instância em execução. Só a resposta 2xx carrega a credencial interna da instância, copiada para a requisição encaminhada; o cliente nunca a vê. O endpoint exige o `WCUI_DATA_PLANE_SECRET` e não é exposto pela borda (o Caddy responde `404` a `/internal/*` vindo de fora).

O desenho completo está em [Plano de dados das sessões](/architecture/session-data-plane/) e o contrato formal na spec [`stream-data-plane`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md).

### Sintomas e diagnóstico

**Sessão presa em "carregando" com o portal de pé.** Confira as rotas publicadas:

```bash
docker exec wcui-caddy ls /etc/caddy/caddy-routes
```

O esperado é um arquivo por instância em estado `running`, mais o `000-placeholder.caddy` (que mantém o `import` do Caddyfile com pelo menos um arquivo).

**Rota publicada mas não aplicada.** O `reload` falhou. O log de auditoria do portal tem um evento `data_plane.reload` com o motivo:

```bash
docker compose logs portal | grep data_plane.reload
```

O Caddy mantém a última configuração válida, então nunca fica com uma configuração quebrada; a rota entra no próximo evento de ciclo de vida da instância. O formato dos eventos está em [Log de auditoria](/security/audit-log/).

**Publicação desligada.** `WCUI_CADDY_ROUTES_DIR` está vazio. Nesse modo o portal entrega as sessões pelo próprio caminho interno (o proxy in-process), que é o padrão em desenvolvimento e nos testes.

## Proxy TLS e cookie `Secure`

Atrás do Caddy, o portal só enxerga o esquema real da requisição (`https`) e o IP real do cliente se confiar nos cabeçalhos encaminhados (`X-Forwarded-Proto`, `X-Forwarded-For`). Sem isso, o cookie de sessão nasce sem a flag `Secure` e o limitador de login só enxerga o IP do próprio Caddy.

A composição de produção já liga esse comportamento: define `UVICORN_PROXY_HEADERS=true` e restringe a origem confiável à subnet da `wcui_net` (`10.213.0.0/24`, fixada no IPAM da composição) por meio de `UVICORN_FORWARDED_ALLOW_IPS`. As variáveis só precisam ser tocadas se você trocar a subnet da rede; nesse caso, altere o IPAM e `WCUI_FORWARDED_ALLOW_IPS` juntos. Ver [Variáveis de ambiente](/operations/environment-variables/).

A composição de desenvolvimento não define essas variáveis: sem proxy à frente, cabeçalhos encaminhados continuam ignorados (origem não confiável).

O contexto de segurança dessas medidas está em [Endurecimento do login](/security/login-hardening/).

## Cabeçalhos de segurança e documentação interativa

O portal adiciona a toda resposta própria os cabeçalhos abaixo:

| Cabeçalho | Valor |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `no-referrer` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Content-Security-Policy` | política restritiva com `default-src 'self'` |

A exceção é o caminho de sessão `/i/...`, cujo conteúdo vem do container do usuário e não deve receber a política do portal. O `style-src 'unsafe-inline'` da CSP é requisito do MUI/Emotion (estilos injetados inline); scripts, fontes e conexões são todos de origem própria. O `X-Frame-Options` é `SAMEORIGIN`, e não `DENY`, porque o próprio portal embute a sessão em um iframe.

A documentação interativa da API (`/docs`, `/redoc` e `/openapi.json`) fica desligada por padrão, para não entregar o mapa da API a anônimos. `WCUI_DOCS_ENABLED=true` a liga, o que é útil em desenvolvimento.

O contrato formal está na spec [`http-hardening`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md).

## Subida em desenvolvimento

A composição de desenvolvimento ([`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml)) não tem Caddy nem PostgreSQL: `http://localhost` já é um secure context, que é o que o cliente Selkies exige para o WebCodecs funcionar, então TLS não faz falta em desenvolvimento.

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

Essa composição sobe só o portal, com as seguintes diferenças em relação à produção:

- A porta `8000` é publicada apenas em `127.0.0.1`, nunca na LAN.
- O banco é SQLite em `/data/webcontainerui.db`, no volume `wcui_db_dev`.
- A rede das instâncias é `wcui_net_dev`.
- O administrador e a chave de cifra das identidades SSH são valores fixos e públicos, definidos no próprio arquivo. Nunca os reutilize em produção.
- O plano de dados externo fica desligado: o portal entrega as sessões pelo proxy in-process.

A imagem já inclui o front-end compilado, então a aplicação completa responde em `http://127.0.0.1:8000`. Para desenvolver o front-end com recarga automática, rode `npm run dev` dentro de `frontend/`: o proxy do Vite ([`frontend/vite.config.js`](https://github.com/alanyoshida/webcontainerui/blob/main/frontend/vite.config.js)) encaminha `/api`, `/i` e `/uploads` para o portal, fazendo o papel de origem única que em produção é o próprio FastAPI servindo o build do React.

O passo a passo para experimentar o portal localmente está em [Teste local](/getting-started/local-trial/); o fluxo de desenvolvimento e testes, em [Desenvolvimento](/reference/development/).
