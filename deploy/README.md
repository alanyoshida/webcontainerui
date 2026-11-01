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

Depois de subir, entre com `WCUI_ADMIN_EMAIL`/`WCUI_ADMIN_PASSWORD`, registre
as imagens do catálogo, crie grupos e usuários, e conceda acesso. O download
de cada imagem roda em segundo plano — acompanhe o estado na aba Catálogo do
painel administrativo antes de esperar que um usuário consiga iniciá-la.

## Variáveis de ambiente

As três abaixo são obrigatórias; a composição recusa subir sem elas
(`docker compose` falha cedo com uma mensagem clara em vez de o portal
quebrar na inicialização).

| Variável | Uso |
|---|---|
| `WCUI_DOMAIN` | Domínio público; o Caddy obtém certificado Let's Encrypt para ele |
| `WCUI_ADMIN_EMAIL` | E-mail do primeiro administrador |
| `WCUI_ADMIN_PASSWORD` | Senha inicial dele (mínimo 12 caracteres) |

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
