# Proposal

## Why

Usuários de imagens de agente de código (e também de webtop) precisam que o
`git` dentro do container autentique com repositórios remotos (clonar, dar
push). Hoje não há nenhuma identidade SSH disponível nos containers: as
imagens de agente nem têm o cliente SSH instalado, e o portal não tem
nenhum mecanismo para prover uma credencial desse tipo a uma instância.

## What Changes

- Cada usuário passa a ter uma identidade SSH própria (um par de chaves),
  gerada pelo portal — o portal nunca recebe nem armazena uma chave privada
  que o usuário já tenha em outro lugar.
- A chave privada fica cifrada em repouso no banco; só a chave pública é
  exibida ao usuário, para ele cadastrar como "deploy key" no GitHub/GitLab/
  Bitbucket.
- Ao criar o container de qualquer instância (imagem de agente ou webtop),
  o portal injeta a identidade SSH do dono (chave privada, pública e um
  `known_hosts` pré-cadastrado com GitHub, GitLab e Bitbucket) no diretório
  home da instância, para que `git`/`ssh` funcionem sem configuração manual.
- Parar e religar uma instância reaproveita o mesmo container (comportamento
  já existente), então a identidade injetada na criação permanece sem
  precisar ser reinjetada.
- O usuário pode regenerar sua identidade SSH pelo portal; a regeneração
  substitui a chave em todas as instâncias vivas do usuário (rodando ou
  paradas), não só nas futuras.
- Nova área de interface para o usuário (não existe nenhuma tela de
  configurações hoje): ver a chave pública atual e regenerar.
- `agent-images/_base/Dockerfile` passa a instalar o cliente SSH (`git` já
  está presente); as imagens webtop do LinuxServer já trazem `git` e `ssh`.
- `agent-images/_base/Dockerfile` passa a instalar também o GitHub CLI
  (`gh`) e o GitLab CLI (`glab`), para interação com repositórios além do
  `git`/`ssh` puro (ex.: abrir pull requests, ver issues). O login desses
  CLIs continua manual pelo usuário no terminal — não usam nem dependem da
  identidade SSH do portal.

## Capabilities

### New Capabilities

- `ssh-identity`: identidade SSH por usuário — geração, armazenamento
  cifrado, exposição da chave pública, regeneração, e injeção automática
  nos containers de instâncias do usuário.

### Modified Capabilities

(Nenhuma — a criação, o ciclo de vida e a persistência de volume das
instâncias não mudam; a injeção da identidade é um passo adicional, não uma
alteração do comportamento já especificado em `desktop-instances`.)

## Impact

- `backend/app/db.py`: nova tabela (ou colunas) para a identidade SSH por
  usuário (chave pública, chave privada cifrada, metadados).
- `backend/app/config.py`: nova configuração (convenção `WCUI_*`) para a
  chave mestra de criptografia em repouso.
- `backend/pyproject.toml`: nova dependência `cryptography` (cifrar/decifrar
  a chave privada; hoje o projeto não tem nenhuma dependência de
  criptografia).
- Novo serviço de backend para gerar/regenerar a identidade e para montar o
  arquivo `known_hosts` pré-cadastrado.
- `backend/app/runtime/protocol.py`, `backend/app/runtime/docker_runtime.py`,
  `backend/app/runtime/fake.py`: nova operação de runtime para copiar
  arquivos para dentro de um container existente (via `put_archive` do
  aiodocker), usada tanto na criação quanto na regeneração.
- `backend/app/services/instances.py`: injetar a identidade logo após
  `create_container`.
- Nova rota de API para o usuário consultar sua chave pública e disparar a
  regeneração.
- `agent-images/_base/Dockerfile`: adicionar o cliente SSH, o GitHub CLI
  (`gh`) e o GitLab CLI (`glab`).
- Frontend: nova área de "configurações" (ainda não existe nenhuma) para
  mostrar a chave pública e regenerar.
