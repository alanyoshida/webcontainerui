---
title: Instalação
description: Instalação de produção guiada pelo install.sh, com os pré-requisitos e o que o script pergunta, gera e executa.
sidebar:
  order: 3
---

A instalação de produção é guiada pelo script [`install.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/install.sh), na raiz do repositório. Ele confere os pré-requisitos, coleta a configuração obrigatória, grava `deploy/.env` e sobe a composição de produção: Caddy, portal e PostgreSQL.

:::danger[Leia antes de implantar]
O processo do portal equivale a root no host, e cada usuário tem root dentro do próprio desktop. Leia [Superfície de confiança](/security/trust-surface/) antes de expor o portal além da própria máquina.
:::

## Pré-requisitos

- Um host Linux com Docker e o plugin Docker Compose v2.
- O daemon do Docker em execução e acessível ao usuário que roda o script (por exemplo, por pertencer ao grupo `docker`).
- Um domínio já apontando para o host. O Caddy obtém o certificado Let's Encrypt automaticamente, o que exige as portas 80 e 443 do host livres e alcançáveis pela internet.
- `python3` ou `openssl`, usados para gerar os segredos. O script prefere `python3` e recorre a `openssl` quando ele não existe.

## Instalar

```bash
git clone https://github.com/alanyoshida/webcontainerui.git webcontainerui
cd webcontainerui
./install.sh
```

`./install.sh --help` (ou `-h`) imprime o resumo de uso e sai.

## O que o script faz

### 1. Confere os pré-requisitos

O script encerra com erro se o comando `docker` não existir, se `docker compose version` falhar ou se `docker info` não conseguir falar com o daemon.

### 2. Coleta a configuração

Se `deploy/.env` já existir, seus valores são carregados primeiro. Depois, cada variável ainda vazia é perguntada ou gerada:

| Variável | Origem | Regra |
|---|---|---|
| `WCUI_DOMAIN` | Perguntada | Obrigatória; domínio público do portal |
| `WCUI_ADMIN_EMAIL` | Perguntada | Obrigatória; e-mail do primeiro administrador |
| `WCUI_ADMIN_PASSWORD` | Perguntada, sem eco | Mínimo de 12 caracteres; o prompt repete até a senha ser aceita |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | Gerada | Chave Fernet (32 bytes aleatórios em base64 urlsafe) que cifra as identidades SSH em repouso |
| `WCUI_POSTGRES_PASSWORD` | Gerada | Senha do PostgreSQL interno |
| `WCUI_DATA_PLANE_SECRET` | Gerada | Segredo compartilhado entre o portal e o Caddy para o `forward_auth` |

:::caution[Guarde a chave de cifra]
Perder `WCUI_SSH_KEY_ENCRYPTION_KEY` impede descriptografar as chaves SSH já cifradas no banco. Inclua `deploy/.env` na sua rotina de backup, tratando-o como segredo.
:::

### 3. Grava `deploy/.env`

As seis variáveis são gravadas em `deploy/.env`, com permissão `600`. O arquivo é ignorado pelo git. O script então exibe um resumo, ocultando a senha e os segredos.

### 4. Pede confirmação e sobe a composição

Antes de subir, o script avisa que vai construir a imagem, expor as portas 80 e 443 do host e solicitar o certificado para o domínio informado, e pergunta `Continuar? [s/N]`. Qualquer resposta diferente de `s` ou `y` cancela a subida; a configuração em `deploy/.env` é mantida para a próxima execução.

Confirmando, o script executa:

```bash
cd deploy && docker compose up -d --build
```

Ao final, o portal fica disponível em `https://<seu-domínio>` assim que o DNS e o certificado propagarem.

## Primeiro acesso

Entre com o e-mail e a senha do primeiro administrador. A partir daí:

1. Acompanhe no painel administrativo o build das imagens de agente e o download das imagens de desktop padrão. Registre outras imagens, se quiser.
2. Crie usuários e grupos.
3. Conceda aos grupos o acesso às imagens. Um usuário sem grupo não tem acesso a imagem alguma.

Depois, percorra o [checklist pós-deploy](/operations/post-deploy-checklist/).

## Atualizar

Rodar `./install.sh` de novo, por exemplo depois de um `git pull`, reaproveita o `deploy/.env` já gravado, não repete as perguntas já respondidas e só reconstrói e reinicia os containers.

```bash
git pull
./install.sh
```

:::caution
Faça backup do banco antes de atualizar para uma versão que altere o schema. Veja [Backup e restauração](/operations/backup-and-restore/) e [Reversão](/operations/rollback/).
:::

## Instalação não interativa

As variáveis `WCUI_DOMAIN`, `WCUI_ADMIN_EMAIL`, `WCUI_ADMIN_PASSWORD`, `WCUI_SSH_KEY_ENCRYPTION_KEY`, `WCUI_DATA_PLANE_SECRET` e `WCUI_POSTGRES_PASSWORD`, quando já exportadas no ambiente, pulam o prompt ou a geração correspondente. Se `WCUI_ADMIN_PASSWORD` vier do ambiente com menos de 12 caracteres, o script encerra com erro em vez de perguntar.

Quando `deploy/.env` já existe, ele é carregado depois do ambiente: os valores gravados nele prevalecem sobre os exportados. Para trocar um valor numa instalação existente, edite o arquivo.

A confirmação final (`Continuar? [s/N]`) é sempre lida da entrada padrão; em provisionamento automatizado, forneça a resposta por ela:

```bash
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="senha com pelo menos 12 caracteres"
echo s | ./install.sh
```

## Prefere fazer à mão?

Quem prefere configurar sem o script, ou precisa das variáveis opcionais, encontra a ordem de subida em [Implantação manual](/operations/manual-deployment/) e a lista completa em [Variáveis de ambiente](/operations/environment-variables/).
