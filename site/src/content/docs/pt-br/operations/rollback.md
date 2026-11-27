---
title: Reversão
description: O que sobrevive a uma derrubada da composição, como reverter banco, plano de dados e migrações de schema, e as limitações da verificação da implantação.
sidebar:
  order: 4
---

Esta página descreve como voltar atrás depois de uma atualização: o que é preservado quando a composição é derrubada, como reverter o banco de dados e o plano de dados das sessões, e como desfazer uma migração de schema. No final estão as limitações conhecidas da verificação dos artefatos de implantação.

## O que sobrevive a `docker compose down`

Derrubar a composição não apaga nada. Os volumes abaixo são nomeados e sobrevivem a `docker compose down`:

| Volume | Conteúdo |
|---|---|
| `wcui_pg_data` | Banco PostgreSQL de produção |
| `wcui_db` (produção) ou `wcui_db_dev` (desenvolvimento) | `/data` do portal: capas enviadas e o arquivo SQLite |
| `caddy_data`, `caddy_config` | Certificados e estado do Caddy |
| `caddy_routes` | Rotas de sessão publicadas pelo portal |
| um volume por desktop de usuário | Dados de cada usuário em cada imagem |

:::danger
`docker compose down -v` apaga os volumes declarados na composição, incluindo o banco. Não use `-v` em produção sem um backup verificado.
:::

## Banco de dados

O banco de produção não tem migração de dados a partir do SQLite: a instalação com PostgreSQL nasce nova. Os backups do PostgreSQL são o caminho de recuperação — ver [Backup e restauração](/operations/backup-and-restore/).

### Antes de uma migração de schema em produção

Antes de aplicar qualquer atualização que altere o schema, faça o backup lógico:

```bash
docker compose exec -T postgres pg_dump -U wcui wcui > wcui-$(date +%F).sql
```

Para reverter uma migração já aplicada, volte o código à versão anterior e restaure esse backup com o portal parado, conforme o procedimento de restauração.

### Voltar para a versão anterior, com SQLite

O arquivo SQLite no volume `wcui_db` nunca é tocado pela versão com PostgreSQL. Para voltar à versão anterior, volte à imagem (ou ao commit) anterior, ou remova da composição o serviço `postgres` e a variável `WCUI_DATABASE_URL` do portal. Sem essa variável, o portal volta a usar o SQLite de `WCUI_DB_PATH`.

Os dados criados no PostgreSQL depois da atualização não são levados de volta para o SQLite.

### Banco SQLite: cópia e restauração do arquivo

Onde o banco é SQLite — a composição de desenvolvimento ou um deploy de versão anterior ao PostgreSQL — o banco é um único arquivo, então a cópia é trivial e a reversão é só restaurá-lo. Antes de aplicar qualquer migração de schema, copie o arquivo:

```bash
docker compose cp portal:/data/webcontainerui.db ./webcontainerui.db.backup
```

Para reverter uma migração já aplicada, pare o portal, restaure o backup no volume e suba de novo:

```bash
docker compose stop portal
docker compose cp ./webcontainerui.db.backup portal:/data/webcontainerui.db
docker compose up -d portal
```

Na composição de desenvolvimento, acrescente `-f docker-compose.dev.yml` a cada comando.

:::note
O SQLite roda em modo WAL. Para uma cópia consistente, pare o portal antes de copiar o arquivo, ou copie também os arquivos `-wal` e `-shm` que estiverem ao lado dele.
:::

## Plano de dados das sessões

O plano de dados não guarda estado além dos snippets de rota no volume `caddy_routes`. Para voltar a entregar todas as sessões pelo portal, restaure o `Caddyfile` anterior (ou remova o volume e reinicie o Caddy). As instâncias e os volumes dos usuários não mudam.

O proxy de sessão in-process do portal continua registrado em produção, sombreado pelo roteamento da borda; é ele que passa a atender quando as rotas por instância deixam de existir no Caddy. Com `WCUI_CADDY_ROUTES_DIR` vazio, o portal também deixa de publicar rotas. Ver [Plano de dados das sessões](/architecture/session-data-plane/).

## Rede `wcui_net`

Reverter para uma composição com outra definição de rede recria a `wcui_net`, o que desconecta os containers de instância conectados a ela. Planeje a reversão com a mesma janela de manutenção da atualização; o portal reconcilia o estado das instâncias na própria inicialização.

## Limitações desta verificação

Os artefatos de implantação foram escritos em um ambiente de desenvolvimento sem acesso ao daemon Docker (erro de permissão no socket). O que foi possível validar nesse ambiente:

- `docker compose config` em ambas as composições: sintaxe e interpolação de variáveis corretas, sem contato com o daemon.
- `caddy validate --config Caddyfile`, com o binário oficial baixado só para essa checagem: `Valid configuration`.
- O `Dockerfile` foi revisado por inspeção. A etapa de build do front-end, a instalação do pacote Python e a cópia do build para o diretório apontado por `frontend_dist` em `app/config.py` foram conferidas manualmente, mas o `docker build` em si não rodou nesse ambiente.

Rode o build em um ambiente com Docker disponível antes do primeiro deploy real, a partir da raiz do repositório:

```bash
docker build -t webcontainerui -f Dockerfile .
```

Em seguida, execute o [Checklist pós-deploy](/operations/post-deploy-checklist/) no ambiente de destino.
