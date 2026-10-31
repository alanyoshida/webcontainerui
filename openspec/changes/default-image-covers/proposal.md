# Proposal

## Why

O portal já provisiona automaticamente as 5 imagens de agente no startup, mas
suas entradas do catálogo continuam sem capa até um administrador enviar uma
manualmente. O mesmo vale para qualquer outra entrada já registrada: o usuário
escolhe o template vendo cartões sem identificação visual. Isso torna o
catálogo menos reconhecível e exige trabalho manual repetido a cada implantação.

## What Changes

- O portal passa a resolver um logo pelo nome de exibição, repositório e tag da
  imagem, usando um mapa local versionado que cobre os 5 agentes de código e os
  ambientes de desktop mais comuns (XFCE, KDE/Plasma, MATE, GNOME, Cinnamon,
  LXDE, LXQt, i3, Sway).
- Para cada entrada existente no catálogo no momento do startup, o seed cadastra
  uma capa padrão de 1200x400 PNG, composta com a cor predominante da marca e
  apenas o logo (sem texto), desde que a entrada ainda não tenha uma capa
  enviada pelo administrador.
- Entradas cujo nome não corresponda a nenhum logo conhecido recebem uma capa
  genérica do portal.
- Quando o arquivo versionado de uma capa padrão muda, o seed substitui
  automaticamente a capa das entradas que ainda usam a capa padrão. Capas
  enviadas pelo administrador nunca são sobrescritas.
- O seed registra a origem da capa para distinguir capa padrão de capa enviada
  pelo administrador.
- As capas padrão são aplicadas independentemente do resultado do build da
  imagem: uma falha de provisionamento não impede a capa de ser cadastrada.

Fora de escopo: tornar as imagens visíveis a todos sem concessão de grupo,
iniciar instâncias automaticamente no startup, cadastrar capa em imagens
registradas depois do startup e oferecer uma ação para restaurar a capa padrão
depois de um upload do administrador.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `image-catalog`: entradas do catálogo passam a receber capa padrão automaticamente
  no startup, com atualização automática quando o asset versionado muda e
  precedência do upload do administrador; entradas sem logo conhecido usam uma
  capa genérica.
- `coding-agent-images`: as imagens de agente passam a receber capa padrão com o
  logo da ferramenta correspondente, junto do seu provisionamento automático.

## Impact

- Backend: `backend/app/services/images.py` (gravação da capa padrão e origem),
  `backend/app/services/agent_images.py` ou novo serviço de capas (resolução de
  logo, seed no startup), `backend/app/db.py` (coluna de origem da capa),
  `backend/app/main.py` (chamada do seed de capas).
- Assets: novo diretório `agent-images/covers/` com os PNGs versionados e um
  script reproduzível de geração a partir dos logos pesquisados.
- Banco: nova coluna para registrar se a capa é padrão ou enviada pelo admin;
  migração idempotente no padrão das migrações existentes.
- Testes: resolução de logo por nome, capa genérica, precedência do admin,
  atualização da capa padrão, idempotência e integração com o startup.
- Sem mudança no frontend: o catálogo já exibe `icon_url` quando presente.
- Sem mudança de API pública além do campo interno de origem da capa.
