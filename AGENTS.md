# AGENTS.md

Instruções para agentes de código trabalhando neste repositório.

## Visão geral

Portal multiusuário para desktops Linux (webtop) e agentes de código em CLI
dentro do navegador. Stack: **FastAPI** (backend, Python 3.12), **React + Vite**
(frontend), **SQLite** (persistência, volume `/data`), **Docker** (instâncias
são containers na rede interna `wcui_net`).

Documentação de produto e planejamento vivem em `openspec/`. Leia os specs
relevantes antes de mudar comportamento — o `openspec show <capability>`
mostra o contrato atual de cada capability.

## Subir o sistema

### Desenvolvimento (sem Caddy)

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

Sobe só o portal (`http://127.0.0.1:8000`). O front-end roda fora da
composição, em outro terminal:

```bash
cd frontend && npm run dev
```

Acesse `http://localhost:5173` (o Vite faz proxy de `/api`, `/i` e `/uploads`
para o portal — origem única em dev). Login dev: `admin@local.test` /
`senha-admin-dev-123456`.

### Produção

```bash
cd deploy
export WCUI_DOMAIN=desktop.seu-dominio.test
export WCUI_ADMIN_EMAIL=admin@seu-dominio.test
export WCUI_ADMIN_PASSWORD="senha com pelo menos 12 caracteres"
docker compose up -d --build
```

Caddy termina TLS na frente. O portal não publica porta — só o Caddy expõe
80/443.

### Variáveis obrigatórias

| Variável | Uso |
|---|---|
| `WCUI_DOMAIN` | Domínio público (só na composição de produção) |
| `WCUI_ADMIN_EMAIL` | E-mail do primeiro administrador |
| `WCUI_ADMIN_PASSWORD` | Senha inicial (mínimo 12 caracteres) |
| `WCUI_SSH_KEY_ENCRYPTION_KEY` | Chave Fernet que cifra as chaves SSH em repouso |

Para gerar a chave Fernet:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Derrubar / limpar

```bash
cd deploy && docker compose -f docker-compose.dev.yml down    # preserva volumes
cd deploy && docker compose -f docker-compose.dev.yml down -v # apaga volumes (CUIDADO)
```

## Testar

### Backend

```bash
cd backend && .venv/bin/python -m pytest        # suíte padrão (sem Docker)
cd backend && .venvv/bin/python -m pytest -m e2e  # suíte e2e (exige Docker real)
```

Instalação do venv:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

### Frontend

```bash
cd frontend && npm test       # vitest (jsdom)
cd frontend && npm run build  # build de produção (verifica compilação)
```

### E2E e verificação manual

Os testes `e2e` exigem Docker real e uma imagem webtop baixada. Use-os antes
de mudanças no runtime Docker, no entrypoint das imagens de agente ou na
injeção de identidade SSH. Para verificação manual, suba o dev stack e
confira o catálogo, o início de instância e a tela de identidade SSH.

## Boas práticas

### Assíncrono e event loop

- O portal roda com **um worker**. O stream de cada sessão atravessa o
  processo Python — **nunca** faça chamada síncrona ao Docker no caminho de
  request (travaria o event loop de todas as sessões).
- Toda operação de Docker passa por `aiodocker`
  (`backend/app/runtime/docker_runtime.py`). Runtime alternativo para
  testes: `backend/app/runtime/fake.py` implementa o mesmo protocolo.

### Segurança

- O portal tem o socket do Docker montado — **equivale a root no host**.
  Não execute código de usuário dentro do processo do portal.
- Containers de instância **nunca publicam porta no host**. O isolamento
  entre usuários é topológico (rede interna), não só checagem de dono.
- A verificação de dono no proxy de sessão (`/i/{uuid}/`) é a segunda
  camada; a credencial aleatória por instância é a terceira. Não remova
  nenhuma delas.
- Segredos ficam no ambiente (`WCUI_*`), nunca no repositório. `.env` é
  ignorado pelo git; use `.env.example` como modelo.
