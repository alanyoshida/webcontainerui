---
title: Variáveis de ambiente
description: Referência de todas as variáveis de ambiente do portal e da composição de produção, com obrigatoriedade, padrão e efeito.
sidebar:
  order: 2
---

O portal lê a configuração do ambiente, com o prefixo `WCUI_`. Esta página lista todas as variáveis: as que a composição de produção exige, as que ela mesma define e as opcionais, que têm padrão razoável e só precisam ser tocadas para calibração. A fonte da verdade é [`backend/app/config.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/config.py) para o portal e [`deploy/docker-compose.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.yml) para a composição.

## Como as variáveis chegam ao portal

Há dois níveis, e a diferença importa ao alterar um valor:

- **Variáveis da composição.** O `docker compose` lê o ambiente do shell e o arquivo `deploy/.env` para interpolar o `docker-compose.yml`. As seis variáveis obrigatórias e `WCUI_FORWARDED_ALLOW_IPS` são desse tipo.
- **Variáveis do container do portal.** O portal só enxerga o que está no bloco `environment` do serviço `portal`. Uma variável opcional colocada apenas em `deploy/.env` **não** chega ao portal: para alterá-la em produção, acrescente-a também ao bloco `environment` do serviço `portal` (por exemplo, `WCUI_IDLE_TIMEOUT_MINUTES: "60"`) e recrie o container com `docker compose up -d`.

Segredos ficam no ambiente, nunca no repositório. O `deploy/.env` é ignorado pelo git; use [`deploy/.env.example`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/.env.example) como modelo. O `install.sh` grava esse arquivo com permissão `600`.

## Obrigatórias em produção

A composição recusa subir sem estas seis variáveis: o `docker compose` falha cedo com uma mensagem clara, em vez de o portal quebrar na inicialização.

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_DOMAIN` | Sim (só na composição de produção) | — | Domínio público do portal. O Caddy obtém certificado Let's Encrypt para ele. Não é lida pelo portal. |
| `WCUI_ADMIN_EMAIL` | Sim | vazio | E-mail do primeiro administrador, provisionado na inicialização. |
| `WCUI_ADMIN_PASSWORD` | Sim | vazio | Senha inicial do primeiro administrador. Mínimo de 12 caracteres (`WCUI_PASSWORD_MIN_LENGTH`). |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | Sim (em qualquer ambiente) | — | Chave Fernet que cifra em repouso a chave privada SSH de cada usuário e os segredos (variáveis de ambiente e cabeçalhos) dos servidores MCP cadastrados. O portal não inicia sem ela nem com um valor que não seja uma chave Fernet válida. |
| `WCUI_DATA_PLANE_SECRET` | Sim | vazio | Segredo compartilhado entre o portal e o Caddy. O `forward_auth` o apresenta ao endpoint interno de autorização; sem ele, nenhuma sessão é aprovada. |
| `WCUI_POSTGRES_PASSWORD` | Sim (só na composição de produção) | — | Senha do PostgreSQL interno. A composição monta `WCUI_DATABASE_URL` a partir dela. Não é lida diretamente pelo portal. |

Fora da composição de produção, `WCUI_ADMIN_EMAIL` e `WCUI_ADMIN_PASSWORD` podem ficar ambos vazios, o que desativa o provisionamento do primeiro administrador. Informar apenas um dos dois é erro de configuração e impede a inicialização.

### Gerando a chave Fernet

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Sem o pacote `cryptography` instalado no host, os equivalentes abaixo produzem o mesmo formato (32 bytes aleatórios em base64 urlsafe) e são os que o `install.sh` usa:

```bash
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
# ou, sem python3:
openssl rand -base64 32 | tr '+/' '-_'
```

:::caution
Guarde `WCUI_SSH_KEY_ENCRYPTION_KEY` com segurança e fora do host. Perdê-la impede descriptografar as chaves SSH e os segredos de servidores MCP já cifrados no banco, e um backup do banco só é útil junto dela. A chave fixa que aparece em `docker-compose.dev.yml` é pública e serve apenas para desenvolvimento.
:::

### Gerando os segredos

`WCUI_DATA_PLANE_SECRET` e `WCUI_POSTGRES_PASSWORD` são gerados da mesma forma:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# ou, sem python3:
openssl rand -base64 32 | tr '+/' '-_' | tr -d '='
```

Gere cada valor uma única vez. A senha do PostgreSQL é gravada no volume `wcui_pg_data` na primeira inicialização do banco; alterar a variável depois não altera a senha já gravada.

