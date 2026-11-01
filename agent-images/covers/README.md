# Capas padrão do catálogo

Os PNGs finais (1200x400) são gerados a partir dos logos oficiais versionados
em `logos/`, com fundo em gradiente na cor predominante da marca e o logo
centralizado em branco, sem texto.

## Regenerar as capas

Requisitos (só em desenvolvimento): Python 3.12+, Pillow e Inkscape (para
converter SVGs novos em PNG).

```bash
python3 agent-images/covers/generate.py
```

O script escreve um `<chave>.png` para cada chave do mapa de logos
(`backend/app/services/image_covers.py`) e valida que o logo correspondente
existe em `logos/`. As capas geradas são versionadas — o portal **não** gera
imagem em tempo de execução.

## Adicionar um novo logo

1. Coloque o arquivo em `logos/` (SVG original e PNG 512px gerado com
   Inkscape: `inkscape --export-type=png --export-filename=<chave>.png
   --export-width=512 <chave>.svg`).
2. Adicione uma entrada em `COVERS` no `agent-images/covers/generate.py`
   com chave, arquivo e cor da marca.
3. Adicione a mesma chave com suas palavras-chave em `LOGOS` em
   `backend/app/services/image_covers.py` (ambientes de desktop antes dos
   agentes, para "ubuntu kde" resolver para kde).
4. Rode o script de geração e commite o PNG novo.

## Fontes dos logos

Logos são marcas dos respectivos projetos, usados aqui apenas para
identificação das entradas do catálogo:

| Chave | Logo | Fonte |
|---|---|---|
| `claude` | Claude | https://cdn.simpleicons.org/claude (Simple Icons) |
| `hermes` | Hermes Agent (Nous Research) | https://hermes-agent.nousresearch.com/ (`hermes-wing.svg`) |
| `agy` | Antigravity | https://antigravity.google (`antigravity-logo.png`) |
| `opencode` | OpenCode | https://cdn.simpleicons.org/opencode (Simple Icons) |
| `oh-my-pi` | oh-my-pi | https://omp.sh/favicon.svg |
| `xfce` | XFCE | https://cdn.simpleicons.org/xfce (Simple Icons) |
| `kde` | KDE | https://cdn.simpleicons.org/kde (Simple Icons) |
| `mate` | MATE | https://commons.wikimedia.org/wiki/File:MATE_Desktop_Environment_Logo.svg |
| `gnome` | GNOME | https://cdn.simpleicons.org/gnome (Simple Icons) |
| `cinnamon` | Cinnamon | https://cdn.simpleicons.org/cinnamon (Simple Icons) |
| `lxde` | LXDE | https://commons.wikimedia.org/wiki/File:LXDE-logo.svg |
| `lxqt` | LXQt | https://commons.wikimedia.org/wiki/File:Lxqt_logo.svg |
| `i3` | i3 | https://cdn.simpleicons.org/i3 (Simple Icons) |
| `sway` | Sway | https://cdn.simpleicons.org/sway (Simple Icons) |
| `vscode` | Visual Studio Code | https://commons.wikimedia.org/wiki/File:Visual_Studio_Code_1.35_icon.svg |
| `generic` | símbolo neutro do portal | criado neste repositório |

## Seed no startup

`seed_image_covers` (`backend/app/services/image_covers.py`) roda a cada
inicialização do portal e cadastra a capa padrão em toda entrada existente no
catálogo cujo nome/repositório/tag case com um logo do mapa; sem
correspondência, usa `generic.png`. Regras:

- Capa enviada pelo administrador (`icon_source = 'admin'`) nunca é
  sobrescrita.
- Capa padrão (`icon_source = 'default'`) é atualizada automaticamente
  quando o PNG versionado muda (nome determinístico com hash SHA-256 do
  conteúdo).
- Imagens registradas depois do startup recebem capa no próximo restart, não
  na criação.
- Falhas (asset ausente, disco) são isoladas por entrada e não impedem o
  startup.