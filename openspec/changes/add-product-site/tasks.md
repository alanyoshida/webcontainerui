# Tasks

## 1. Estrutura do projeto do site

- [x] 1.1 Criar `site/` com Astro + Starlight (`package.json`, lockfile, `astro.config.mjs` com `site` e `base` lidos de variáveis de ambiente com padrão `https://alanyoshida.github.io` e `/webcontainerui`) e verificar que `cd site && npm ci && npm run build` termina sem erro
- [x] 1.2 Configurar os locales (inglês como `root`, `pt-br` como segundo) e a barra lateral com as seções `getting-started`, `architecture`, `security`, `operations` e `reference`; verificar com uma página provisória por idioma que `/webcontainerui/getting-started/...` e `/webcontainerui/pt-br/getting-started/...` existem em `dist/` e que o seletor de idioma leva de uma à outra
- [x] 1.3 Criar `src/pages/index.astro` e `src/pages/pt-br/index.astro` provisórias e verificar que o build gera `dist/index.html` e `dist/pt-br/index.html` a partir delas, sem colisão com as rotas do Starlight; se colidir, adotar o plano B de D2 e registrar a troca no `design.md`
- [x] 1.4 Adicionar `site` ao `.dockerignore` e `site/node_modules`, `site/dist` e `site/.astro` ao `.gitignore` se ainda não cobertos; verificar com `git status` que nenhum artefato de build aparece como não rastreado após um build

## 2. Integridade: traduções e links

- [x] 2.1 Estender o schema de docs para aceitar `sourceHash` no frontmatter e escrever `site/scripts/check-translations.mjs` (modo de checagem e `--stamp <caminho>`), cobrindo páginas de docs e textos da landing; verificar com testes do script os três casos da spec: página sem tradução falha nomeando-a, origem alterada falha nomeando-a, paridade passa
- [x] 2.2 Ligar a checagem ao `npm run build` (script `prebuild` ou `check`) e verificar que alterar um arquivo pt-BR sem recarimbar faz `npm run build` sair com código diferente de zero
- [x] 2.3 Adicionar o validador de links internos do Starlight e verificar que um link proposital para página inexistente falha o build indicando página e link; remover o link de teste

## 3. Identidade visual e peças compartilhadas

- [x] 3.1 Definir os tokens de cor claro/escuro em `src/styles/` a partir de `frontend/src/theme.js`, aplicar às variáveis de tema do Starlight e fixar o escuro como padrão; verificar no navegador que uma página de docs abre em carvão `#121417` com destaque `#fb7185` e que o tema claro alterna
- [x] 3.2 Instalar Inter, JetBrains Mono e Caveat via `@fontsource`, aplicar (Caveat só na logo) e verificar na aba de rede que nenhuma fonte é requisitada a outro domínio
- [x] 3.3 Levar os logos de `docs/` e as capas de `agent-images/covers/` usadas pelo site para `src/assets/`, configurar logo claro/escuro no cabeçalho e favicon; verificar que a logo correta aparece em cada tema
- [x] 3.4 Criar o componente do diagrama de origem única em SVG inline com rótulos por idioma e cores dos tokens; verificar que renderiza legível nos dois temas e nos dois idiomas, com `title`/`desc` acessíveis

## 4. Capturas de tela

- [x] 4.1 Escrever `site/scripts/capture-screenshots.mjs` (Playwright, viewport fixo, tema escuro, login dev) que grava catálogo, visão de sessão de desktop, visão de sessão de agente e painel administrativo em `src/assets/screenshots/`; verificar rodando contra o stack de dev que os quatro arquivos são gerados
- [x] 4.2 Versionar as capturas geradas e documentar em `site/README.md` o comando e os pré-requisitos (stack de dev no ar, imagens webtop e de agente disponíveis); verificar que o comando documentado roda como escrito

## 5. Conteúdo da documentação (pt-BR, origem)

- [x] 5.1 Escrever `getting-started/` (o que é o produto, teste local, instalação com `install.sh`) a partir do `README.md`; verificar que cada comando citado existe e confere com `install.sh` e `deploy/docker-compose.dev.yml`
- [x] 5.2 Escrever `architecture/` (origem única com o diagrama de 3.4, plano de dados das sessões, banco de dados, alvo de escala, imagens de agente) a partir de `README.md` e `AGENTS.md`; verificar cada afirmação contra as specs `session-proxy`, `stream-data-plane`, `database-persistence` e `coding-agent-images`
- [x] 5.3 Conferir no código atual cada achado dos relatórios de pentest e SAST/SCA (ponto de partida: tabela de D6), registrando evidência por linha, e escrever `security/audits` com status, onde foi tratado, data e commit de cada relatório e link para o relatório completo no GitHub; verificar que nenhum achado sem evidência de correção aparece como "corrigido"
- [x] 5.4 Mover o conteúdo de `deploy/SECURITY.md` para as demais páginas de `security/` (superfície de confiança, camadas de isolamento, login e limitador, trilha de eventos), trocando nomes de changes arquivadas por links para specs; verificar que nenhum trecho do arquivo original ficou sem destino
- [x] 5.5 Mover o conteúdo de `deploy/README.md` para `operations/` (subida manual, variáveis de ambiente, backup e restauração, plano de dados, TLS e cookie, reversão, checklist pós-deploy); verificar que toda variável `WCUI_*` documentada existe em `backend/app/config.py` ou nas composições
- [x] 5.6 Escrever `reference/` com o índice das 19 capabilities (uma linha de propósito e link para a spec no GitHub) e a página de desenvolvimento e testes; verificar que a lista bate com `openspec list --specs`