## Banco de dados

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_DATABASE_URL` | Não (definida pela composição de produção) | ausente | URL do SQLAlchemy, no formato `postgresql+psycopg://usuario:senha@host:5432/banco`. Presente, o portal usa o banco apontado; ausente ou vazia, cai no SQLite de `WCUI_DB_PATH`. Em produção a composição a monta como `postgresql+psycopg://wcui:<WCUI_POSTGRES_PASSWORD>@postgres:5432/wcui`. |
| `WCUI_DB_PATH` | Não | `/data/webcontainerui.db` | Caminho do arquivo SQLite, usado em desenvolvimento e testes quando `WCUI_DATABASE_URL` não está definida. |

Ver [Banco de dados](/architecture/database/) e [Backup e restauração](/operations/backup-and-restore/).

## Proxy TLS e cookie `Secure`

Estas variáveis fazem o portal confiar nos cabeçalhos encaminhados pelo Caddy. Sem elas, o cookie de sessão nasce sem a flag `Secure` e o limitador de login só enxerga o IP do Caddy. A composição de produção já as define; a de desenvolvimento não, porque não há proxy à frente.

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_FORWARDED_ALLOW_IPS` | Não | `10.213.0.0/24` | Variável da composição: subnet confiável (a da `wcui_net` no IPAM) autorizada a enviar `X-Forwarded-*`. A composição a repassa ao portal como `UVICORN_FORWARDED_ALLOW_IPS`. Não é lida pelo portal com esse nome. |
| `UVICORN_FORWARDED_ALLOW_IPS` | Não (definida pela composição de produção) | valor de `WCUI_FORWARDED_ALLOW_IPS` | Lida pelo uvicorn: lista de origens das quais os cabeçalhos encaminhados são aceitos. |
| `UVICORN_PROXY_HEADERS` | Não (definida pela composição de produção) | `true` na composição | Lida pelo uvicorn: liga o `ProxyHeadersMiddleware`. |

Só altere `WCUI_FORWARDED_ALLOW_IPS` se trocar a subnet da `wcui_net`, e sempre junto do bloco `ipam` da composição. O IPAM é a fonte da verdade; confira com `docker network inspect wcui_net`.

## Plano de dados das sessões

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_DATA_PLANE_SECRET` | Sim em produção | vazio | Segredo exigido pelo endpoint interno `/internal/data-plane/authorize` (cabeçalho `X-Data-Plane-Secret`). Vazio desativa o endpoint, que é o caso de desenvolvimento e testes. A composição entrega o mesmo valor ao `caddy` e ao `portal`. |
| `WCUI_CADDY_ROUTES_DIR` | Não (definida pela composição de produção) | ausente; `/data/caddy-routes` na composição | Diretório compartilhado onde o portal publica as rotas de sessão que o Caddy importa. Ausente ou vazia, a publicação é desligada e o portal entrega as sessões pelo proxy in-process. |
| `WCUI_CADDY_CONTAINER` | Não (definida pela composição de produção) | `wcui-caddy` | Nome ou ID do container do Caddy em que o portal executa `caddy reload` depois de publicar rotas. Só é usada quando `WCUI_CADDY_ROUTES_DIR` está definida. |
| `WCUI_HEARTBEAT_MIN_SECONDS` | Não | `30` | Intervalo mínimo entre heartbeats de atividade aceitos por instância. A visão de sessão sinaliza enquanto está aberta e o portal não grava mais do que isso. |

Ver [Plano de dados das sessões](/architecture/session-data-plane/).

## Limitação de tentativas de login

