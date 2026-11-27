# Design

## Context

Ver `proposal.md` para a motivação. O que condiciona a abordagem:

- O repositório é público em `github.com/alanyoshida/webcontainerui`, o Pages
  não está habilitado e não existe `.github/`. Este é o primeiro workflow.
- O conteúdo já existe em Markdown, em português: `README.md` (232 linhas,
  inclui o diagrama ASCII de origem única e o alvo de escala),
  `deploy/README.md` (253 linhas: ordem de subida, variáveis, banco, plano de
  dados, TLS, cabeçalhos, limitador de login, reversão), `deploy/SECURITY.md`
  (140 linhas) e os relatórios `docs/relatorio-pentest-2026-11-01.md` e
  `docs/relatorio-sast-sca-2026-11-01.md`.
- `deploy/README.md` e `deploy/SECURITY.md` são citados em `README.md` (2x),
  `AGENTS.md` (2x), `install.sh` (2x) e no próprio `SECURITY.md`.
- A identidade visual está em `frontend/src/theme.js`: fundo `#121417`, papel
  `#1a1d21`, primário `#fb7185` no escuro; `#f4f6f8`/`#1565c0` no claro; Inter
  e JetBrains Mono variáveis e Caveat para a logo, todas via `@fontsource`.
- Material visual disponível: `docs/logo-dark.png`, `docs/logo-light.png`,
  as capas e logos em `agent-images/covers/` e uma única captura
  (`images/agent_page.png`).
- O frontend já tem Node e Playwright (`@playwright/test`); a imagem do portal
  é construída com `node:20-alpine` e não copia nada além de `frontend/`,
  `backend/` e `agent-images/`.
- A regra "sem CSS próprio" do `AGENTS.md` vale para `frontend/`. O site é
  outro projeto e precisa de CSS próprio para a landing.

## Goals / Non-Goals

**Goals:**

- Um projeto isolado em `site/` que não toca o build, os testes nem as
  dependências do portal.
- Landing com layout livre e docs em Markdown comum, no mesmo build.
- Dois idiomas sem duplicar layout: só o texto é duplicado.
- Defasagem de tradução e link quebrado falham o build, não dependem de
  revisão humana.
- Um único lugar para cada texto longo.

**Non-Goals:**

- Reaproveitar componentes React/MUI do portal no site.
- Gerar páginas a partir das specs do OpenSpec.
- Pré-visualização por pull request (deploy de preview).
- Otimização de SEO além do que o gerador entrega por padrão (sitemap, meta
  tags, `hreflang`).

## Decisions

### D1 — Astro + Starlight em `site/`

A landing são páginas Astro livres; os docs usam o Starlight (busca local,
barra lateral, i18n, claro/escuro, `hreflang`).

- *VitePress*: docs equivalentes, mas a landing fica presa ao hero padrão ou
  exige um tema Vue inteiro.
- *MkDocs Material*: Python já está no stack, mas a landing sob medida exige
  sobrescrever templates Jinja e o resultado fica com cara de docs.
- *HTML à mão*: liberdade total na landing, porém busca, navegação e i18n dos
  docs teriam de ser escritos do zero.

`site/` tem `package.json` e `package-lock.json` próprios. Nada é compartilhado
com `frontend/` em nível de pacote.

### D2 — Estrutura de rotas e conteúdo

```
site/
  astro.config.mjs          site + base + integração Starlight
  src/
    pages/
      index.astro           landing em inglês      -> /webcontainerui/
      pt-br/index.astro     landing em português   -> /webcontainerui/pt-br/
    components/landing/     seções da landing (recebem textos por prop)
    content/
      landing/{en,pt-br}.*  textos da landing por idioma
      docs/                 páginas em inglês      -> /webcontainerui/<secao>/...
        pt-br/              páginas em português   -> /webcontainerui/pt-br/<secao>/...
    assets/                 logos, capturas, capas
    styles/                 tokens de tema e CSS da landing
  scripts/check-translations.mjs
```

O inglês é o locale `root` do Starlight; `pt-br` é o segundo locale. Não existe
`index` na coleção de docs, para a rota `/` ficar com a página Astro da
landing. As duas landings são o mesmo componente recebendo textos diferentes.

A coexistência de páginas próprias em `src/pages/` com as rotas do Starlight é
o ponto a confirmar primeiro na implementação (tarefa 1.3). Se houver colisão,
o plano B é a landing como página Starlight com `template: splash` e
componentes próprios — as URLs e o conteúdo não mudam.

Seções dos docs (mesmos slugs nos dois idiomas, para o seletor de idioma levar
à página equivalente):

| Seção | Slug | Conteúdo | Origem |
|---|---|---|---|
| Começar | `getting-started/` | o que é, teste local, instalação com `install.sh` | `README.md` |
| Arquitetura | `architecture/` | origem única, plano de dados, banco, alvo de escala, imagens de agente | `README.md`, `AGENTS.md` |
| Segurança | `security/` | superfície de confiança, camadas de isolamento, login, trilha de auditoria, auditorias e status | `deploy/SECURITY.md`, relatórios |
| Operação | `operations/` | subida manual, variáveis, backup/restauração, reversão, checklist pós-deploy | `deploy/README.md` |
| Referência | `reference/` | índice das capabilities com link para cada spec no GitHub; desenvolvimento e testes | `openspec/specs/`, `README.md` |

