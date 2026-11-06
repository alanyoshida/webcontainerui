# Proposal

## Why

O stream de cada sessão atravessa o processo Python do portal, que roda com um
worker único — o teto de 10–30 sessões simultâneas é imposto por esse caminho,
não pelo banco nem pela banda. Tirar o transporte dos frames do portal (README,
"Alvo de escala", caminho de crescimento acima de ~50 sessões) eleva o limite
para o que o host comporta, sem reprojetar a autorização.

## What Changes

- O Caddy, que hoje só termina TLS, passa a ser o **plano de dados** das
  sessões: encaminha `/i/{uuid}/` (HTTP + WS) direto ao container, consultando
  o portal por `forward_auth` antes de cada requisição e da abertura de canal.
- O portal ganha um **endpoint de autorização interna** que concentra a decisão
  atual (sessão válida, dono, em execução) e devolve a credencial da instância
  em cabeçalhos para o Caddy injetar — a credencial nunca chega ao cliente.
- O portal **publica as rotas vivas** no plano de dados no ciclo de vida das
  instâncias (criar, iniciar, parar, excluir): uma rota por instância com o
  `container_name:porta` do catálogo.
- A detecção de ociosidade é preservada com sinal novo: a visão de sessão
  emite **heartbeat** enquanto está aberta, junto dos toques do endpoint de
  autorização — o portal continua sem persistir atividade por mensagem.
- O proxy interno do portal (`/i/{uuid}/` via FastAPI) **continua existindo**
  para dev e testes; em produção ele fica sombreado pelo roteamento da borda —
  não há modo de configuração.
- **BREAKING (deploy)**: o Caddyfile muda de formato (rotas dinâmicas por
  instância) e o container do Caddy passa a precisar do volume de rotas e do
  acesso de rede aos containers — já na `wcui_net`.

## Capabilities

### New Capabilities

- `stream-data-plane`: o transporte do tráfego de sessão por um proxy externo
  em produção — decisão de autorização prévia no portal, injeção de credencial,
  publicação de rotas no ciclo de vida, preservação da detecção de ociosidade
  e manutenção do caminho in-process para desenvolvimento.

### Modified Capabilities

Nenhum requisito de `session-proxy` muda: autorização, injeção de credencial,
transporte bidirecional, sessões longas e porta do catálogo continuam valendo
como comportamento do sistema — muda o componente que transporta.

## Impact

- **Backend**: novo endpoint interno em `api/session_proxy.py` (ou módulo
  próprio); hooks de publicação de rota em `services/instances.py` (ciclo
  criar/iniciar/parar/excluir/recriar); nada muda no contrato das rotas
  existentes.
- **Frontend**: heartbeat throttled na visão de sessão (novo módulo + teste).
- **Deploy**: `deploy/Caddyfile` (snippets importados, `forward_auth`,
  timeouts), `deploy/docker-compose.yml` (volume compartilhado de rotas,
  `caddy reload`), sem imagem nova do Caddy.
- **Segurança**: o endpoint de autorização interna não pode ser alcançável
  pela borda; a superfície do Caddy cresce (ele agora alcança os containers)
  — coberto em `deploy/SECURITY.md`.
- **Testes**: unitários do endpoint e do publicador de rotas; e2e valida a
  recusa sem portal; verificação manual do stack de produção com Caddy.
