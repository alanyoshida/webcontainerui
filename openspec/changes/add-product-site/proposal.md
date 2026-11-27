# Proposal

## Why

O produto não tem vitrine pública. O repositório é público, mas quem chega nele
encontra um README longo, só em português, cujo texto de abertura fala apenas
de "desktops Linux" e nem menciona os agentes de código em CLI. A documentação
existe e é boa, mas está espalhada (`README.md`, `deploy/README.md`,
`deploy/SECURITY.md`, dois relatórios em `docs/`, 19 specs) e não é navegável
nem pesquisável.

Um site no GitHub Pages resolve as duas coisas de uma vez: apresenta o produto
para quem ainda não o conhece e dá um lugar único, com busca e navegação, para
arquitetura, segurança e operação.

## What Changes

- Novo site estático em `site/`, publicado no GitHub Pages em
  `https://alanyoshida.github.io/webcontainerui/` por um workflow do GitHub
  Actions a cada push em `main`.
- **Landing sob medida**: apresentação do produto (desktops Linux e agentes de
  código no navegador), capturas de tela, catálogo de imagens, resumo do modelo
  de segurança em camadas, aviso explícito de que o portal equivale a root no
  host, e o caminho de instalação.
- **Documentação navegável** com busca, barra lateral e alternância
  claro/escuro, organizada em: Começar, Arquitetura, Segurança, Operação e
  Referência.
- **Dois idiomas**: inglês na raiz do site e português em `/pt-br/`. O
  português é a língua de origem; o inglês é tradução. O build detecta
  tradução defasada em relação à origem.
- **Identidade visual do portal**: carvão, primário rosa, Inter, JetBrains
  Mono e a logo em Caveat, com o tema escuro como padrão.
- **Fonte única dos textos longos**: o conteúdo de `deploy/README.md` e
  `deploy/SECURITY.md` migra para o site; os dois arquivos ficam curtos e
  apontam para lá. Referências em `README.md`, `AGENTS.md` e `install.sh` são
  ajustadas.
- **Página de auditoria**: cada achado do pentest de 2026-11-01 e do scan
  SAST/SCA aparece com seu status atual (corrigido, aceito ou aberto) e onde
  foi tratado; os relatórios originais ficam como anexos.
- **README enxuto**, ainda em português: abertura que cita desktops e agentes
  de código, instalação rápida e link para o site nos dois idiomas.
- Novas capturas de tela (catálogo, sessão de desktop, sessão de agente,
  painel administrativo) geradas a partir do stack de desenvolvimento.
- Validação do site em pull requests (build, links internos e tradução
  defasada) sem publicar.

Nenhum comportamento do portal muda. Não há alteração em backend, frontend,
imagens de agente ou composições Docker além de excluir `site/` do contexto de
build da imagem.

Fora de escopo: domínio próprio, versionamento da documentação por release,
blog, analytics, tradução das specs do OpenSpec e tradução da interface do
portal.

## Capabilities

### New Capabilities

- `product-site`: site público do projeto — o que ele apresenta (landing e
  documentação), em quais idiomas, com qual identidade visual, como é
  publicado e quais garantias de integridade o build oferece (links,
  traduções, status dos achados de segurança).

### Modified Capabilities

Nenhuma. O site descreve o comportamento já especificado; nenhum requisito das
capabilities existentes muda.

## Impact

- **Código novo**: `site/` (projeto Node independente, com `package.json` e
  lockfile próprios) e `.github/workflows/` (primeiro workflow do repositório).
- **Dependências novas**, restritas a `site/`: Astro, Starlight, validador de
  links e os mesmos pacotes `@fontsource` já usados no frontend. Nada entra no
  backend nem no frontend do portal.
- **Documentos alterados**: `README.md`, `AGENTS.md`, `deploy/README.md`,
  `deploy/SECURITY.md`, `install.sh` (apenas comentários e a mensagem final que
  cita a documentação).
- **Build da imagem**: `.dockerignore` passa a excluir `site/`.
- **Configuração externa (manual, feita pelo mantenedor)**: habilitar o GitHub
  Pages com origem "GitHub Actions" nas configurações do repositório.
- **Manutenção contínua**: toda mudança de documentação passa a ter duas
  metades (pt-BR e inglês); a checagem de tradução defasada torna a segunda
  metade impossível de esquecer.
