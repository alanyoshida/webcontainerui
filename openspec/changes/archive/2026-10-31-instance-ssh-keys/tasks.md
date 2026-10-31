# Tasks

## 1. Dependência e configuração

- [x] 1.1 Adicionar `cryptography` às dependências de `backend/pyproject.toml`;
  verificar que `from cryptography.hazmat.primitives.asymmetric import ed25519`
  e `from cryptography.fernet import Fernet` importam sem erro no venv do
  backend.
- [x] 1.2 Adicionar `ssh_key_encryption_key: str` (sem valor padrão) a
  `Settings` (`backend/app/config.py`), seguindo a convenção `WCUI_*`;
  verificar com teste que `Settings()` levanta erro de validação quando
  `WCUI_SSH_KEY_ENCRYPTION_KEY` não está definida.

## 2. Armazenamento e geração da identidade

- [x] 2.1 Adicionar a tabela `ssh_identities` em `backend/app/db.py`
  (`user_id` único, `public_key`, `private_key_encrypted`, `created_at`),
  com migração idempotente no padrão de `_migrate_add_icon_path`; verificar
  com teste que a tabela existe após `init_db` e que rodar `init_db` de
  novo não falha nem duplica.
- [x] 2.2 Criar `backend/app/services/ssh_identity.py` com `get_or_create_identity`
  (gera um par Ed25519 e cifra a privada com Fernet usando
  `settings.ssh_key_encryption_key` se o usuário ainda não tiver uma; senão
  retorna a existente) e `regenerate_identity` (substitui, não acumula);
  verificar com testes unitários: gera na primeira chamada, não duplica
  numa segunda chamada sem regenerar, `regenerate_identity` troca a chave
  pública retornada, e nenhuma função de consulta devolve a chave privada
  em texto puro.
- [x] 2.3 Implementar a montagem do pacote a injetar (tar com `.ssh/`
  modo 700, `.ssh/id_ed25519` modo 600, `.ssh/id_ed25519.pub` modo 644,
  `.ssh/known_hosts` modo 644 pré-cadastrado com GitHub, GitLab e
  Bitbucket, dono fixado em `PUID`/`PGID` para instâncias webtop e `0:0`
  para instâncias de agente), no mesmo módulo; verificar com teste
  unitário que confere nomes, modos, dono e conteúdo dos membros do tar
  gerado para cada caso.

## 3. Runtime: capacidade de copiar arquivos para um container

- [x] 3.1 Adicionar `put_archive(container_id, destination_path, tar_bytes)`
  ao protocolo `ContainerRuntime` (`backend/app/runtime/protocol.py`) e
  implementar em `FakeContainerRuntime` (`backend/app/runtime/fake.py`)
  registrando as chamadas em `put_archive_calls`; verificar com teste
  unitário que o fake registra container, destino e conteúdo informados.
- [x] 3.2 Implementar `put_archive` em `AioDockerContainerRuntime`
  (`backend/app/runtime/docker_runtime.py`) sobre
  `DockerContainer.put_archive`; verificar com teste e2e (mesma marca dos
  testes e2e existentes) que injeta um arquivo de teste num container real
  e confirma, via `get_archive` ou `docker exec cat`, que o conteúdo e o
  modo chegaram corretos.

## 4. Integração com a criação e a regeneração de instâncias

- [x] 4.1 Chamar a injeção da identidade SSH do dono logo após
  `create_container` em `_provision_and_start`
  (`backend/app/services/instances.py`), antes de `start_container`;
  verificar com teste unitário usando `FakeContainerRuntime` que
  `put_archive` é chamado com o destino `/config` e o conteúdo da
  identidade do dono ao criar uma instância.
- [x] 4.2 Implementar a propagação na regeneração: localizar todas as
  linhas de `instances` do usuário com `container_id` não nulo (em
  execução ou paradas) e chamar `put_archive` em cada uma, isolando falha
  por instância (sem interromper as demais); verificar com teste unitário
  usando um fake runtime que falha numa das instâncias e confirma que as
  outras são atualizadas e a falha é reportada.

