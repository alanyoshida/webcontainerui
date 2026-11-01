# Tasks

## 1. Emissor

- [ ] 1.1 Criar `backend/app/services/audit_log.py` (`audit(event, **fields)` com campos convencionais `actor_id/actor_email/ip/target/outcome/detail`, linha JSON, logger `wcui.audit`) e configurar o handler no lifespan de `main.py` — testes unitários: linha JSON parseável, campos presentes, `ensure_ascii=False`, propagate desligado
- [ ] 1.2 Teste de contrato de segredos: fixture `caplog` no logger `wcui.audit` e asserção de que valor de senha, token de sessão e valor de env MCP não aparecem em nenhum evento emitido pelas rotas cobertas — verificado na suíte de rotas (grupos 2-4)

## 2. Autenticação

- [ ] 2.1 Emitir `auth.login` (desfecho success/failure, e-mail tentado, IP), `auth.login.throttled` (e-mail tentado, IP, sem verificação de credencial) e `auth.logout` em `backend/app/api/auth.py` — testes: login ok/falha/recusado/logout produzem os eventos correspondentes com campos corretos

## 3. Administração

- [ ] 3.1 Emitir eventos admin em `api/admin.py`, `api/access_control.py`, `api/images.py` (criar/desabilitar imagem, upload de capa), `api/agents_md.py`, `api/mcp_servers.py`, `api/agent_skills.py` — testes: uma operação representativa de cada família produz evento com ator=admin, alvo e desfecho
- [ ] 3.2 Emitir `admin.user.disabled` incluindo a revogação de sessões como detail, em `api/admin.py` — teste: desabilitar usuário emite o evento com ator/alvo

## 4. Instâncias e verificação

- [ ] 4.1 Emitir `instance.created/stopped/deleted/failed` em `api/instances.py` + `services/instances.py` (falha de provisionamento), com ator=dono e alvo=instância — testes com o runtime falso cobrindo os quatro eventos
- [ ] 4.2 Documentar em `deploy/SECURITY.md` o formato (linha JSON, campos, nomes de evento) e como coletar/rotacionar (`docker logs`, driver json-file) — conferência: exemplo de linha do doc bate com o emitido
- [ ] 4.3 Rodar suíte backend (`pytest`) e front (`npm test && npm run build`) verdes; contra o stack dev, gerar um evento de cada família e mostrar as linhas coletadas via `docker logs deploy-portal-1`
