---
title: Checklist pós-deploy
description: Verificações a executar depois de subir ou atualizar o portal em produção, com os comandos de cada uma.
sidebar:
  order: 5
---

Execute este checklist depois de cada subida ou atualização em produção. As duas primeiras checagens levam dois minutos e pegam as duas falhas silenciosas da área de login: HSTS ausente na borda e cookie de sessão sem a flag `Secure`. Nenhuma das duas causa erro visível — o portal funciona normalmente, só que menos protegido. As demais confirmam que a composição subiu como esperado.

Os comandos pressupõem o diretório `deploy/` e a variável `WCUI_DOMAIN` definida no shell.

## 1. HSTS presente na borda

```bash
curl -sI https://$WCUI_DOMAIN | grep -i strict-transport-security
```

Resultado esperado:

```text
strict-transport-security: max-age=31536000
```

O cabeçalho é adicionado pelo Caddy. Se o comando não imprimir nada, o `Caddyfile` em uso não é o do repositório ou a resposta não está vindo do Caddy.

## 2. Cookie de sessão com `Secure`

Faça login pela API e inspecione o cabeçalho `Set-Cookie`. Substitua `...` pela senha do administrador:

```bash
curl -sD - -o /dev/null -X POST https://$WCUI_DOMAIN/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$WCUI_ADMIN_EMAIL\",\"password\":\"...\"}" | grep -i set-cookie
```

O `Set-Cookie` precisa conter o atributo `Secure`.

:::caution
Se o `Set-Cookie` vier sem `Secure`, o `UVICORN_FORWARDED_ALLOW_IPS` não está casando com a subnet real da `wcui_net`. Confira a subnet com o comando abaixo; o IPAM da composição é a fonte da verdade.

```bash
docker network inspect wcui_net
```

Ajuste `WCUI_FORWARDED_ALLOW_IPS` para a subnet exibida (ou corrija o IPAM) e recrie o portal. Ver [Variáveis de ambiente](/operations/environment-variables/).
:::

:::note
Evite deixar a senha no histórico do shell. Cada tentativa com senha errada conta para o limitador de login, descrito em [Endurecimento do login](/security/login-hardening/).
:::

## 3. Serviços no ar e saudáveis

```bash
docker compose ps
```

Os três serviços (`postgres`, `portal` e `caddy`) devem estar em execução, com `postgres` e `portal` marcados como `healthy`.

## 4. Endpoint interno fechado na borda

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://$WCUI_DOMAIN/internal/data-plane/authorize
```

Resultado esperado: `404`. O endpoint de autorização do plano de dados só pode ser alcançado de dentro da rede interna.

## 5. Documentação interativa desligada

Com o padrão `WCUI_DOCS_ENABLED=false`, os caminhos `/docs`, `/redoc` e `/openapi.json` respondem `404`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://$WCUI_DOMAIN/openapi.json
```

Resultado esperado: `404`.

## 6. Catálogo e primeira sessão

- Entre no portal com `WCUI_ADMIN_EMAIL` e `WCUI_ADMIN_PASSWORD`.
- Na aba Catálogo do painel administrativo, acompanhe o download e o build das imagens. Eles rodam em segundo plano e, no primeiro deploy, somam vários GB.
- Crie grupos e usuários e conceda as imagens aos grupos. Um usuário só vê uma imagem concedida a um grupo do qual participa.
- Inicie uma instância e abra a sessão. Com ela aberta, confira as rotas publicadas no plano de dados:

```bash
docker exec wcui-caddy ls /etc/caddy/caddy-routes
```

O esperado é um arquivo por instância em estado `running`, mais o `000-placeholder.caddy`. Se a sessão ficar presa em "carregando", siga o diagnóstico em [Implantação manual](/operations/manual-deployment/).

## 7. Backup e segredos guardados

- Faça o primeiro backup do banco e confirme que o arquivo não está vazio — ver [Backup e restauração](/operations/backup-and-restore/).
- Guarde `deploy/.env` fora do host, em especial `WCUI_SSH_KEY_ENCRYPTION_KEY`: sem ela, um backup restaurado não consegue descriptografar as chaves SSH dos usuários.
- Releia [Superfície de confiança](/security/trust-surface/) antes de abrir o portal a outros usuários.
