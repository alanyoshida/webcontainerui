# Design

## Context

O frontend usa MUI 6 com tema único em `frontend/src/theme.js` (`mode: "light"` fixo) e a convenção do repo é "sem CSS próprio: tema MUI e prop `sx`". A TopBar atual (`TopBar.jsx`) coloca logo, Identidade SSH, Administração, e-mail e Sair numa única `Toolbar` flex sem tratamento de largura mínima — medido em emulação mobile, o conteúdo mínimo dela é 611px, o que força shrink-to-fit e quebra todo o layout em telas estreitas (ver conversa de exploração). O console admin usa 8 abas em estado local dentro de `AdminPage.jsx`, sem endereço por seção. Ícones vêm de `@mui/icons-material`; nenhuma fonte é carregada (o MUI cai no sans do sistema). Motivação completa em proposal.md.

## Goals / Non-Goals

**Goals:**

- Única fonte de estilo continua sendo o tema MUI: os três temas nascem de `buildTheme(mode)` no `theme.js`.
- TopBar estruturada em zonas (esquerda/centro/direita) que nunca exceda a viewport.
- Console admin navegável por endereço, com título por seção.
- Diálogo de confirmação único e reutilizável para as 6 ações destrutivas.
- Fontes e ícones self-hosted (funciona offline).

**Non-Goals:**

- Suporte a touch para a sessão ttyd (teclas auxiliares Ctrl/Esc/setas) — desktop-first.
- Detecção de desconexão da sessão após o iframe carregar.
- Fingerprint SHA256 da chave SSH.
- Reescrita dos painéis além do que as specs exigem.

## Decisions

**D1 — Temas via `buildTheme(mode)` + ThemeModeContext.** `theme.js` exporta `buildTheme("light" | "dark" | "pastel")` e um `ThemeModeProvider` (contexto React) guarda o modo, inicializado de `localStorage` (chave `wcui.theme`), com dark como fallback quando não há escolha. Alternativas rejeitadas: CSS variables fora do MUI (violaria a convenção do repo); seguir `prefers-color-scheme` (decisão de produto foi dark fixo como padrão). Paletas: light = atual; dark = carvão (`#121417` fundo, superfícies `#1a1d21`, primary clareado); pastel = fundo creme suave, primário pêssego dessaturado, `borderRadius` 16 e sombras mais suaves.

**D2 — Fontes self-hosted com @fontsource.** `@fontsource-variable/inter` e `@fontsource-variable/jetbrains-mono` entram como dependências npm e são importadas no `theme.js`/`main.jsx`; o Vite empacota os woff2. Alternativa rejeitada: Google Fonts CDN (portal deve funcionar sem internet; já é requisito das instâncias rodarem em rede interna). `typography.fontFamily` aponta para Inter; JetBrains Mono é aplicada por `fontFamily` pontual em chave SSH, referência de imagem e colunas técnicas.

**D3 — Ícones Lucide.** `lucide-react` substitui `@mui/icons-material` em toda a interface (a spec exige conjunto único). Os componentes Lucide renderizam SVG compatível com `startIcon`/`ListItemIcon`; tamanho padrão 20-24 alinhado por prop. Task de varredura garante zero imports de `@mui/icons-material` ao final. Alternativa rejeitada: manter Material (estética "genérica" foi parte do problema) ou Phosphor duotone (usuário escolheu o combo A, traço).

**D4 — TopBar em três zonas.** Esquerda: botão "Administração" (`Button` + seta, abre `Menu` com as 8 seções) renderizado só para admins. Centro: logo (flexGrow). Direita: seletor de tema (`IconButton` + `Menu` com Light/Dark/Pastel) e botão-avatar (iniciais derivadas do e-mail — primeira letra da parte local + primeira letra do domínio, maiúsculas — com chevron) abrindo o menu do usuário (cabeçalho com e-mail, Identidade SSH, Sair). Em `breakpoints.down("sm")`: e-mail já vive só no menu (nunca ficou solto na barra), rótulos encurtam, e os filhos da Toolbar recebem `minWidth: 0`/`noWrap` para que a barra nunca ultrapasse a viewport — corrigindo a causa-raiz dos 611px.

