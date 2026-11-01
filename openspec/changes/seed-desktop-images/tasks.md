# Tasks

## 1. Seed de desktops

- [x] 1.1 Criar `backend/app/services/desktop_images.py` com a tupla `DESKTOP_IMAGES` com as quatro entradas de desktop (`webtop:latest` "Webtop XFCE", `webtop:ubuntu-kde` "Ubuntu KDE", `webtop:alpine-mate` "Alpine MATE", `vscode:latest` "VS Code") e `seed_desktop_images(settings, runtime)` idempotente por (repositório, tag), `provision_kind='pull'`, falha isolada por entrada — verificado com testes unitários novos (`test_desktop_images.py`): banco vazio registra as quatro com `pull_state` em provisionamento e dispara `run_pull`; entrada existente (ready/desabilitada/editada) não é duplicada nem tocada; falha de registro de uma entrada não impede a outra
- [x] 1.2 Ligar `seed_desktop_images` no lifespan de `backend/app/main.py`, entre `seed_agent_images` e `seed_image_covers` — verificado com teste de integração da fábrica: app criado com banco vazio termina o lifespan com as quatro entradas no catálogo **e com as capas padrão (xfce/kde/mate/vscode) já aplicadas no mesmo boot**

## 2. Documentação e verificação

- [x] 2.1 Documentar em `deploy/README.md` (seção de ordem de subida) que um deploy novo nasce com os 5 agentes + VS Code + Webtop XFCE baixando em segundo plano, e que entradas já existentes nunca são sobrescritas pelo seed — conferência por leitura cruzada com o design
- [ ] 2.2 Rodar a suíte padrão (`cd backend && .venv/bin/python -m pytest`) verde; contra o stack dev reiniciado, confirmar em `/api/admin/images` que não há duplicação das entradas padrão e que o startup loga o seed sem erro

## Workflow follow-up

- Arquivar (`openspec archive "seed-desktop-images"`) após revisão, registrando o delta na spec `image-catalog`.
