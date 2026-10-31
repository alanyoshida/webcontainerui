# Design

## Context

Cada instância usa um volume Docker próprio por `(user_id, image_id)`,
montado em `/config` (`_VOLUME_MOUNT_PATH`, `backend/app/services/instances.py:12`),
com `HOME=/config` tanto nas imagens de agente (`agent-images/_base/Dockerfile`)
quanto no usuário `abc` das imagens webtop do LinuxServer (confirmado via
`docker run --entrypoint sh lscr.io/linuxserver/webtop:latest -c 'getent passwd abc'`
→ `abc:x:911:1001::/config:/bin/bash`). As imagens de agente rodam como
root; as webtop rodam como `abc`, cujo uid/gid efetivo o próprio init do
LinuxServer ajusta para `PUID`/`PGID` (já configurados hoje via
`Settings.puid`/`Settings.pgid`, injetados em `_build_spec`).

`stop_instance` nunca remove o container, só o para; religar é só
`start_container` de novo no mesmo container
(`_resume_existing`, `instances.py:173-202`). Só quando o container já não
existe no runtime é que `_provision_and_start` recria do zero
(`create_container` + `start_container`). Isso define o único ponto onde a
identidade SSH precisa ser escrita no filesystem do container: logo após
`create_container`, nunca a cada start.

Não existe hoje nenhum conceito de segredo/credencial trazido pelo usuário:
as únicas credenciais por instância (`inner_user`/`inner_password`, Selkies/
ttyd) são geradas pelo próprio portal com `secrets.token_urlsafe` e gravadas
em texto puro (`db.py`, colunas `inner_user`/`inner_password`) — não há
precedente de criptografia em repouso no projeto (`itsdangerous` está no
`pyproject.toml` mas não é usado em lugar nenhum). A change anterior
(`coding-agent-catalog-images`) decidiu explicitamente deixar "gestão de
segredos/API keys dos agentes pelo portal" fora de escopo, com a
justificativa "usuário configura manualmente dentro do terminal" — esta
change reverte essa posição deliberadamente, mas só para a identidade SSH
embutida do portal, não para segredos arbitrários de agentes em geral.

`aiodocker`'s `DockerContainer` já expõe `put_archive` (copia um tar para
dentro do filesystem de um container existente, rodando ou parado, sem
depender do entrypoint da imagem). As imagens webtop do LinuxServer já têm
`git` e `ssh` instalados; `agent-images/_base/Dockerfile` só tem `git`.

## Goals / Non-Goals

**Goals:**
- Uma identidade SSH por usuário, reaproveitada em todas as instâncias dele.
- `git`/`ssh` funcionam dentro de qualquer instância (agente ou webtop) sem
  configuração manual, assim que a instância existe.
- O portal nunca recebe nem armazena uma chave privada que o usuário já
  tinha em outro lugar — só gera e mostra a pública.
- Regenerar propaga para instâncias já existentes (rodando ou paradas), não
  só para criações futuras.

**Non-Goals:**
- Importar/colar uma chave privada existente — decisão explícita, ver
  proposal.md.
- Identidade por instância (em vez de por usuário).
- Gestão geral de segredos/variáveis de ambiente para agentes — o non-goal
  da change anterior continua valendo para qualquer coisa além desta
  identidade SSH embutida.
- Integração com a API do GitHub/GitLab para cadastrar a deploy key
  automaticamente — o usuário cola a chave pública manualmente.
- Escolher algoritmo de chave — fixo em Ed25519, sem opção exposta.

## Decisions

### D1: Geração da chave em Python (biblioteca `cryptography`), não `ssh-keygen`

Gera um par Ed25519 com `cryptography.hazmat.primitives.asymmetric.ed25519`
e serializa em formato OpenSSH (`Encoding.OpenSSH` /
`PrivateFormat.OpenSSH`). Evita depender de um binário `ssh-keygen`
presente no container do próprio portal e é determinístico/testável sem
subprocesso. Alternativa descartada: invocar `ssh-keygen` via subprocess —
mais frágil (depende do binário existir na imagem do portal) e mais difícil
de testar.

### D2: Armazenamento cifrado com chave mestra obrigatória

Nova tabela `ssh_identities` (`user_id` único, `public_key` em texto,
`private_key_encrypted` cifrada, `created_at`) — uma linha por usuário;
regenerar sobrescreve, não acumula histórico. Cifragem simétrica com
`Fernet` (também da lib `cryptography`), usando uma chave mestra nova,
`Settings.ssh_key_encryption_key` (env `WCUI_SSH_KEY_ENCRYPTION_KEY`),
seguindo a convenção `WCUI_*` já usada pelas demais configurações
(`config.py`). Sem valor padrão: ausente, a inicialização falha (mesmo
padrão de "erro de configuração" já usado para o par admin incompleto em
`Settings._admin_pair_is_complete`). Alternativa descartada: gerar e
persistir uma chave mestra sozinha no primeiro boot — mais frágil para um
operador fazer backup/rotação conscientes, e foge do padrão do projeto de
toda configuração sensível vir de env var explícita.

### D3: Injeção via `put_archive` logo após `create_container`

