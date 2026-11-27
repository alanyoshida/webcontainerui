---
title: Trilha de eventos de segurança
description: Formato, campos e catálogo dos eventos de segurança que o portal emite, o que nunca é registrado e de quem é a responsabilidade pela retenção.
sidebar:
  order: 4
---

O portal emite um registro estruturado para cada evento de segurança relevante: quem fez o quê, de onde e com que desfecho. A trilha existe para detecção e perícia — saber que houve uma rajada de logins com falha, qual administrador revogou uma concessão, quando uma instância foi excluída. Ela é deliberadamente simples: linhas JSON na saída padrão, sem tabela no banco e sem dependência adicional.

## Formato

Um evento é uma linha JSON na saída padrão do portal, capturável com `docker logs` no container do portal ou pelo coletor do operador (Loki, Vector, CloudWatch e similares):

```bash
docker logs deploy-portal-1 2>&1 | grep '"event"'
```

```json
{"event": "auth.login", "actor_id": 1, "actor_email": "a@x.test", "ip": "203.0.113.9", "outcome": "success"}
```

O nome do container depende do nome do projeto do Compose; confira com `docker ps`.

A linha é o JSON puro, sem prefixo. **Não há carimbo de tempo dentro do evento**: o horário vem do driver de log do Docker (`docker logs --timestamps`) ou do coletor. Se o seu coletor descarta o horário de ingestão, os eventos ficam sem data.

## Campos

| Campo | Presença | Conteúdo |
|---|---|---|
| `event` | sempre | Nome do evento, do catálogo abaixo |
| `actor_id` | quando há sessão | Identificador numérico de quem agiu |
| `actor_email` | quando há sessão ou tentativa de login | E-mail de quem agiu; em falhas de login, o e-mail **tentado** |
| `ip` | quando disponível | IP do cliente como o portal o enxerga |
| `target` | quando a ação tem objeto | Objeto da ação: id de instância, e-mail de usuário, `repositório:tag` de imagem, grupo |
| `outcome` | sempre | `success`, `failure` ou `denied` |
| `detail` | opcional | Texto curto, por exemplo `op=criar` ou `retry_after=287s` |

Sobre cada um:

- `actor_id` e `actor_email` vêm da sessão autenticada. Em eventos internos do sistema, sem usuário por trás — como uma falha de provisionamento —, eles estão ausentes.
- Em falhas de login, `actor_email` é o texto que o cliente enviou, sem normalização. Não é prova de que a conta existe.
- `ip` é o IP real do cliente apenas atrás de proxy confiável, isto é, quando a requisição chega pelo Caddy e a allowlist `UVICORN_FORWARDED_ALLOW_IPS` está correta. Uma requisição feita de dentro da rede interna pode forjar esse valor. Ver [Endurecimento do login](/security/login-hardening/).
- `detail` é truncado quando carrega mensagem de erro (300 caracteres).

## Catálogo de eventos

### Autenticação

| Evento | Desfecho | Quando |
|---|---|---|
| `auth.login` | `success` | Login aceito |
| `auth.login` | `failure` | E-mail inexistente, senha errada ou conta desabilitada — os três indistintos, de propósito |
| `auth.login.throttled` | `denied` | Tentativa recusada pelo limitador, sem verificação de credencial; `detail` traz o tempo de espera |
| `auth.logout` | `success` | Logout de uma sessão válida |

### Administração

| Evento | Quando |
|---|---|
| `admin.user.created` | Usuário criado; `detail` indica se é administrador |
| `admin.user.disabled` | Conta desabilitada (e sessões dela revogadas) |
| `admin.group.changed` | Grupo criado, renomeado ou excluído; membro adicionado ou removido |
| `admin.grant.changed` | Imagem concedida a um grupo |
| `admin.grant.revoked` | Concessão revogada; `detail` traz quantas instâncias foram afetadas |
| `admin.image.changed` | Entrada do catálogo criada, editada, atualizada, habilitada, desabilitada, com capa trocada ou com download repetido |
| `admin.document.changed` | Documento `AGENTS.md` criado, editado, excluído ou vinculado a uma imagem |
| `admin.mcp.changed` | Servidor MCP criado, editado, excluído, vinculado ou desvinculado |
| `admin.skill.changed` | Skill criada, editada, excluída, vinculada ou desvinculada |

Todos têm o administrador como ator e `outcome` igual a `success`; a operação específica vai em `detail` (`op=criar`, `op=editar`, `op=excluir` e assim por diante).

### Instâncias

