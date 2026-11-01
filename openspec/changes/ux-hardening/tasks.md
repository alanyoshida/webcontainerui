# Tasks

## 1. Backend: recusa de auto-desabilitação

- [ ] 1.1 Em `POST /api/admin/users/{id}/disable`, recusar com erro de conflito quando o alvo é o próprio administrador autenticado; adicionar teste pytest cobrindo a recusa e o caso normal de desabilitar outro usuário. **Verificar:** `cd backend && .venv/bin/python -m pytest`

## 2. Diálogo de confirmação reutilizável

- [ ] 2.1 Criar `ConfirmDialog` compartilhado no padrão do `AccessPanel` (título, impacto, botão de confirmação `color="error"` `variant="contained"`, estado de busy, foco no cancelar) com teste vitest de render, confirmação e busy. **Verificar:** `cd frontend && npm test`
- [ ] 2.2 Parar instância exige confirmação na tabela (`InstanceTableRow`) e na visão de sessão (`InstanceSessionView`), com texto "processos são interrompidos; arquivos permanecem salvos". **Verificar:** teste vitest de que a ação só dispara após confirmar
- [ ] 2.3 Desabilitar usuário exige diálogo com o e-mail da conta, e a própria linha do admin logado não oferece a ação (além da recusa do backend 1.1). **Verificar:** teste vitest
- [ ] 2.4 Excluir grupo (`GroupsPanel`) com diálogo citando o número de membros. **Verificar:** teste vitest
- [ ] 2.5 Desabilitar imagem (`ImagesPanel`) com diálogo descrevendo a retirada da oferta. **Verificar:** teste vitest
- [ ] 2.6 Vínculo/desvínculo de skill (`SkillsPanel`) com diálogo informando que um build será disparado; checkbox só reflete estado após confirmação. **Verificar:** teste vitest
- [ ] 2.7 Remover servidor MCP (`McpServersPanel`) com diálogo informando propagação imediata às instâncias vivas. **Verificar:** teste vitest
- [ ] 2.8 Migrar os diálogos existentes (excluir instância em `InstanceTableRow`/`InstanceSessionView`, regenerar SSH) para `ConfirmDialog`, preservando os textos atuais. **Verificar:** testes existentes seguem verdes

## 3. Console administrativo em seções

- [ ] 3.1 Rotas `/admin/usuarios`, `/admin/grupos`, `/admin/catalogo`, `/admin/agents-md`, `/admin/skills`, `/admin/mcp`, `/admin/acessos`, `/admin/metricas` com redirect de `/admin`; cada seção renderiza seu painel atual sob título `h4` com o nome da seção (ex.: "MCP"). **Verificar:** teste vitest de rota/título e de recarregar mantendo a seção
- [ ] 3.2 Snackbar de confirmação (sucesso) e alerta de erro distintos nas alterações de vínculo de AGENTS.md, Skills e MCP. **Verificar:** teste vitest
- [ ] 3.3 Instrução fixa na seção Acessos enquanto nenhum grupo está selecionado; pluralização correta "1 imagem / N imagens" nos três painéis de vínculo. **Verificar:** teste vitest

## 4. Home e listagem de instâncias

- [ ] 4.1 Card "Em execução agora" no topo da `HomePage` com atalho "Abrir sessão" por instância rodando e mensagem quando não há nenhuma, visível sem rolagem. **Verificar:** teste vitest
- [ ] 4.2 Listagem responsiva: coluna "Referência" oculta em `xs`, ações como `IconButton` com `Tooltip`; documento sem rolagem horizontal em 375px. **Verificar:** teste vitest + inspeção manual em 375px

## 5. Sessão

- [ ] 5.1 Adicionar parâmetro de dimensionamento ao `src` do iframe (`/i/{id}/?resize=scale`) e envolvê-lo em caixa com centralização e fundo escuro de terminal (fixo) como fallback para conteúdos que ignoram o parâmetro. **Verificar:** inspeção manual e2e com imagem de agente (ttyd) e webtop (Selkies), redimensionando a janela

## 6. Temas e tipografia

- [ ] 6.1 `buildTheme("light" | "dark" | "pastel")` em `theme.js` (dark carvão `#121417`, pastel com primário pêssego) + `ThemeModeProvider` com persistência em `localStorage` e dark como padrão sem escolha. **Verificar:** teste vitest de padrão, persistência e troca
- [ ] 6.2 Dependências `@fontsource-variable/inter` e `@fontsource-variable/jetbrains-mono`; Inter como `fontFamily` global e JetBrains Mono na chave pública SSH e nas referências de imagem. **Verificar:** `npm run build` e inspeção da chave SSH em mono
- [ ] 6.3 Varredura de cores fixas (hex em `sx`) nos componentes tocados, substituindo por tokens da paleta; conferir que gráficos das métricas seguem o tema ativo. **Verificar:** inspeção visual nos 3 temas

## 7. TopBar e navegação do shell

- [ ] 7.1 TopBar em zonas: à esquerda botão "Administração" (somente admins) abrindo menu com as 8 seções; logo ao centro; à direita seletor de tema (menu Light/Dark/Pastel) e botão-avatar com iniciais + chevron abrindo menu com e-mail no cabeçalho, Identidade SSH e Sair. **Verificar:** teste vitest (admin vê, usuário comum não vê o botão; itens corretos em cada menu)
- [ ] 7.2 Responsividade da TopBar: em telas estreitas o e-mail sai da barra (permanece no menu), rótulos encurtam e a barra nunca excede a viewport (sem shrink-to-fit). **Verificar:** inspeção manual em 375px (sem rolagem horizontal do documento)

## 8. Ícones

- [ ] 8.1 Adicionar `lucide-react`, substituir todos os imports de `@mui/icons-material` pelos equivalentes Lucide e remover a dependência antiga do `package.json`. **Verificar:** `grep` sem imports de `@mui/icons-material` + `npm run build` + `npm test`

## 9. Verificação integrada

- [ ] 9.1 Suíte frontend verde e build de produção OK. **Verificar:** `cd frontend && npm test && npm run build`
- [ ] 9.2 Suíte backend verde. **Verificar:** `cd backend && .venv/bin/python -m pytest`
- [ ] 9.3 Verificação manual multi-tema: roteiro de screenshots (Playwright, login admin dev) das telas login, home, sessão, identidade SSH e 8 seções admin nos 3 temas, nos breakpoints 320/375/768/1024/1440, entregues em pasta para revisão. **Verificar:** pasta de screenshots revisada sem sobreposição, contraste ilegível ou rolagem horizontal

## Workflow follow-up

- Commits por unidade coerente (pt-BR, imperativo): backend, diálogos, seções admin, home/listagem, sessão, temas, TopBar, ícones — ver AGENTS.md.
- Após revisão e implementação completa, arquivar com `openspec archive ux-hardening` (sincroniza os deltas nas specs principais).
