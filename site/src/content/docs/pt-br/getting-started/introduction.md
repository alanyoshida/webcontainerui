---
title: Introdução
description: O que é o WebContainerUI, o que ele oferece a usuários e administradores e o que saber antes de implantar.
sidebar:
  order: 1
---

O WebContainerUI é um portal multiusuário que entrega desktops Linux completos e agentes de código em linha de comando dentro do navegador. Cada pessoa entra com a própria conta, escolhe um item do catálogo e recebe um container só dela, acessado pela mesma origem do portal, sem instalar cliente algum.

O back-end é FastAPI (Python 3.12), o front-end é React com Vite, a persistência é feita com SQLAlchemy (SQLite em desenvolvimento, PostgreSQL em produção) e cada instância é um container Docker numa rede interna.

## O que o catálogo oferece

O catálogo reúne dois tipos de entrada, usados pelo mesmo mecanismo de sessão.

### Desktops Linux

São as imagens [webtop](https://docs.linuxserver.io/images/docker-webtop/) do LinuxServer.io, registradas por download (`pull`). Um deploy novo já nasce com quatro entradas, baixadas em segundo plano na primeira subida:

| Entrada | Imagem |
|---|---|
| Webtop XFCE | `lscr.io/linuxserver/webtop:latest` |
| Ubuntu KDE | `lscr.io/linuxserver/webtop:ubuntu-kde` |
| Alpine MATE | `lscr.io/linuxserver/webtop:alpine-mate` |
| VS Code | `lscr.io/linuxserver/vscode:latest` |

O administrador pode registrar outras imagens, editar limites de recurso (memória, CPU, memória compartilhada), definir a porta de encaminhamento, desabilitar uma entrada sem removê-la e enviar uma imagem de capa.

### Agentes de código em CLI

São imagens construídas localmente pelo próprio portal, cada uma expondo um terminal web ([ttyd](https://github.com/tsl0922/ttyd)) que já abre na ferramenta correspondente:

| Entrada | Ferramenta | Comando |
|---|---|---|
| Claude Code | Claude Code | `claude` |
| Hermes | Hermes Agent (Nous Research) | `hermes` |
| Agy | Antigravity CLI | `agy` |
| OpenCode | OpenCode | `opencode` |
| oh-my-pi | oh-my-pi | `omp` |

Os detalhes de construção estão em [Imagens de agente](/architecture/agent-images/).

## O que o usuário faz

- Vê no catálogo apenas as imagens prontas às quais seus grupos têm acesso.
- Inicia, abre, para, atualiza e exclui as próprias instâncias. Cada usuário mantém no máximo uma instância por imagem.
- Usa a sessão numa visão dedicada do portal, com opção de tela cheia.
- Mantém os arquivos entre execuções: cada par usuário e imagem tem um volume próprio, preservado ao parar a instância e removido apenas ao excluí-la, após confirmação.
- Tem uma identidade SSH própria, gerada pelo portal e disponível em todas as suas instâncias, para que o `git` dentro do container autentique com repositórios remotos sem configuração manual.

Instâncias ociosas são paradas automaticamente (30 minutos por padrão), para que sessões abandonadas não consumam memória do host.

## O que o administrador faz

- **Usuários e grupos**: cria contas, desabilita sem apagar e organiza as pessoas em grupos. Não há autocadastro.
- **Concessões de acesso**: a permissão de uso de uma imagem é dada a grupos, nunca a pessoas. Revogar uma concessão para imediatamente as instâncias afetadas, e o impacto é informado antes da confirmação.
- **Catálogo**: registra imagens, acompanha o download ou o build, edita limites e capas.
- **Biblioteca AGENTS.md**: mantém documentos `AGENTS.md` e vincula cada entrada do catálogo a no máximo um deles; o texto é injetado nas instâncias como `/config/AGENTS.md`.
- **Servidores MCP**: cadastra servidores do Model Context Protocol e os vincula a imagens de agente; a configuração chega às instâncias sem reconstruir a imagem.
- **Skills**: mantém uma biblioteca de skills e as vincula a imagens de agente; o vínculo dispara o rebuild da imagem, que instala as skills.
- **Métricas de uso**: vê as instâncias em execução e o histórico de execuções, com horas por usuário e por grupo, imagens mais usadas, motivos de término, uso diário e pico de instâncias simultâneas.

O comportamento de cada uma dessas áreas é especificado formalmente; o índice está em [Capabilities](/reference/capabilities/).

## Antes de implantar

:::danger[O portal equivale a root no host]
O processo do portal precisa do socket do Docker para criar containers, e quem pode criar container pode montar o sistema de arquivos do host. Além disso, o usuário tem root dentro do próprio desktop: as imagens webtop embutem um terminal com `sudo` sem senha. Trate uma sessão como um login SSH numa máquina da sua rede e não exponha o portal à internet sem autenticação robusta à frente.
:::

Leia [Superfície de confiança](/security/trust-surface/) e [Camadas de isolamento](/security/isolation-layers/) antes de expor o portal além da própria máquina.

## Próximos passos

- [Teste local](/getting-started/local-trial/): suba o portal na própria máquina com um comando, sem domínio nem TLS.
- [Instalação](/getting-started/installation/): instalação de produção guiada pelo `install.sh`.
- [Arquitetura: origem única](/architecture/overview/): como as sessões são servidas e isoladas.