### D3 — Caminho base e domínio

`site: "https://alanyoshida.github.io"` e `base: "/webcontainerui"`, ambos
lidos de variáveis de ambiente com esse padrão. Todo link interno e asset
passa pelo helper de base do Astro; nenhum caminho absoluto escrito à mão.
Assim, adotar domínio próprio depois é trocar duas variáveis no workflow e
adicionar um `CNAME`, sem tocar em conteúdo. Domínio próprio fica fora desta
change.

### D4 — Português é a origem; defasagem falha o build

Toda página nasce em `content/docs/pt-br/`. A página inglesa correspondente
carrega no frontmatter `sourceHash`, o SHA-256 do arquivo pt-BR do qual foi
traduzida (o schema de docs do Starlight é estendido para aceitar o campo).

`scripts/check-translations.mjs`:

- sem argumentos: para cada página pt-BR, exige a página inglesa de mesmo
  caminho e compara o hash; lista as faltantes e as defasadas e sai com código
  diferente de zero se houver alguma;
- `--stamp <caminho>`: regrava o `sourceHash` da página inglesa depois de
  revisada a tradução.

O mesmo vale para os textos da landing. A checagem roda antes do build, local
e no CI.

- *Comparar datas de commit no git*: exige histórico completo no CI e marca
  como defasada qualquer página tocada por formatação.
- *Só avisar, sem falhar*: aviso que ninguém lê; a tradução apodrece.
- *Fallback do Starlight para página ausente*: fica ligado por segurança, mas
  como a checagem exige paridade, na prática não aparece no site publicado.

Custo assumido: corrigir uma vírgula em português obriga a reconferir e
recarimbar a página inglesa. É o preço de a versão principal do site (inglês
na raiz) nunca divergir da origem.

### D5 — Fonte única: o site é canônico para texto longo

O conteúdo de `deploy/README.md` e `deploy/SECURITY.md` é movido (não copiado)
para `operations/` e `security/`. Os dois arquivos permanecem, curtos:

- `deploy/README.md`: o que há na pasta, os dois comandos de subida e o link
  para a seção Operação do site (e o caminho do arquivo-fonte no repositório,
  para leitura offline).
- `deploy/SECURITY.md`: o parágrafo do aviso de root no host e o link para a
  seção Segurança.

`README.md` mantém aviso de segurança, instalação e teste local resumidos, e
passa a linkar o site; arquitetura, alvo de escala e desenvolvimento saem dele.
`AGENTS.md` não é encurtado (é instrução operacional para agentes), só tem as
duas referências atualizadas e ganha uma seção curta sobre `site/`.

- *Site importa os Markdown de onde estão*: evitaria mover, mas esses arquivos
  têm links relativos ao repositório, citam nomes de changes arquivadas e não
  têm par em inglês; a adaptação seria tão grande quanto mover.
- *Manter cópia nos dois lugares*: duas versões divergem na primeira edição.

### D6 — Página de auditoria com status por achado

A página `security/audits` traz uma tabela por relatório: identificador,
severidade, resumo de uma linha, status (`corrigido`, `aceito`, `aberto`) e
onde foi tratado (capability/spec ou arquivo). Os relatórios completos
continuam em `docs/`, só em português, linkados no GitHub como anexo.

Levantamento preliminar feito para este design, a confirmar item a item na
implementação (tarefa 5.3) antes de publicar:

| Achado | Indício no código atual | Status provável |
|---|---|---|
| M1 cookie sem `Secure` | allowlist de `X-Forwarded-*`, HSTS no `Caddyfile` | corrigido |
| M2 sem rate limit no login | limitador por conta e por IP em `auth.py` | corrigido |
| M3 sessão na mesma origem | decisão de arquitetura documentada | aceito |
| B1 timing de conta desabilitada | checagem de `disabled_at` agora após a senha | corrigido (medir) |
| B2 cabeçalhos de segurança | spec `http-hardening` | corrigido |
| B3 `/docs` exposto | spec `http-hardening` | corrigido |
| B4 rede Docker compartilhada | sem rede por usuário no runtime | aberto |
| B5 `icon_url` sem validação | `localCoverUrl()` no frontend | corrigido |
| I1 `harden_desktop` sem efeito | campo só existe no schema | conferir |
| I2 containers órfãos | sem limpeza dedicada encontrada | conferir |
| I3 header `Server` | `header -Server` no `Caddyfile` | corrigido |
| I4 sem log de segurança | spec `security-audit-log` | corrigido |
| I5 `sessions` cresce | `purge_sessions` no reaper | corrigido |

Publicar um achado como "aberto" é aceitável e desejado: a página existe para
ser honesta, não para parecer limpa.

### D7 — Aviso de root no host tem seção própria na landing