| Evento | Desfecho | Quando |
|---|---|---|
| `instance.created` | `success` | Dono criou uma instância; `detail` traz a imagem |
| `instance.updated` | `success` | Dono atualizou a instância para a versão corrente da imagem |
| `instance.stopped` | `success` | Dono parou a instância |
| `instance.deleted` | `success` | Dono excluiu a instância |
| `instance.failed` | `failure` | Falha ao criar ou iniciar o container; sem ator, com o erro truncado em `detail` |

### Plano de dados

| Evento | Desfecho | Quando |
|---|---|---|
| `data_plane.reload` | `failure` | O `caddy reload` disparado pelo portal após publicar ou retirar uma rota falhou |

Este evento é operacional, não de autenticação, mas sai pelo mesmo canal: um reload que falha significa que uma rota de sessão pode não ter sido aplicada — ou, mais importante, **retirada**. Vale um alerta.

## O que a trilha não cobre

A cobertura atual é a das tabelas acima, e ela tem lacunas conhecidas. Não presuma que a ausência de evento significa ausência de ação.

- **Tentativas negadas por autorização não são registradas.** Um usuário comum batendo em rota administrativa (`403`) ou pedindo a instância de outro (`404`) não gera evento. Só o limitador de login emite `denied`.
- **Operações administrativas só são registradas quando concluídas.** Uma tentativa que falha por validação ou conflito não aparece.
- **Paradas automáticas não emitem `instance.stopped`.** Instância parada por ociosidade, por reconciliação de estado ou como efeito de uma revogação de concessão não gera evento próprio; a revogação registra apenas a contagem em `admin.grant.revoked`.
- **Regeneração da identidade SSH não é registrada.**
- **Acesso às sessões não é registrado.** Abrir `/i/{uuid}/`, cada autorização do plano de dados e o conteúdo da sessão ficam fora da trilha. O que o usuário faz dentro do container não é visível ao portal.
- **Leituras não são registradas.** Listar usuários, consultar métricas de uso ou ler um documento não gera evento.
- **A trilha é best-effort.** A emissão não é transacional com a ação: se o processo cair entre a ação e a escrita, o evento se perde. E a saída padrão não tem proteção contra adulteração — quem tem acesso ao host ou ao daemon do Docker pode apagar ou alterar os logs.

Se o seu ambiente exige trilha completa de acesso, registre também o log de acesso do Caddy na borda.

## O que nunca é registrado

Nenhum evento carrega segredo. Senha, token de sessão, credencial interna de instância, chave privada SSH e valores de variáveis de ambiente ou cabeçalhos de servidor MCP nunca passam pelo emissor (`backend/app/services/audit_log.py`).

A garantia é por construção dos pontos de emissão: o emissor só recebe campos nomeados explicitamente, e nenhum chamador passa esses valores. Não existe um filtro que remova segredos de um texto arbitrário. Dois pontos de atenção decorrem disso:

- `instance.failed` e `data_plane.reload` copiam para `detail` até 300 caracteres da mensagem de erro do Docker ou do Caddy. Essas mensagens não costumam conter segredos, mas não são controladas pelo portal.
- Em falhas de login, o e-mail tentado é registrado como veio. Um usuário que digite a senha no campo de e-mail por engano terá esse texto gravado no log.

A trilha contém dados pessoais — e-mails e endereços IP. Trate o destino dos logs de acordo.

## Retenção e rotação

O portal só escreve na saída padrão. Retenção e rotação são responsabilidade do driver de log do Docker ou do coletor externo.

:::caution[A composição não configura rotação]
A composição de produção não define opções de log para o serviço do portal. Com o driver padrão `json-file` sem `max-size`, o arquivo de log do container cresce sem limite, e os eventos somem quando o container é removido e recriado (o que acontece a cada atualização). Se a trilha importa para você, configure as duas coisas: rotação e envio para fora do host.
:::

Exemplo de rotação local, a acrescentar ao serviço `portal` na composição:

```yaml
services:
  portal:
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "10"
```

Rotação local limita o disco, mas também limita o histórico e não protege a trilha de quem compromete o host. Para perícia, envie os eventos a um coletor em outra máquina.

## Consultas úteis

Falhas de login e recusas do limitador, com horário:

```bash
docker logs --timestamps deploy-portal-1 2>&1 \
  | grep -E '"event": "auth\.login(\.throttled)?"' \
  | grep -E '"outcome": "(failure|denied)"'
```

Tudo o que um administrador alterou:

```bash
docker logs --timestamps deploy-portal-1 2>&1 | grep '"event": "admin\.'
```

Especificação: [security-audit-log](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md).
