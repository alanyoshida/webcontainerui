---
title: Capabilities
description: Índice das 19 capabilities do projeto, com o propósito de cada uma e o link para a spec formal no repositório.
sidebar:
  order: 1
---

O comportamento do portal é especificado por capability, em [`openspec/specs/`](https://github.com/alanyoshida/webcontainerui/tree/main/openspec/specs). Esta página é o índice das 19 capabilities atuais.

As specs são o contrato formal de comportamento do produto: cada uma declara um propósito e uma lista de requisitos normativos (com `DEVE`), e cada requisito tem ao menos um cenário no formato WHEN/THEN. Quando esta documentação e uma spec divergirem, vale a spec. As specs existem somente em português; não há tradução para o inglês.

## Contas e acesso

| Capability | Propósito |
|---|---|
| [`auth`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) | Autentica pessoas no portal e governa o ciclo de vida da sessão, que pode ser revogada a qualquer momento pelo usuário ou pelo administrador. |
| [`user-management`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/user-management/spec.md) | Administra as contas que podem usar o portal e os grupos que as organizam, base sobre a qual as permissões de imagem são resolvidas. |
| [`access-control`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/access-control/spec.md) | Decide quais imagens cada usuário pode usar, concedendo permissão a grupos, e define o que acontece com instâncias em execução quando uma permissão é retirada. |
| [`ssh-identity`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/ssh-identity/spec.md) | Dá a cada usuário uma identidade SSH própria, gerada e guardada pelo portal, disponível em qualquer instância dele para que o `git` autentique sem configuração manual. |

## Catálogo e imagens

| Capability | Propósito |
|---|---|
| [`image-catalog`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/image-catalog/spec.md) | Mantém o conjunto de imagens que o portal oferece, incluindo o download e o estado de prontidão que decide se a imagem já pode originar instâncias. |
| [`coding-agent-images`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/coding-agent-images/spec.md) | Mantém no catálogo um conjunto fixo de imagens de agentes de código em CLI, provisionadas pelo portal e acessadas pelo mesmo mecanismo de sessão dos desktops. |
| [`agents-md`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agents-md/spec.md) | Mantém uma biblioteca de documentos `AGENTS.md`, permite vincular cada entrada do catálogo a um deles e injeta o documento nas instâncias. |
| [`agent-skills`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agent-skills/spec.md) | Mantém uma biblioteca de skills, permite vincular cada imagem de agente a várias delas e garante que o build da imagem as instale. |
| [`mcp-servers`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/mcp-servers/spec.md) | Mantém uma biblioteca de servidores MCP, permite vincular cada imagem de agente a vários deles e os configura nas instâncias sem exigir rebuild. |

## Instâncias e sessões

| Capability | Propósito |
|---|---|
| [`desktop-instances`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/desktop-instances/spec.md) | Governa as sessões de cada usuário: quando um container nasce, para e é removido, onde os arquivos persistem, quantas sessões uma pessoa mantém e como sessões abandonadas deixam de consumir memória. |
| [`session-proxy`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md) | Entrega a sessão ao navegador do dono e de mais ninguém, autorizando cada requisição pela propriedade da instância antes de encaminhá-la ao container. |
| [`stream-data-plane`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md) | Define o transporte do tráfego de sessão por um plano de dados externo ao portal em produção, com a decisão de autorização permanecendo no portal. |
| [`session-view`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-view/spec.md) | Define como o portal exibe uma sessão em execução e permite expandi-la para a tela inteira, preservando uma forma clara de sair desse modo. |
| [`instance-usage-metrics`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/instance-usage-metrics/spec.md) | Registra o histórico de execução de cada instância e oferece ao administrador visibilidade, ao vivo e histórica, sobre quem usa quais instâncias e por quanto tempo. |

## Segurança e persistência

| Capability | Propósito |
|---|---|
| [`http-hardening`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md) | Endurece a superfície HTTP do portal com cabeçalhos de segurança e exposição mínima de documentação e identificação de stack. |
| [`security-audit-log`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md) | Mantém uma trilha estruturada e consultável dos eventos de segurança: quem fez o quê, de onde e com que desfecho, sem jamais registrar segredos. |
| [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md) | Define qual banco de dados o portal usa em cada ambiente, como a escolha é configurada e como a composição de produção provê o PostgreSQL. |

## Interface

| Capability | Propósito |
|---|---|
| [`app-shell`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/app-shell/spec.md) | Define a moldura visível do portal: a barra superior, a navegação administrativa, a estrutura de páginas do console e as regras de feedback e estados vazios. |
| [`theming`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/theming/spec.md) | Define a identidade visual do portal: os três temas de cores, o tema padrão, a persistência da escolha e as famílias tipográficas e de ícones. |

## Consultar as specs localmente

Com o CLI do OpenSpec instalado, a lista e o conteúdo das specs podem ser consultados a partir do clone do repositório:

```bash
openspec list --specs
openspec show auth
```

O fluxo de proposta e implementação de mudanças está em [Desenvolvimento](/reference/development/).