Uma seção dedicada ("o que saber antes de implantar"), separada da seção que
apresenta as camadas de isolamento, com o texto do aviso e link para a página
de superfície de confiança. Embutir o aviso como nota dentro da seção de
segurança o esconderia atrás do argumento de venda.

### D8 — Identidade visual por tokens, fontes locais

`styles/` define os tokens de cor a partir dos valores de `theme.js` e os
aplica às variáveis de tema do Starlight e ao CSS da landing. Escuro é o
padrão; o claro usa a paleta `light` do portal. O tema pastel do portal não é
levado ao site. Fontes vêm dos mesmos pacotes `@fontsource` do frontend, sem
requisição a terceiros; Caveat só na logo. Os valores são copiados, não
importados de `frontend/`, para manter os projetos independentes — a paleta do
portal muda raramente e a divergência seria visível de imediato.

### D9 — Diagrama de arquitetura como componente

O diagrama de origem única é redesenhado como SVG inline num componente Astro
que recebe os rótulos por idioma, respeitando claro/escuro pelos tokens. Um
SVG estático exigiria um arquivo por idioma e por tema. O README não mantém o
diagrama ASCII: a seção de arquitetura sai dele (D5).

### D10 — Publicação por GitHub Actions

Dois workflows:

- `site-check`: em pull requests que tocam `site/**` ou o próprio workflow —
  instala, roda a checagem de traduções e o build (que inclui a validação de
  links internos). Não publica.
- `site-deploy`: em push para `main` nos mesmos caminhos e por disparo manual
  — mesmos passos e, em seguida, publica o artefato no Pages com as ações
  oficiais (`upload-pages-artifact` e `deploy-pages`), com permissões mínimas
  (`contents: read`, `pages: write`, `id-token: write`) e concorrência que
  cancela publicações em andamento.

- *Branch `gh-pages`*: mistura artefato de build no histórico do repositório.
- *Pages servindo a pasta `/docs`*: `docs/` já é usada para logos e relatórios
  e o site precisa de build.

Links internos quebrados falham o build por um plugin validador do Starlight.
Links externos não são verificados no CI (instáveis por natureza).

### D11 — Capturas de tela reproduzíveis

Um script Playwright em `site/scripts/` abre o stack de desenvolvimento
(`http://127.0.0.1:8000`, credenciais dev já públicas no repositório), navega e
grava as capturas em `site/src/assets/screenshots/`, em viewport fixo e tema
escuro. Roda sob demanda, não no CI: as capturas de sessão exigem Docker real
com uma imagem webtop e uma imagem de agente construídas. As imagens geradas
são versionadas. A interface do portal é só em português; as mesmas capturas
servem aos dois idiomas, com `alt` e legenda traduzidos.

### D12 — `site/` fora da imagem do portal

`.dockerignore` ganha `site`. O `Dockerfile` não copia `site/`, então isso só
reduz o contexto enviado ao daemon; a imagem não muda.

## Risks / Trade-offs

- [Páginas próprias colidem com rotas do Starlight] → validado na primeira
  tarefa de código; plano B descrito em D2 sem mudança de URL.
- [Tradução inglesa de baixa qualidade na versão principal do site] → o
  português é a origem e fica a um clique; revisão humana do inglês da landing
  e das páginas de segurança antes da primeira publicação (tarefa 7.4).
- [Checagem de defasagem vira atrito e alguém a desliga] → o `--stamp` torna o
  recarimbo um comando; a regra entra no `AGENTS.md`.
- [Status de um achado publicado errado como "corrigido"] → cada linha exige
  evidência conferida no código atual; na dúvida, o status é "aberto".
- [Página de auditoria envelhece: novos relatórios não entram] → a página
  declara a data e o commit de cada relatório; `AGENTS.md` registra que um
  relatório novo em `docs/` pede atualização da página.
- [Encurtar `deploy/README.md` prejudica quem clona sem internet] → o arquivo
  curto aponta também para o caminho do Markdown-fonte dentro de `site/`.
- [Capturas de tela ficam desatualizadas com a evolução da interface] → o
  script as regenera com um comando; não há automação além disso.
- [Primeiro push falha porque o Pages não está habilitado] → habilitar é
  tarefa manual explícita, anterior ao merge.

## Migration Plan

1. Mantenedor habilita o Pages com origem "GitHub Actions".
2. A change entra por pull request; `site-check` valida o build.
3. No merge em `main`, `site-deploy` publica. Conferir as duas landings e uma
   página de cada seção nos dois idiomas no endereço público.
4. Só então preencher o campo "Website" do repositório com o endereço do site.

Reversão: reverter o commit restaura os textos em `deploy/` e no `README.md`;
desabilitar o Pages nas configurações tira o site do ar. Nada no portal
depende do site.

## Open Questions

- Licença e atribuição dos logos de terceiros em `agent-images/covers/logos/`
  (GNOME, KDE, VS Code etc.) quando exibidos num site de produto: a landing
  pode usá-los com a nota de marca já presente em
  `agent-images/covers/README.md`, ou trocar por nomes em texto sem alterar
  layout nem tarefas.
