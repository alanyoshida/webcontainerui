---
title: Desenvolvimento
description: Como montar o ambiente de desenvolvimento, rodar as suítes de teste e seguir as convenções do projeto ao contribuir.
sidebar:
  order: 2
---

Esta página reúne o que é preciso para contribuir: montar o ambiente, rodar os testes e seguir as convenções do código. As instruções operacionais completas para agentes de código estão no [`AGENTS.md`](https://github.com/alanyoshida/webcontainerui/blob/main/AGENTS.md) do repositório.

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `backend/` | Portal em FastAPI (Python 3.12 ou superior) |
| `frontend/` | Interface em React com Vite |
| `agent-images/` | Dockerfiles das imagens de agente e capas padrão |
| `deploy/` | Composições de desenvolvimento e de produção, e o `Caddyfile` |
| `openspec/` | Specs de comportamento e planejamento de mudanças |
| `site/` | Este site |

## Ambiente

O back-end e o front-end se instalam de forma independente.

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev,postgres]"
```

```bash
cd frontend && npm ci
```

### Subir o portal

A composição de desenvolvimento sobe o portal completo em `http://127.0.0.1:8000`, sem Caddy:

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

As credenciais de desenvolvimento e os detalhes da composição estão em [Teste local](/getting-started/local-trial/).

### Front-end com hot-reload

Com o portal no ar, rode o Vite em outro terminal:

```bash
cd frontend && npm run dev
```

Acesse `http://localhost:5173`. O Vite faz proxy de `/api`, `/i` e `/uploads` para o portal em `http://127.0.0.1:8000`, preservando a origem única em desenvolvimento.

O Caddy não é usado em desenvolvimento: `http://localhost` já é um secure context, que é o que o cliente Selkies exige para a API WebCodecs funcionar.

## Testes

### Back-end

A suíte padrão roda em SQLite, com um runtime de containers falso, e **não exige Docker**. O marcador `e2e` está desselecionado por padrão.

```bash
cd backend && .venv/bin/python -m pytest
```

Os testes e2e exigem Docker real e uma imagem webtop baixada, e sobem um PostgreSQL efêmero para cobrir o dialeto de produção:

```bash
cd backend && .venv/bin/python -m pytest -m e2e
```

Rode a suíte e2e antes de mudanças no runtime Docker, no entrypoint das imagens de agente, na injeção de identidade SSH ou no acesso a dados.

### Front-end

```bash
cd frontend && npm test
```

```bash
cd frontend && npm run build
```

`npm test` roda o Vitest em jsdom; `npm run build` gera o build de produção e serve como verificação de compilação. Os testes de navegador com Playwright ficam em `frontend/e2e/` e rodam à parte, com `npm run test:e2e`.

### Verificação manual

Para conferir uma mudança de ponta a ponta, suba a composição de desenvolvimento e verifique o catálogo, o início de uma instância e a tela de identidade SSH.

## Convenções

### Assíncrono e event loop

O portal roda com **um worker**. Em desenvolvimento, o stream de cada sessão atravessa o processo Python, então uma chamada síncrona ao Docker no caminho de uma requisição travaria o event loop de todas as sessões.

- Toda operação de Docker passa por `aiodocker`, em `backend/app/runtime/docker_runtime.py`.
- `backend/app/runtime/fake.py` implementa o mesmo protocolo e é o runtime usado pelos testes.

### Segurança

- O portal tem o socket do Docker montado, o que equivale a root no host. Não execute código de usuário dentro do processo do portal.
- Containers de instância nunca publicam porta no host.
- A verificação de dono no encaminhamento de sessão e a credencial aleatória por instância são camadas distintas; não remova nenhuma delas. Veja [Camadas de isolamento](/security/isolation-layers/).
- Comandos executados em containers por `runtime.exec` são sempre fixos no código, nunca derivados de input de usuário.
- Segredos ficam no ambiente (`WCUI_*`), nunca no repositório. O `.env` é ignorado pelo git; use `deploy/.env.example` como modelo.

### Banco de dados

O acesso a dados é SQLAlchemy Core com SQL explícito e precisa rodar igual em SQLite e PostgreSQL. As regras para timestamps, booleanos e migrações estão em [Banco de dados](/architecture/database/).

### Front-end

- Sem CSS próprio: use o tema MUI (`frontend/src/theme.js`) e a prop `sx`.
- Os testes usam `@testing-library/react` com Vitest, em arquivos `*.test.jsx` junto do componente.
- Em produção, o FastAPI serve o build de `frontend/dist`; as rotas de API têm prioridade sobre o catch-all do SPA.

### Plano de dados

O proxy in-process (`backend/app/api/session_proxy.py`) deve continuar registrado: é o caminho de desenvolvimento e da suíte de testes, e a defesa em profundidade em produção. Não reintroduza registro de atividade por mensagem trafegada. Veja [Plano de dados das sessões](/architecture/session-data-plane/).

### Imagens de agente

Uma falha de build de um agente não pode impedir os demais nem o startup do portal. Veja [Imagens de agente](/architecture/agent-images/).

## Planejamento com OpenSpec

Mudanças de comportamento são planejadas em `openspec/changes/<nome>/`, com `proposal.md`, `design.md`, um delta de spec por capability afetada e `tasks.md`. Leia as specs relevantes antes de alterar comportamento; o índice está em [Capabilities](/reference/capabilities/).

```bash
openspec status --change "<nome>"
openspec instructions apply --change "<nome>" --json
```

Depois de implementada e revisada, a change é arquivada, o que sincroniza os deltas nas specs principais:

```bash
openspec archive "<nome>"
```

As specs usam `DEVE` por requisito, com ao menos um cenário no formato WHEN/THEN.

## Commits

- Mensagens em português, no imperativo, sem prefixo de tipo, por exemplo `Adiciona tela cheia à visão de sessão`.
- Um commit por unidade de trabalho coerente. O commit de proposta (`Propõe change <nome>`) é separado do commit de implementação (`Implementa <resumo>`).
- Não commite segredos, `.env` nem bancos locais.
- Use `git add` com caminhos explícitos; evite `git add .` quando há artefatos de build ou venv no diretório.