O portal limita tentativas de login com falha por conta (e-mail) e por origem (IP), com recusa temporária (`429` com `Retry-After`). O estado fica em memória e é zerado quando o portal reinicia; as janelas são curtas. A implementação está em [`backend/app/services/login_throttle.py`](https://github.com/alanyoshida/webcontainerui/blob/main/backend/app/services/login_throttle.py).

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_LOGIN_MAX_FAILURES` | Não | `10` | Falhas que disparam a recusa, por chave (conta ou IP), dentro da janela. |
| `WCUI_LOGIN_WINDOW_SECONDS` | Não | `300` | Janela deslizante de contagem, em segundos. |
| `WCUI_LOGIN_LOCK_SECONDS` | Não | `300` | Duração da recusa depois de atingido o limiar, em segundos. |

Ver [Endurecimento do login](/security/login-hardening/).

## Autenticação e sessões do portal

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_SESSION_TTL_HOURS` | Não | `12` | Validade da sessão de login, em horas. |
| `WCUI_PASSWORD_MIN_LENGTH` | Não | `12` | Comprimento mínimo de senha. Vale também para `WCUI_ADMIN_PASSWORD`. |
| `WCUI_SESSION_PURGE_GRACE_HOURS` | Não | `24` | Carência da purga: uma sessão expirada ou revogada só é removida do banco depois deste período. Mínimo `1`. |

## Cabeçalhos de segurança e documentação interativa

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_DOCS_ENABLED` | Não | `false` | Liga `/docs`, `/redoc` e `/openapi.json`. Desligados por padrão para não entregar o mapa da API a anônimos; útil em desenvolvimento. |

## Instâncias: inatividade e limites de recurso

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_IDLE_TIMEOUT_MINUTES` | Não | `30` | Tempo de inatividade depois do qual uma instância é encerrada automaticamente. |
| `WCUI_REAPER_INTERVAL_SECONDS` | Não | `60` | Intervalo entre as varreduras que encerram instâncias inativas e purgam sessões. |
| `WCUI_ACTIVITY_DEBOUNCE_SECONDS` | Não | `30` | Intervalo mínimo entre gravações do registro de atividade de uma instância. |
| `WCUI_DEFAULT_SHM_SIZE_MB` | Não | `1024` | Tamanho padrão de `/dev/shm` por imagem, em MB. |
| `WCUI_DEFAULT_MEM_LIMIT_MB` | Não | `2048` | Limite padrão de memória por imagem, em MB. |
| `WCUI_DEFAULT_CPU_LIMIT` | Não | `2.0` | Limite padrão de CPU por imagem, em núcleos. |
| `WCUI_PUID` | Não | `1000` | Valor de `PUID` passado aos containers de instância: UID do usuário nas imagens de desktop e dono dos arquivos que o portal injeta nelas. Imagens de agente rodam como root. |
| `WCUI_PGID` | Não | `1000` | Valor de `PGID` passado aos containers de instância, com o mesmo papel para o GID. |
| `WCUI_TIMEZONE` | Não | `Etc/UTC` | Fuso horário (`TZ`) dos containers de instância. |

Os três limites de recurso valem para entradas do catálogo registradas sem limite explícito; cada entrada guarda os seus próprios valores, que o administrador pode editar por imagem.

## Docker: rede e nomes

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_DOCKER_NETWORK` | Não (definida pelas composições) | `wcui_net` | Rede Docker em que o portal conecta os containers de instância. A composição de desenvolvimento usa `wcui_net_dev`. |
| `WCUI_VOLUME_PREFIX` | Não | `wcui` | Prefixo do nome dos volumes de usuário (`<prefixo>-u<usuário>-i<imagem>`). |
| `WCUI_CONTAINER_PREFIX` | Não | `wcui` | Prefixo do nome dos containers de instância (`<prefixo>-<id>`). |

:::caution
Alterar `WCUI_VOLUME_PREFIX` ou `WCUI_CONTAINER_PREFIX` em um deploy já em uso faz o portal procurar volumes e containers por outros nomes: os dados existentes dos usuários deixam de ser encontrados. Defina esses valores apenas em uma instalação nova.
:::

## Arquivos e limites de conteúdo

| Variável | Obrigatória? | Padrão | Efeito |
|---|---|---|---|
| `WCUI_FRONTEND_DIST` | Não | `/app/frontend/dist` | Diretório do build do front-end servido em `/`. Se o diretório não existir, o portal sobe sem front-end. |
| `WCUI_UPLOADS_DIR` | Não | `/data/uploads/images` | Diretório das imagens de capa enviadas pelo administrador. Fica sob o volume montado em `/data`. |
| `WCUI_MAX_ICON_UPLOAD_MB` | Não | `5` | Tamanho máximo de uma imagem de capa enviada, em MB. |
| `WCUI_MAX_AGENTS_MD_BYTES` | Não | `262144` | Tamanho máximo do conteúdo de um documento AGENTS.md da biblioteca, em bytes. |

## Valores da composição de desenvolvimento

A composição [`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml) define cinco variáveis com valores fixos e não exige nenhuma do operador:

| Variável | Valor em desenvolvimento |
|---|---|
| `WCUI_DB_PATH` | `/data/webcontainerui.db` |
| `WCUI_DOCKER_NETWORK` | `wcui_net_dev` |
| `WCUI_ADMIN_EMAIL` | `admin@local.test` |
| `WCUI_ADMIN_PASSWORD` | valor fixo e público, definido no arquivo |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | chave fixa e pública, definida no arquivo |

Ela não define `WCUI_DATABASE_URL`, `WCUI_DATA_PLANE_SECRET`, `WCUI_CADDY_ROUTES_DIR` nem as variáveis `UVICORN_*`: em desenvolvimento o banco é SQLite, o plano de dados externo fica desligado e cabeçalhos encaminhados são ignorados.
