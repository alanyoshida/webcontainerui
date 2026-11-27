---
title: Backup e restauração
description: Como fazer backup lógico do PostgreSQL de produção com pg_dump, como restaurá-lo e por que o arquivo de backup é sensível.
sidebar:
  order: 3
---

Em produção, todo o estado do portal fica no PostgreSQL interno da composição. Os backups desse banco são o único caminho de recuperação: a instalação nasce com banco vazio e não existe migração de dados a partir do SQLite de versões anteriores. Esta página cobre o backup lógico, a restauração e o que mais precisa ser guardado junto.

## O que o banco guarda

O serviço `postgres` (imagem `postgres:17-alpine`, banco `wcui`, usuário `wcui`) persiste os dados no volume nomeado `wcui_pg_data`. O volume sobrevive a `docker compose down`; só `docker compose down -v` o apaga.

O banco contém os dados do portal:

- usuários, com o hash das senhas, e grupos;
- sessões de login;
- o catálogo de imagens, com limites e concessões de acesso;
- o registro das instâncias e as métricas de uso;
- a identidade SSH de cada usuário, com a chave privada cifrada;
- os servidores MCP cadastrados, com variáveis de ambiente e cabeçalhos cifrados;
- a biblioteca de documentos AGENTS.md e as skills de agente.

O desenho da camada de persistência está em [Banco de dados](/architecture/database/).

### O que não está no banco

- **Os dados de cada desktop de usuário.** Cada par usuário/imagem tem um volume Docker próprio, nomeado, fora do PostgreSQL. O `pg_dump` não os cobre.
- **As capas enviadas pelo administrador.** Ficam em `/data/uploads/images`, no volume `wcui_db` do portal.
- **Os certificados TLS.** Ficam no volume `caddy_data` e são reemitidos pelo Caddy se o volume for perdido.
- **Os segredos do ambiente.** `deploy/.env` não faz parte de nenhum volume.

## Por que o backup é sensível

:::caution
Trate o arquivo de backup como um segredo. Ele contém os e-mails de todos os usuários, os hashes das senhas, as sessões de login, as chaves privadas SSH cifradas e os segredos cifrados dos servidores MCP.
:::

As chaves privadas SSH e os segredos dos servidores MCP são cifrados em repouso com `WCUI_SSH_KEY_ENCRYPTION_KEY` (Fernet). Isso tem duas consequências operacionais:

- Quem obtiver o backup **e** essa chave consegue descriptografar a chave privada SSH de todos os usuários e os segredos dos servidores MCP. Guarde os dois em locais separados.
- Um backup restaurado **sem** a mesma `WCUI_SSH_KEY_ENCRYPTION_KEY` deixa as identidades SSH e os segredos dos servidores MCP ilegíveis. Guarde a chave (e o restante de `deploy/.env`) com o mesmo cuidado que o backup, fora do host.

Armazene os backups cifrados e com acesso restrito, e não os deixe no diretório `deploy/` do host além do necessário.

## Backup lógico

Execute a partir do diretório `deploy/`, com a composição no ar:

```bash
docker compose exec -T postgres pg_dump -U wcui wcui > wcui-$(date +%F).sql
```

O `pg_dump` produz um instantâneo consistente sem precisar parar o portal. Como o PostgreSQL não publica porta no host, o comando roda dentro do container do banco.

Faça um backup antes de qualquer atualização que altere o schema e mantenha uma rotina periódica compatível com o quanto de dados você aceita perder.

## Restauração

A restauração é feita com o portal parado, para que nada grave no banco durante a carga:

```bash
docker compose stop portal
docker compose exec -T postgres psql -U wcui wcui < wcui-2026-11-06.sql
docker compose start portal
```

Substitua `wcui-2026-11-06.sql` pelo arquivo que você quer restaurar.

:::note
O comando acima carrega o backup sobre o banco existente. O arquivo gerado pelo `pg_dump` sem opções adicionais recria tabelas e dados, mas não remove os objetos que já existem; a restauração limpa pressupõe um banco `wcui` vazio, como o de uma instalação nova antes da primeira subida do portal.
:::

Depois de restaurar, o portal reconcilia o estado das instâncias na própria inicialização. Confira o resultado com o [Checklist pós-deploy](/operations/post-deploy-checklist/).

## Desenvolvimento e versões anteriores (SQLite)

Em desenvolvimento e nos testes o banco é um único arquivo SQLite (`WCUI_DB_PATH`, por padrão `/data/webcontainerui.db`), sem `WCUI_DATABASE_URL`. O mesmo vale para deploys de versões anteriores à adoção do PostgreSQL, cujo arquivo permanece intacto no volume `wcui_db`. A cópia e a restauração desse arquivo estão descritas em [Reversão](/operations/rollback/).