**D5 — Seções admin como rotas.** Rotas `/admin/usuarios`, `/admin/grupos`, `/admin/catalogo`, `/admin/agents-md`, `/admin/skills`, `/admin/mcp`, `/admin/acessos`, `/admin/metricas`; `/admin` redireciona para `/admin/usuarios`. `AdminPage` vira layout com `<Outlet/>`; cada seção é um wrapper que renderiza o painel existente sob um `Typography h4` com o nome da seção. Alternativa rejeitada: query param `?tab=` (endereço por path é mais limpo e atende "endereço próprio" da spec sem ambiguidade). Bookmarks antigos de `/admin` continuam funcionando via redirect.

**D6 — `ConfirmDialog` compartilhado.** Um componente único (título, descrição com impacto, rótulos, estado de busy, botão de confirmação `color="error"` `variant="contained"`) replica o padrão já existente em `AccessPanel` (impacto contável). Usado por: parar instância (tabela e visão de sessão), desabilitar usuário, excluir grupo, desabilitar imagem, vínculo/desvínculo de skill (texto informa o rebuild), remover servidor MCP (texto informa propagação imediata). Os diálogos existentes de excluir instância e regenerar SSH migram para ele por consistência.

**D7 — Auto-desabilitação recusada em duas camadas.** Backend: o endpoint de desabilitar compara `requester.id == target.id` e recusa com erro de conflito claro. Frontend: a própria linha não renderiza a ação. A camada de API é a garantia; a de UI, a cortesia.

**D8 — Card "Em execução agora".** Novo componente no topo da `HomePage`, sempre presente: lista compacta das instâncias `running` com atalho "Abrir sessão", ou a mensagem de que não há nenhuma em execução. Acima do catálogo, dentro da primeira dobra em qualquer viewport desktop.

**D9 — Listagem responsiva.** Em `xs`: coluna "Referência" oculta (`display: { xs: "none" }`), ações viram `IconButton` com `Tooltip` (também melhora o alvo de toque), e o `TableContainer` permanece como válvula de escape com scroll interno se o nome da imagem for longo. O documento em si nunca rola horizontalmente (depende do D4).

**D10 — Dimensionamento da sessão.** O `src` do iframe passa a incluir parâmetro de dimensionamento (`/i/{id}/?resize=scale`, aceito pelo ttyd dos agentes; query atravessa o proxy sem mudança de backend). Para conteúdos que ignoram o parâmetro (Selkies/webtop), a caixa externa centraliza o iframe com fundo escuro de terminal (fixo, independente do tema, pois o conteúdo embutido é escuro), eliminando a aparência de faixa morta. Risco de comportamento variável do parâmetro entre versões do ttyd é coberto pelo fallback.

**D11 — Feedback e estados vazios.** Alterações de vínculo (AGENTS.md/Skills/MCP) exibem snackbar de sucesso/erro dispara a partir dos handlers existentes. A seção de acessos ganha instrução fixa sob o seletor enquanto nenhum grupo estiver escolhido. Pluralização "1 imagem / N imagens" corrigida nos três painéis de vínculo.

## Risks / Trade-offs

- [Regressão da Toolbar em larguras intermediárias] → verificação manual nos breakpoints 320/375/768/1024/1440 após a mudança (roteiro de screenshots já existente desta exploração).
- [Lucide sem equivalente para algum ícone em uso] → checagem da lista de imports de `@mui/icons-material` antes da troca; nomes Lucide são correspondentes próximos em todos os casos atuais (Image, Visibility, Delete...).
- [`?resize=scale` variável entre versões do ttyd] → fallback cosmético é obrigatório e independe do parâmetro; verificação manual e2e com imagem de agente e webtop.
- [Cores fixas em `sx` de painéis contradizem o tema dark/pastel] → varredura por hex hardcoded nos componentes tocados; substituição por tokens da paleta.
- [Confirmação extra em parar/vincular adiciona fricção] → decisão consciente de produto (consistência: todo botão vermelho confirma); diálogos com botão de confirmação focado e `Enter` confirmar.
- [Mudança de comportamento na API de desabilitar] → único ponto de API afetado; erro claro orientará quem usava auto-desabilitação por API direta.

## Migration Plan

Sem migração de banco. Deploy padrão (`docker compose up -d --build`). Rollback: `git revert` do commit de implementação e rebuild — nenhuma mudança de dados ou schema.

## Open Questions

Nenhum bloqueante. O comportamento exato de `?resize=scale` na imagem webtop (Selkies) será observado na verificação manual e2e; o fallback cosmético já cobre o pior caso.