Nova operação no protocolo `ContainerRuntime`
(`backend/app/runtime/protocol.py`): `put_archive(container_id, destination_path, tar_bytes)`.
Implementada em `AioDockerContainerRuntime` sobre `DockerContainer.put_archive`
e em `FakeContainerRuntime` registrando as chamadas (`put_archive_calls`),
no mesmo padrão já usado para `build_calls`/`pull_calls`
(`backend/app/runtime/fake.py`). Um novo serviço monta um tar com
`.ssh/` (modo 700), `.ssh/id_ed25519` (600), `.ssh/id_ed25519.pub` (644) e
`.ssh/known_hosts` (644, pré-cadastrado com GitHub, GitLab e Bitbucket), e
chama `put_archive(container_id, "/config", tar_bytes)` — reaproveitando o
mesmo `_VOLUME_MOUNT_PATH` já usado pelo resto do sistema. `instances.py`
passa a chamar isso logo após `create_container`, antes de
`start_container`, em `_provision_and_start`.

Dono dos arquivos: fixado explicitamente no próprio tar (uid/gid), em vez
de depender da ordem entre nossa injeção e o init do LinuxServer
reconciliar `/config` para `PUID`/`PGID` — ver Risco abaixo.

Descoberto ao verificar manualmente (ver tasks.md 8.1): `ENV HOME=/config`
no Dockerfile das imagens de agente não basta para que `ssh`/`git`
encontrem `/config/.ssh` — o cliente `ssh` resolve o diretório do usuário
via `/etc/passwd` (`getpwuid`), não pela variável de ambiente, e o root das
imagens de agente (base `node:20-bookworm-slim`) tem `/root` cadastrado lá.
`agent-images/_base/Dockerfile` passou a corrigir também o passwd (`sed` no
campo do home de `root`), igual ao que as imagens webtop do LinuxServer já
fazem nativamente para o usuário `abc` (confirmado via
`getent passwd abc` → home `/config` de fato no passwd, não só via env).
Travado por `backend/tests/test_e2e_agent_base_ssh_home.py`.

### D4: Regeneração reaproveita o mesmo `put_archive`, por instância, com falha isolada

Ao regenerar, o backend busca as linhas de `instances` do usuário com
`container_id` não nulo (em execução ou parada) e chama `put_archive` de
novo em cada uma, num loop que isola falha por instância — mesmo padrão já
usado no seed de imagens de agente (`coding-agent-images`, decisão D5:
"falha isolada por imagem no seed"). Uma instância sem container (nunca
chegou a ser criada, ou está em erro sem `container_id`) é simplesmente
pulada.

### D5: API e frontend

Dois endpoints novos sob o usuário autenticado (não administrador):
`GET /api/me/ssh-identity` (retorna a chave pública, gerando a identidade
primeiro se ainda não existir) e `POST /api/me/ssh-identity/regenerate`.
Nenhuma rota de importação — reforça D1/o non-goal de nunca aceitar uma
chave já existente. No frontend, uma área nova (não existe nenhuma tela de
configurações hoje) mostra a chave pública com botão de copiar e um botão
de regenerar com confirmação, já que é uma ação que invalida a chave
cadastrada em qualquer git host externo.

## Risks / Trade-offs

- [Risco] A ordem entre nosso `put_archive` e o init do LinuxServer (que
  ajusta o dono de `/config` para `PUID`/`PGID`) pode deixar os arquivos
  injetados com dono/permissão errados dependendo do timing →
  [Mitigação] fixar uid/gid explicitamente nas entradas do tar
  (`PUID`/`PGID` já conhecidos via `Settings`, em vez de confiar em root +
  reconciliação implícita do init); validar com teste de integração real
  (`docker exec ... ls -la /config/.ssh`) durante a implementação.
- [Risco] Perder `WCUI_SSH_KEY_ENCRYPTION_KEY` torna todas as identidades já
  armazenadas indecifráveis → [Mitigação] aceitável: identidade SSH é
  sempre substituível (o usuário regenera e recadastra a pública); não é
  dado do usuário que se perde, só uma credencial derivada.
- [Risco] `put_archive` numa instância sem container (`container_id` nulo,
  nunca chegou a existir) → [Mitigação] pular essas linhas no loop de
  regeneração, sem erro.
- [Trade-off] `known_hosts` fixo só cobre GitHub/GitLab/Bitbucket — outro
  host exige aceite manual pelo usuário no terminal, igual ao
  comportamento de hoje para qualquer conexão SSH não pré-cadastrada.

## Migration Plan

Aditiva: nova tabela, nova env var obrigatória (`WCUI_SSH_KEY_ENCRYPTION_KEY`,
precisa ser definida no deploy — documentar no README/compose), novos
endpoints, novo painel de frontend. Instâncias já em execução no momento do
deploy **não** recebem a identidade retroativamente — só instâncias criadas
depois, ou qualquer instância (nova ou antiga) alcançada por uma
regeneração explícita feita depois que a identidade já existe. Rollback:
remover a env var/endpoints/tabela; instâncias continuam funcionando sem a
identidade, comportamento idêntico ao atual.

## Open Questions

Nenhuma pendente — algoritmo (Ed25519), biblioteca (`cryptography`) e
mecanismo de injeção (`put_archive`) já resolvidos acima.
