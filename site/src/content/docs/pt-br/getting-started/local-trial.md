---
title: Teste local
description: Como subir o portal na própria máquina com um comando, sem domínio, sem TLS e sem Caddy.
sidebar:
  order: 2
---

A composição de desenvolvimento sobe o portal inteiro na própria máquina, sem domínio, sem TLS e sem Caddy. É o caminho mais curto para avaliar o produto antes de uma instalação de produção.

## Pré-requisitos

- Docker com o plugin Docker Compose v2.
- Um clone do repositório.

Não é preciso ter Node nem Python instalados: a imagem é construída a partir do [`Dockerfile`](https://github.com/alanyoshida/webcontainerui/blob/main/Dockerfile) da raiz, que compila o front-end numa etapa própria.

## Subir

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

A aplicação completa (front-end e API) responde em `http://127.0.0.1:8000`. Entre com as credenciais de desenvolvimento:

| Campo | Valor |
|---|---|
| E-mail | `admin@local.test` |
| Senha | `senha-admin-dev-123456` |

:::caution
Essas credenciais e a chave de cifra das identidades SSH são fixas e públicas em [`deploy/docker-compose.dev.yml`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/docker-compose.dev.yml). Servem apenas para teste local. O portal só escuta em `127.0.0.1`, portanto não fica exposto à rede; não altere esse mapeamento de porta para publicá-lo.
:::

## O que acontece na primeira subida

No startup, o portal:

1. constrói a imagem base dos agentes e, em seguida, as cinco imagens de agente de código, aguardando cada build;
2. registra as quatro entradas de desktop padrão e dispara o download delas em segundo plano;
3. cadastra uma capa padrão para cada entrada do catálogo.

Por causa do primeiro passo, a primeira subida demora mais que as seguintes: o portal só passa a responder depois que os builds dos agentes terminam. Nas subidas seguintes, só é reconstruído o que mudou. As imagens de desktop têm vários gigabytes e aparecem com progresso de download no painel administrativo; só uma imagem pronta pode originar instância.

## O que a composição cria

| Recurso | Nome | Uso |
|---|---|---|
| Serviço | `portal` | FastAPI servindo front-end, API e o encaminhamento das sessões |
| Porta | `127.0.0.1:8000` | Único ponto de acesso, restrito ao host local |
| Rede | `wcui_net_dev` | Rede interna em que o portal e as instâncias ficam |
| Volume | `wcui_db_dev` | Banco SQLite em `/data/webcontainerui.db` e capas enviadas |

O socket do Docker (`/var/run/docker.sock`) é montado no portal, que o usa para criar os containers das instâncias. Vale também aqui o aviso de [Superfície de confiança](/security/trust-surface/).

## Por que funciona sem TLS

O cliente Selkies, usado pelas imagens webtop, exige um *secure context* para que a API WebCodecs funcione. `http://localhost` e `http://127.0.0.1` já são tratados pelo navegador como secure context, por isso TLS não faz falta neste cenário. Em qualquer outro endereço é necessário HTTPS, que a [instalação de produção](/getting-started/installation/) resolve com o Caddy.

Sem Caddy, quem entrega as sessões é o próprio processo do portal, pelo proxy in-process descrito em [Plano de dados das sessões](/architecture/session-data-plane/).

## Derrubar

Para derrubar preservando o banco de dados:

```bash
cd deploy && docker compose -f docker-compose.dev.yml down
```

Para apagar também o volume do banco:

```bash
cd deploy && docker compose -f docker-compose.dev.yml down -v
```

:::note
Os containers das instâncias e os volumes de arquivos dos usuários são criados pelo portal diretamente no Docker, fora da composição. O `down` não os remove; exclua as instâncias pelo portal antes de derrubar, ou remova-os manualmente depois.
:::

## Próximos passos

Para desenvolver o front-end com hot-reload e rodar as suítes de teste, veja [Desenvolvimento](/reference/development/).