## 6. Landing (pt-BR, origem)

- [x] 6.1 Implementar os componentes de seção da landing recebendo textos por prop: hero com captura, o que o portal oferece (desktops e agentes, com capas), como funciona (diagrama resumido), segurança em camadas, "o que saber antes de implantar" com o aviso de root no host, instalação e rodapé com link para o GitHub; verificar no navegador em 375px, 768px e desktop que não há estouro horizontal
- [x] 6.2 Escrever os textos da landing em português em `src/content/landing/pt-br.*` e montar `/pt-br/`; verificar que a página cita desktops Linux e agentes de código, mostra ao menos uma captura e que a seção do aviso leva à página de superfície de confiança
- [x] 6.3 Revisar acessibilidade da landing (contraste do rosa sobre carvão em texto, ordem de foco, `alt` em todas as imagens, `prefers-reduced-motion`); verificar com auditoria de acessibilidade do navegador sem erros de contraste ou de rótulo

## 7. Inglês

- [x] 7.1 Traduzir todas as páginas de docs para inglês na raiz e carimbar cada uma com `--stamp`; verificar que `check-translations` passa
- [x] 7.2 Traduzir os textos da landing para `src/content/landing/en.*`, carimbar e montar `/`; verificar que a raiz abre em inglês e que o seletor leva a `/pt-br/`
- [x] 7.3 Traduzir `alt` e legendas das capturas e os rótulos do diagrama; verificar que nenhuma página inglesa exibe texto em português fora das capturas de tela
- [ ] 7.4 Revisão humana do inglês da landing e das páginas de `security/` pelo mantenedor antes da primeira publicação; verificar pelo registro da aprovação no pull request

## 8. Documentos do repositório

- [x] 8.1 Encurtar `deploy/README.md` e `deploy/SECURITY.md` para resumo, comandos essenciais, link para a seção do site nos dois idiomas e caminho do Markdown-fonte em `site/`; verificar que nenhum dos dois mantém cópia do texto completo
- [x] 8.2 Reescrever o `README.md`: abertura citando desktops e agentes de código, aviso de segurança, instalação e teste local resumidos, links para o site em inglês e português; remover as seções migradas e a referência à change `webtop-portal`; verificar que todos os links relativos restantes resolvem
- [x] 8.3 Atualizar as referências em `AGENTS.md` (2) e `install.sh` (comentário e mensagem final) e acrescentar ao `AGENTS.md` uma seção curta sobre `site/` (comandos, regra pt-BR primeiro + `--stamp`, relatório novo em `docs/` pede atualização de `security/audits`); verificar com `grep -rn "deploy/README.md\|deploy/SECURITY.md"` que cada ocorrência restante aponta para conteúdo que ainda existe e com `bash -n install.sh` que o script segue válido

## 9. Publicação

- [x] 9.1 Criar `.github/workflows/site-check.yml` (pull requests que tocam `site/**` ou os workflows: instalar, checar traduções, build) e verificar que o workflow roda e passa no pull request desta change
- [ ] 9.2 Criar `.github/workflows/site-deploy.yml` (push em `main` nos mesmos caminhos e disparo manual; mesmos passos e publicação no Pages com permissões `contents: read`, `pages: write`, `id-token: write` e concorrência por grupo) e verificar a sintaxe com um linter de workflows ou pela aceitação do arquivo no GitHub
- [x] 9.3 Mantenedor: habilitar o GitHub Pages com origem "GitHub Actions" nas configurações do repositório antes do merge; verificar que `gh api repos/alanyoshida/webcontainerui/pages` deixa de responder 404

## 10. Verificação integrada

- [x] 10.1 Rodar `npm run build` limpo em `site/` e conferir em `npm run preview` as duas landings e uma página de cada seção nos dois idiomas, a busca por `forward_auth`, a troca de idioma preservando a página e a ausência de erros no console
- [x] 10.2 Rodar as suítes do portal (`cd backend && .venv/bin/python -m pytest` e `cd frontend && npm test && npm run build`) e verificar que seguem passando, confirmando que a change não afetou o portal
- [ ] 10.3 Após o merge, verificar que `site-deploy` publicou e que `https://alanyoshida.github.io/webcontainerui/` e `/pt-br/` respondem com o conteúdo do commit; então preencher o campo "Website" do repositório

## Workflow follow-up

- Arquivar a change com `openspec archive "add-product-site"` depois da publicação verificada, criando a spec principal `product-site`.