- A chave privada SSH de cada usuário é cifrada em repouso (Fernet). O
  portal nunca recebe nem armazena chave privada pré-existente — só gera.
- Antes de expor o portal além da própria máquina, leia `deploy/SECURITY.md`.

### Banco e migrações

- SQLite em `/data/webcontainerui.db` (volume nomeado). WAL ligado,
  `busy_timeout` 5s, `foreign_keys` ligado.
- Migrações são idempotentes e rodam em `init_db` (`backend/app/db.py`), no
  padrão `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` guardado por
  `PRAGMA table_info`. Siga esse padrão para coluna nova.
- **Antes de aplicar migração de schema em produção**, faça backup do
  arquivo SQLite (ver `deploy/README.md`, seção "Reversão").

### Frontend

- Sem CSS próprio: tema MUI (`frontend/src/theme.js`) e prop `sx`.
- Testes usam `@testing-library/react` + `vitest` (jsdom). Siga o padrão
  dos testes existentes (`*.test.jsx` junto do componente).
- O Vite faz proxy de `/api`, `/i` e `/uploads` em dev. Em produção o
  FastAPI serve o build de `frontend/dist` — rotas de API têm prioridade
  sobre o catch-all do SPA.

### Imagens de agente

- Cada agente tem um Dockerfile em `agent-images/<agente>/`, partindo de
  `wcui-agent-base` (ttyd + entrypoint comum). A base é construída e
  marcada antes dos agentes pelo seed (`seed_agent_images`).
- O hash do contexto de build (`agent_images.py`) cobre só `_base` e o
  subdiretório do agente. Mudança em `agent-images/covers/` **não** dispara
  rebuild.
- Falha de build de um agente não impede os demais nem o startup do portal.
  Mantenha esse isolamento.

### Documentos AGENTS.md

- A biblioteca de textos vive em `agent_md_documents`, com vínculo
  `0..1` por entrada do catálogo (`images.agents_md_id`); CRUD admin em
  `/api/admin/agents-md`.
- O documento é injetado como `/config/AGENTS.md` na criação da instância
  (best-effort, junto da identidade SSH) e propagado às instâncias vivas
  quando o admin salva o texto ou o vínculo.
- Desvincular remove o arquivo de fato das instâncias vivas via
  `runtime.exec` — operação do protocolo `ContainerRuntime` (implementada
  com `docker exec`). O comando é sempre fixo no código do portal, nunca
  derivado de input de usuário.

### OpenSpec (planejamento)

- Changes ficam em `openspec/changes/<nome>/` com `proposal.md`, `design.md`,
  `specs/<capability>/spec.md` (delta) e `tasks.md` (checkboxes rastreáveis).
- Antes de implementar uma change: rode `openspec status --change "<nome>"`
  e `openspec instructions apply --change "<nome>" --json` para carregar o
  contexto e a lista de tarefas.
- Marque cada checkbox `- [ ]` → `- [x]` na linha exata que o CLI reporta,
  imediatamente após completar a tarefa.
- Após implementar e revisar, arquive com `openspec archive "<nome>"` —
  o comando sincroniza os deltas nas specs principais.
- Escreva specs com `DEVE` (português) ou `SHALL/MUST` (inglês) por
  requisito, com pelo menos um `#### Scenario:` em formato WHEN/THEN.

### Commits

- Mensagens de commit em português, no imperativo, sem prefixo de tipo:
  `Adiciona tela cheia à visão de sessão`,
  `Corrige formato inconsistente de last_seen_at`.
- Um commit por unidade de trabalho coerente. Commit de proposta
  (`Propõe change <nome>`) separado do commit de implementação
  (`Implementa <resumo>`).
- Não commite segredos, `.env` ou bancos locais (`.gitignore` cobre).
- Use `git add` explícito nos caminhos; evite `git add .` quando há
  artefatos de build ou venv no diretório.