# Site de produto

Landing e documentação do WebContainerUI, publicadas no GitHub Pages em
<https://alanyoshida.github.io/webcontainerui/> (inglês) e
<https://alanyoshida.github.io/webcontainerui/pt-br/> (português).

Astro + Starlight. É um projeto Node independente do portal: nada aqui entra
na imagem Docker nem nos testes do backend ou do frontend.

## Comandos

```bash
npm ci            # instala as dependências
npm run dev       # servidor de desenvolvimento
npm test          # testes do script de traduções
npm run check     # confere se alguma tradução está defasada
npm run build     # checagem de traduções + build + validação de links internos
npm run preview   # serve o build local
```

Requer Node 22.23 ou mais novo (o CI usa a versão em `.nvmrc`).

## Onde fica cada coisa

| Caminho | Conteúdo |
|---|---|
| `src/content/docs/pt-br/` | Documentação em português, a **origem** |
| `src/content/docs/` | Tradução para o inglês, servida na raiz do site |
| `src/content/landing/pt-br.json`, `en.json` | Textos da landing |
| `src/pages/`, `src/layouts/`, `src/components/landing/` | Landing |
| `src/components/starlight/` | Peças do Starlight sobrescritas (logo, tema) |
| `src/styles/tokens.css` | Cores e fontes, copiadas de `frontend/src/theme.js` |
| `src/assets/screenshots/` | Capturas de tela reais do portal |
| `scripts/` | Checagem de traduções e captura de telas |

## Escrever ou alterar uma página

1. Edite (ou crie) a página em `src/content/docs/pt-br/<seção>/`.
2. Faça a mesma mudança na página inglesa de mesmo caminho, sem o `pt-br/`.
3. Registre que a tradução foi revisada contra o texto atual:

   ```bash
   node scripts/check-translations.mjs --stamp src/content/docs/<seção>/<página>.md
   ```

Sem o passo 3 o build falha, de propósito: o inglês é a versão que aparece na
raiz do site e não pode ficar para trás. O carimbo é o SHA-256 da página em
português, gravado em `sourceHash` no frontmatter da página inglesa. Os textos
da landing seguem a mesma regra (`--stamp src/content/landing/en.json`).

Links internos são escritos a partir da raiz do site, sem idioma e sem o
caminho base, e iguais nas duas línguas: `[texto](/security/audits/)`. Um
plugin acrescenta o caminho base e o prefixo do idioma; link para página que
não existe falha o build.

## Capturas de tela

As imagens em `src/assets/screenshots/` são capturas reais, geradas por:

```bash
npm run screenshots
```

Pré-requisitos:

- stack de desenvolvimento no ar em `http://127.0.0.1:8000`
  (`cd deploy && docker compose -f docker-compose.dev.yml up --build`), com o
  startup concluído;
- as imagens `Ubuntu KDE` e `OpenCode` prontas no catálogo (o script espera os
  downloads do primeiro boot, que somam vários GB);
- navegador do Playwright instalado (`npx playwright install chromium`).

O script entra como administrador dev, cria o usuário descartável
`capturas@local.test` e o grupo `Demonstração` com acesso a todo o catálogo,
abre uma sessão de agente e uma de desktop com esse usuário, captura e exclui
as duas instâncias. Ele nunca inicia nem exclui instância de outra conta. O
usuário e o grupo ficam no banco de dev depois da execução.

Rode sob demanda, quando a interface mudar; não faz parte do CI.

## Publicação

`.github/workflows/site-check.yml` valida pull requests e
`site-deploy.yml` publica a cada push em `main`. Endereço e caminho base vêm
de `SITE_URL` e `SITE_BASE`; para domínio próprio, troque as duas no workflow
e adicione `public/CNAME`.
