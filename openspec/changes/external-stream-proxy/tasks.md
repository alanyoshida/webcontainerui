# Tasks

## 1. Endpoint de autorização interna

- [x] 1.1 Criar endpoint interno (ex. `POST /internal/data-plane/authorize`) que valida o segredo do plano de dados (`WCUI_DATA_PLANE_SECRET` em `config.py`), executa a tríade sessão/dono/`running` e responde 200 com `Authorization` da instância em header — recusas 401/404/409 como hoje; verificar `pytest tests/ -k authorize` (testes novos: segredo ausente/errado, dono errado, não-running, sucesso com credencial correta)
- [x] 1.2 Registrar o `tracker.touch(instance_id)` nas decisões aprovadas e garantir que o endpoint não aparece no schema público nem no catch-all do SPA; verificar `pytest -k "docs or spa"` e inspeção da resposta do `/openapi.json` (se habilitado) e do catch-all

## 2. Publicação de rotas no ciclo de vida

- [x] 2.1 Criar o publicador de rotas: escreve `deploy/caddy-routes/<instance_id>.caddy` com o par `container_name:porta_do_catálogo`, remove o arquivo ao parar/excluir e dispara `caddy reload` via `runtime.exec` fixo no container do Caddy (idempotente, serializado); verificar teste unitário com runtime fake cobrindo criar/iniciar/parar/excluir/recriar e reload após cada transição
- [x] 2.2 Ligar o publicador às transições de `services/instances.py` (pós-start e stop/delete/recreate) e ao startup (instâncias vivas); verificar `pytest tests/ -k instances` verde e presença do arquivo de rota nos fixtures de ciclo de vida

## 3. Borda: Caddyfile e composição

- [x] 3.1 Reescrever `deploy/Caddyfile`: site com headers atuais + `import /etc/caddy/caddy-routes/*.caddy` + rota `/i/*` com `forward_auth` (portal, header do segredo, `copy_headers Authorization`, falha fechada) e transport 3600s; verificar `caddy validate` no container e que `/` e `/api/*` seguem para o portal
- [x] 3.2 Atualizar `deploy/docker-compose.yml`: volume compartilhado `caddy-routes` montado no portal e no Caddy, `WCUI_DATA_PLANE_SECRET` nos dois serviços (gerada no `install.sh`/`.env.example`); verificar `docker compose config` válido
- [x] 3.3 Atualizar `deploy/SECURITY.md` (superfície do plano de dados, segredo compartilhado) e `deploy/README.md` (novo volume, resolução de problemas de reload); verificar revisão dos passos contra a composição real

## 4. Heartbeat de atividade no front-end

- [x] 4.1 Adicionar endpoint autenticado de heartbeat (dono da instância, toca o tracker) no backend com teste de autorização e throttle; verificar `pytest tests/ -k heartbeat`
- [x] 4.2 Emitir o heartbeat throttled (1×/min) da visão de sessão enquanto montada, parando ao desmontar; verificar `cd frontend && npm test -k heartbeat` e sessão aberta no dev stack sem ser reaped pela janela de ociosidade curta

## 5. Equivalência e verificação de ponta a ponta

- [x] 5.1 Testes de integração do par endpoint + publicador com runtime fake simulando o Caddy (consulta com segredo, recusa sem aprovação, credencial no header encaminhado); verificar `pytest tests/ -k data_plane`
- [x] 5.2 Estender a suíte e2e: recusa com portal parado (nada encaminhado) e sessão funcional pelo caminho in-process (dev); verificar `cd backend && .venv/bin/python -m pytest -m e2e`
- [x] 5.3 Verificação manual no stack de produção local (domínio de teste): sessão de desktop e CLI de agente funcionam via Caddy sem frames no portal (log do portal limpo durante tráfego), recusa com portal parado, rota retirada ao parar instância; registrar o resultado na task — resultado: CLI ttyd (GET 200, `/token` 200, WS 101 com subprotocolo `tty`) e desktop Selkies (GET 200) servidos pelo Caddy; portal só registrou `/internal/data-plane/authorize` (nenhum `/i/`); portal parado ⇒ 502 sem encaminhar; parar as instâncias removeu as duas rotas. Achado corrigido: o `forward_auth` herdava os headers de upgrade e tentava WS contra o endpoint interno (403) — snippet agora remove `Upgrade`/`Connection`/`Sec-WebSocket-*` da subrequisição.

## 6. Documentação

- [x] 6.1 Atualizar `README.md` (diagrama da arquitetura com o plano de dados, alvo de escala) e `AGENTS.md` (boas práticas: plano de dados, segredo, publicação de rotas); verificar consistência com comandos e nomes reais

## Workflow follow-up

- Rodar `openspec validate external-stream-proxy --strict` antes do commit de implementação
- Arquivar com `openspec archive "external-stream-proxy"` após revisão
