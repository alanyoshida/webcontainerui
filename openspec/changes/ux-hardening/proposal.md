# Proposal

## Why

A auditoria de UX (16 screenshots capturados via Playwright, análise por especialistas) encontrou falhas estruturais: a TopBar sem colapso responsivo faz o layout mobile explodir para 611px (shrink-to-fit a 0.61x, cliques interceptados, conteúdo minúsculo); 5 ações destrutivas executam sem confirmação — inclusive desabilitar a própria conta e disparar rebuild caro de imagem; a ação principal da home ("Abrir sessão") fica abaixo da dobra; 8 abas horizontais admin misturam domínios sem hierarquia; e a identidade visual é a default do MUI (sem fontes carregadas, ícones Material genéricos, tema light fixo).

## What Changes

- **TopBar redesenhada**: à esquerda, botão "Administração" que abre menu com as seções internas (somente para admins; não aparece para usuário comum); à direita, seletor de tema e avatar com iniciais que abre o menu do usuário (e-mail no cabeçalho, Identidade SSH, Sair). Em telas pequenas o e-mail sai da barra e a barra deixa de transbordar.
- **Console administrativo reestruturado**: as 8 abas horizontais viram seções navegáveis com endereço próprio e título da página igual à seção selecionada (ex.: "MCP").
- **Confirmação para toda ação destrutiva**: parar instância, desabilitar usuário (com recusa de auto-desabilitação), excluir grupo, desabilitar imagem, vincular/desvincular skill (avisando do rebuild) e remover servidor MCP passam a exigir diálogo de confirmação com o impacto descrito.
- **Home com card "Em execução agora"**: resumo fixo das instâncias rodando, com atalhos diretos, logo abaixo do cabeçalho — sem depender de rolagem.
- **Listagem de instâncias responsiva**: em telas estreitas a tabela compacta para não transbordar (coluna de ações sempre alcançável).
- **Sessão ocupa a área disponível**: o conteúdo do terminal/desktop negocia dimensionamento via parâmetro na URL do iframe, com fallback cosmético (centralização e fundo coerente com o tema) quando não suportado.
- **Temas light, dark e pastel**: dark carvão como padrão na primeira visita, persistência local e seletor próprio na TopBar; pastel com primário pêssego.
- **Tipografia e ícones próprios**: Inter para texto, JetBrains Mono para chaves SSH, referências de imagem e saídas técnicas; ícones Lucide substituindo os Material.
- **Feedback e estados vazios no console**: alterações de vínculo (AGENTS.md, Skills, MCP) confirmam visualmente o salvamento; seções que dependem de seleção instruem o que fazer antes da primeira escolha.

## Capabilities

### New Capabilities

- `theming`: identidade visual do portal — três temas (light, dark carvão, pastel pêssego), tema padrão dark, persistência da escolha, seletor na TopBar, tipografia Inter/JetBrains Mono e conjunto de ícones Lucide.
- `app-shell`: a moldura visível do portal — TopBar (menu "Administração" à esquerda para admins, avatar com menu do usuário à direita, seletor de tema), navegação entre seções administrativas como páginas com título próprio, feedback visível de alterações de dados e estados vazios instrutivos.

### Modified Capabilities

- `desktop-instances`: parar instância passa a exigir confirmação; a listagem ganha apresentação compacta em telas estreitas; a home ganha o resumo "Em execução agora" com atalhos.
- `session-view`: a área da sessão passa a negociar o dimensionamento do conteúdo embutido e a preencher o espaço disponível, com fallback cosmético.
- `user-management`: o sistema passa a recusar a auto-desabilitação e a exigir confirmação ao desabilitar uma conta.
- `image-catalog`: desabilitar uma entrada passa a exigir confirmação com o impacto descrito.
- `agent-skills`: vincular/desvincular skill passa a exigir confirmação explícita antes de disparar o rebuild.
- `mcp-servers`: remover um servidor MCP passa a exigir confirmação citando o efeito imediato nas instâncias vivas.

## Impact

- **Frontend** (React + MUI): `theme.js` (multi-tema), `TopBar.jsx` (redesenho completo), `AdminPage.jsx` (abas → seções com rotas), todos os painéis admin (diálogos, feedback), `HomePage`/`InstancesSection` (card de execução, listagem responsiva), `InstanceSession`/`InstanceSessionView` (dimensionamento), `SshIdentityPage` (fonte mono).
- **Backend** (FastAPI): recusa de auto-desabilitação no endpoint de desabilitar usuário; demais mudanças são de apresentação.
- **Novas dependências frontend**: `@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`, `lucide-react`; uso de `@mui/icons-material` substituído progressivamente.
- **Sem mudança de API pública** exceto a recusa de auto-desabilitação (mesma rota, novo código de erro).
- **Sem migração de banco.**
