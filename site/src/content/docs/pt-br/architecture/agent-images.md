---
title: Imagens de agente
description: Como o portal constrói as imagens de agentes de código a partir de uma base comum, decide quando reconstruir e injeta capas e documentos AGENTS.md.
sidebar:
  order: 4
---

As imagens de agente dão acesso, pelo navegador, a agentes de código de linha de comando. Diferentemente dos desktops, que são baixados de um registro, elas são construídas localmente pelo portal, a partir de Dockerfiles versionados em [`agent-images/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images), e entram no catálogo sem ação manual do administrador.

## Conjunto de imagens

| Entrada | Diretório | Imagem | Instalação | Comando |
|---|---|---|---|---|
| Claude Code | `claude-code/` | `wcui-agent-claude-code:latest` | `npm install -g @anthropic-ai/claude-code` | `claude` |
| Hermes | `hermes/` | `wcui-agent-hermes:latest` | `pip install hermes-agent` em venv isolado | `hermes` |
| Agy | `agy/` | `wcui-agent-agy:latest` | script oficial do Antigravity CLI | `agy` |
| OpenCode | `opencode/` | `wcui-agent-opencode:latest` | `npm install -g opencode-ai` | `opencode` |
| oh-my-pi | `oh-my-pi/` | `wcui-agent-oh-my-pi:latest` | script oficial do oh-my-pi | `omp` |

Todas usam a porta 3000 e são registradas no catálogo com provisionamento do tipo `build`.

## Base comum

Cada agente parte de `wcui-agent-base:latest`, construída a partir de [`agent-images/_base/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images/_base). A base contém:

- `node:20-bookworm-slim`, com Python 3, `pip` e `venv`, que são os runtimes que as CLIs dos agentes costumam usar;
- `git` e `openssh-client`;
- [ttyd](https://github.com/tsl0922/ttyd), o terminal web, como binário estático de versão fixada;
- GitHub CLI (`gh`) e GitLab CLI (`glab`), também como binários de versão fixada. O login em cada um é manual, pelo usuário, no terminal; nenhum dos dois usa a identidade SSH do portal;
- o entrypoint comum.

### Entrypoint

O [`entrypoint.sh`](https://github.com/alanyoshida/webcontainerui/blob/main/agent-images/_base/entrypoint.sh) executa `ttyd --writable` com o comando do agente (o `CMD` de cada imagem derivada), usando as mesmas variáveis de ambiente que o portal passa a qualquer instância:

| Variável | Efeito |
|---|---|
| `PORT` | Porta em que o ttyd escuta; o portal a define com a porta da entrada do catálogo |
| `SUBFOLDER` | Vira o `--base-path` do ttyd, para casar com o prefixo `/i/<uuid>/` |
| `CUSTOM_USER` e `PASSWORD` | Viram a `--credential` do ttyd, que é a credencial interna da instância |

É isso que permite a uma imagem de agente usar o mesmo mecanismo de sessão dos desktops, descrito em [Origem única](/architecture/overview/).

### Home em `/config`

O volume de arquivos do usuário é montado em `/config`. A base fixa `HOME=/config`, ajusta o diretório do usuário em `/etc/passwd` (o cliente `ssh` resolve a home por ali, não pela variável de ambiente) e define `/config` como diretório de trabalho. Assim, credenciais, sessões e configuração das CLIs ficam no volume e sobrevivem à recriação do container, e o agente já inicia no diretório onde o `AGENTS.md` é injetado.

## Provisionamento no startup

A cada inicialização, o portal:

1. constrói a imagem base;
2. para cada agente, garante a entrada no catálogo e constrói a imagem quando necessário, aguardando cada build.

Uma falha de build é isolada: a entrada fica marcada como falha, as demais seguem e o portal sobe mesmo assim. Uma falha é tentada de novo no startup seguinte.

O build acontece dentro do container do portal, que carrega uma cópia de `agent-images/` e envia o contexto ao daemon do host pelo socket do Docker.

## Hash de contexto

Para não reconstruir tudo a cada startup, o portal calcula um hash SHA-256 do contexto de build de cada agente e o guarda junto da entrada, após um build bem-sucedido. O rebuild só acontece quando o hash muda ou quando a entrada não está pronta.

O hash cobre:

- o conteúdo e o caminho relativo de cada arquivo de `_base/` e do subdiretório do agente;
- a lista de skills vinculadas à imagem.

Ele não depende de data de modificação, só do conteúdo.

:::note
Mudanças em `agent-images/covers/` não entram no hash e, portanto, não disparam rebuild.
:::

## Skills e servidores MCP

Duas bibliotecas administrativas se aplicam somente a imagens de agente, com mecanismos diferentes:

- **Skills** são instaladas durante o build. Cada Dockerfile recebe o argumento `SKILLS` e instala cada item com `npx skills add`, isoladamente: uma skill que falha não derruba o build nem impede as demais. Vincular ou desvincular uma skill altera o hash e dispara o rebuild imediato da imagem. Instâncias já em execução não recebem as skills de um rebuild posterior.
- **Servidores MCP** são configurados nas instâncias, sem rebuild: vincular, editar ou desvincular um servidor propaga para as instâncias vivas, e novas instâncias já nascem configuradas.

## Capas padrão

No startup, o portal cadastra uma capa padrão em toda entrada do catálogo, de desktop ou de agente, a partir dos PNGs versionados em [`agent-images/covers/`](https://github.com/alanyoshida/webcontainerui/tree/main/agent-images/covers). A capa é escolhida casando o nome, o repositório ou a tag da entrada com um mapa de logos; sem correspondência, usa-se uma capa genérica.

- Uma capa enviada pelo administrador nunca é sobrescrita.
- Uma capa padrão é atualizada automaticamente quando o PNG versionado muda.
- Uma imagem registrada depois do startup recebe a capa padrão no próximo restart.
- O portal não gera imagens em tempo de execução: as capas são geradas em desenvolvimento por um script e versionadas. O procedimento e as fontes dos logos estão no [README das capas](https://github.com/alanyoshida/webcontainerui/blob/main/agent-images/covers/README.md).

## Documentos AGENTS.md

O administrador mantém uma biblioteca de documentos `AGENTS.md` e vincula cada entrada do catálogo a no máximo um deles. O vínculo vale para qualquer entrada, não só para imagens de agente.

- **Na criação da instância**, o documento vinculado é gravado como `/config/AGENTS.md`. A injeção é best-effort, feita junto da identidade SSH: uma falha não impede a instância de subir.
- **Ao salvar** o texto ou o vínculo, o portal propaga a alteração às instâncias vivas daquela entrada.
- **Ao desvincular**, o arquivo é removido das instâncias vivas por `docker exec`, com um comando fixo no código do portal, nunca derivado de input de usuário.
- **A remoção** de um documento é recusada enquanto houver entradas vinculadas a ele.

O conteúdo de um documento é limitado a 262144 bytes por padrão (`WCUI_MAX_AGENTS_MD_BYTES`).

## Adicionar ou alterar um agente

Antes de mudar o entrypoint ou um Dockerfile de agente, rode a suíte e2e, que exige Docker real; veja [Desenvolvimento](/reference/development/).

## Referência formal

O contrato de comportamento está nas specs [`coding-agent-images`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/coding-agent-images/spec.md), [`agents-md`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agents-md/spec.md), [`image-catalog`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/image-catalog/spec.md), [`agent-skills`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/agent-skills/spec.md) e [`mcp-servers`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/mcp-servers/spec.md).