## 5. API

- [x] 5.1 Adicionar `GET /api/me/ssh-identity`, retornando a chave pública
  do usuário autenticado (gerando a identidade antes, se ainda não
  existir); verificar com teste que a primeira consulta gera e consultas
  seguintes retornam a mesma chave.
- [x] 5.2 Adicionar `POST /api/me/ssh-identity/regenerate`, chamando
  `regenerate_identity` e a propagação às instâncias vivas; verificar com
  teste que a chave pública muda após a chamada e que a propagação (via
  fake runtime) é acionada.
- [x] 5.3 Garantir que as duas rotas atuam apenas sobre o usuário
  autenticado da requisição (sem parâmetro de outro usuário, sem exigir
  papel de administrador); verificar com teste que a identidade de um
  usuário nunca é alcançável a partir da sessão de outro.

## 6. Imagem de agente

- [x] 6.1 Adicionar o cliente SSH (`openssh-client`) a
  `agent-images/_base/Dockerfile` (`git` já está presente); verificar com
  `docker build` local e `docker run --rm <imagem> ssh -V` confirmando o
  cliente instalado.
- [x] 6.2 Corrigir o home do usuário root no passwd da imagem de agente
  para `/config` (descoberto ao verificar a injeção de ponta a ponta: `ssh`
  resolve `~/.ssh` via `/etc/passwd`, não via `$HOME`, então sem essa
  correção `known_hosts`/a identidade injetada nunca eram encontrados);
  verificar com teste e2e (`test_e2e_agent_base_ssh_home.py`) que
  `getent passwd root` dentro da imagem construída retorna `/config`.
- [x] 6.3 Adicionar o GitHub CLI (`gh`) e o GitLab CLI (`glab`) a
  `agent-images/_base/Dockerfile`, baixando o binário da release oficial
  pinada por versão (mesmo padrão já usado para o `ttyd`: binário estático
  direto do GitHub/GitLab release, não `curl | sh`); verificar com
  `docker build` local e `docker run --rm <imagem> gh --version` /
  `glab --version` confirmando os dois clientes instalados.

## 7. Interface do usuário

- [x] 7.1 Criar uma área de "Identidade SSH" no frontend mostrando a chave
  pública do usuário (com botão de copiar) e um botão "Regenerar" com
  diálogo de confirmação (ação que invalida a chave cadastrada em
  qualquer git host externo); verificar com testes de componente: exibe a
  chave retornada pela API, copiar funciona, regenerar pede confirmação e,
  confirmado, atualiza a chave exibida.
- [x] 7.2 Adicionar um ponto de acesso a essa área na navegação do portal
  (não existe nenhuma tela de configurações hoje); verificar com teste de
  componente que o link/botão leva à área de identidade SSH.

## 8. Verificação integrada

- [x] 8.1 Subir o stack de dev
  (`docker compose -f deploy/docker-compose.dev.yml up --build -d`),
  gerar a identidade SSH de um usuário pela interface, criar uma instância
  de agente e confirmar no terminal que `ssh -T git@github.com` ou
  `git ls-remote` contra um repositório de teste autentica com a chave
  injetada.
- [x] 8.2 Repetir a verificação numa instância webtop (terminal gráfico).
- [x] 8.3 Parar e religar a instância e confirmar que a identidade
  continua disponível em `/config/.ssh`, sem nova injeção.
- [x] 8.4 Regenerar a identidade com uma instância em execução e outra
  parada, e confirmar que ambas passam a ter a nova chave pública.
- [x] 8.5 Rodar a suíte completa de testes (`pytest` no backend, `npm test`
  no frontend) e confirmar que nada regrediu.

## Workflow follow-up

- Arquivar a change após a revisão, criando a capability `ssh-identity`
  nas specs principais.
