---
title: Plano de dados das sessões
description: Como o Caddy transporta o tráfego de /i/{uuid}/ direto aos containers em produção, consultando o portal por forward_auth antes de cada requisição.
sidebar:
  order: 2
---

Em produção, o tráfego de uma sessão (HTTP e WebSocket sob `/i/{uuid}/*`) vai do navegador ao container pelo Caddy, sem atravessar o processo do portal. O portal continua sendo quem decide: antes de cada requisição, o Caddy o consulta por `forward_auth`. Em desenvolvimento, sem Caddy, o próprio portal entrega as sessões.

## Divisão de responsabilidades

| Componente | Responsabilidade |
|---|---|
| Caddy | Termina TLS, transporta os bytes da sessão e consulta o portal antes de encaminhar |
| Portal | Decide a autorização (sessão, dono, instância em execução), publica as rotas e registra atividade |
| Container | Recebe a requisição já com a credencial interna da instância |

O portal **não transporta frames**. A autorização é uma chamada curta por requisição HTTP; o canal WebSocket é autorizado uma vez, na abertura, e não por mensagem.

## Autorização por `forward_auth`

O endpoint interno é `GET /internal/data-plane/authorize`. O `forward_auth` do Caddy reescreve a URI para esse endpoint e envia a URI original no cabeçalho `X-Forwarded-Uri`, de onde o portal extrai o identificador da instância. O cookie de sessão do usuário acompanha a subrequisição.

O portal responde:

| Resposta | Situação |
|---|---|
| `401` | Segredo do plano de dados ausente ou incorreto |
| `404` | URI encaminhada não corresponde a um caminho `/i/{uuid}/` |
| `401` | Sem sessão autenticada válida |
| `404` | Instância inexistente ou de outro usuário |
| `409` | Instância não está em execução |
| `200` | Aprovado; a resposta carrega a credencial da instância no cabeçalho `Authorization` |

Qualquer resposta diferente de `2xx` faz o Caddy devolver essa resposta ao cliente e não encaminhar nada ao container. O mesmo vale quando o portal está indisponível: sem aprovação, não há encaminhamento.

### Segredo compartilhado

O endpoint só responde a quem apresentar `WCUI_DATA_PLANE_SECRET` no cabeçalho `X-Data-Plane-Secret`, comparado em tempo constante. Com o segredo vazio no portal, o endpoint fica desativado e ninguém é aprovado; é o caso de desenvolvimento e testes, que não têm Caddy à frente.

O endpoint não aparece no schema público da API, e o [`Caddyfile`](https://github.com/alanyoshida/webcontainerui/blob/main/deploy/Caddyfile) responde `404` a `/internal/*` vindo da borda. Só o `forward_auth`, de dentro da rede interna, o alcança.

### Credencial da instância

Só a resposta aprovada carrega a credencial interna da instância. O Caddy a copia para a requisição encaminhada (`copy_headers Authorization`), substituindo qualquer credencial enviada pelo cliente. Ela nunca é devolvida ao navegador.

## Publicação de rotas

O Caddy não conhece as instâncias de antemão. O portal escreve um arquivo `<uuid>.caddy` por instância em execução no diretório `WCUI_CADDY_ROUTES_DIR`, montado no volume compartilhado `caddy_routes`, e o `Caddyfile` importa esse diretório. Cada arquivo tem esta forma:

```text
handle /i/<uuid>/* {
	forward_auth portal:8000 {
		uri /internal/data-plane/authorize
		header_up -Upgrade
		header_up -Connection
		header_up -Sec-WebSocket-Key
		header_up -Sec-WebSocket-Version
		header_up -Sec-WebSocket-Protocol
		header_up -Sec-WebSocket-Extensions
		header_up X-Data-Plane-Secret {$WCUI_DATA_PLANE_SECRET}
		copy_headers Authorization
	}
	reverse_proxy <nome-do-container>:<porta> {
		transport http {
			read_timeout 3600s
			write_timeout 3600s
		}
	}
}
```

Os cabeçalhos de upgrade são removidos da subrequisição de autorização porque o endpoint interno só aceita HTTP; sem isso, a abertura do WebSocket falharia. A porta é a definida na entrada do catálogo, e os tempos de espera de 3600 segundos evitam que uma sessão longa e ociosa seja cortada.

### Ciclo de vida

- **Ao criar ou iniciar** uma instância, o portal publica a rota e recarrega o Caddy.
- **Ao parar ou excluir**, retira a rota e recarrega.
- **No startup**, sincroniza o diretório com o banco: escreve as rotas das instâncias em execução, remove as demais e recarrega uma única vez.

A publicação é idempotente (um arquivo com o conteúdo esperado não é reescrito nem provoca recarga), a escrita é atômica e as operações são serializadas por um lock. Um arquivo de placeholder mantém o diretório sempre com ao menos um arquivo importável.

### Recarga do Caddy

A recarga é feita por `docker exec` no container do Caddy (`WCUI_CADDY_CONTAINER`, por padrão `wcui-caddy`), com um comando fixo no código:

```bash
caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

O comando nunca é derivado de input de usuário. O identificador da instância e o nome do container, que entram no arquivo de rota, são gerados pelo portal e validados contra um conjunto restrito de caracteres antes da escrita. Falhas de recarga são registradas na [trilha de auditoria](/security/audit-log/); a rota permanece escrita e é aplicada na recarga seguinte.

Sem `WCUI_CADDY_ROUTES_DIR` configurado, toda a publicação é um no-op. É o modo de desenvolvimento e de testes.

## Detecção de ociosidade

Como o portal não vê o tráfego das sessões em produção, a atividade que alimenta a parada automática de instâncias ociosas vem de duas fontes:

- **Autorizações aprovadas**: cada resposta `200` do endpoint interno registra um toque de atividade.
- **Heartbeat da visão de sessão**: enquanto a sessão está aberta no portal, o front-end chama `POST /api/instances/{id}/heartbeat`. O portal aceita no máximo um toque por instância a cada 30 segundos (`WCUI_HEARTBEAT_MIN_SECONDS`).

Os toques são acumulados em memória e gravados em lote. Não há gravação por mensagem trafegada.

## Proxy in-process em desenvolvimento

O proxy dentro do portal (`backend/app/api/session_proxy.py`) continua registrado em todos os ambientes. Ele atende `/i/{instance_id}/...` em HTTP e WebSocket com as mesmas verificações (sessão, dono, instância em execução) e a mesma injeção de credencial.

- Em **desenvolvimento e na suíte de testes**, é ele quem entrega as sessões.
- Em **produção**, fica sombreado pelo roteamento da borda: as rotas `handle /i/<uuid>/*` do Caddy têm precedência sobre o `reverse_proxy` geral para o portal. Uma requisição a um `/i/<uuid>/` sem rota publicada cai no portal e passa pelas mesmas verificações, o que o torna também uma defesa em profundidade.

## Referência formal

O contrato de comportamento está nas specs [`stream-data-plane`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md) e [`session-proxy`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md). As variáveis citadas aqui estão em [Variáveis de ambiente](/operations/environment-variables/).
