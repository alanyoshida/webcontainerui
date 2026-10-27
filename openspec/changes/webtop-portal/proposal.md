# Proposal

## Why

Precisamos de um portal multiusuário, nos moldes do Kasm Workspaces, para rodar
desktops Linux completos dentro do navegador usando as imagens
[webtop do LinuxServer.io](https://docs.linuxserver.io/images/docker-webtop/).
O requisito central não é apenas "subir container": é **isolamento entre
usuários**. As imagens webtop, por padrão, não têm autenticação nenhuma e expõem
um terminal com `sudo` sem senha — quem alcança a interface gráfica obtém root
dentro do container. Qualquer portal construído sobre elas precisa garantir, por
construção, que um usuário nunca alcance a instância de outro.

## What Changes

Projeto greenfield: não existe código hoje. Esta change cria o sistema inteiro.

- **Portal web com origem única** servindo o front-end, a API e o proxy das
  sessões no mesmo host, permitindo embutir o desktop em iframe same-origin
  (o Selkies envia `frame-ancestors 'self'` por padrão).
- **Containers sem nenhuma porta publicada.** Os webtops ficam apenas numa rede
  Docker interna, alcançáveis somente pelo processo do portal. O isolamento passa
  a ser topológico; a checagem de dono no proxy é a segunda camada, não a única.
- **Autenticação por sessão server-side revogável**, com hash de senha Argon2.
- **Gestão de usuários e grupos pelo admin.** Não há auto-cadastro: o admin cria
  as contas e atribui grupos.
- **Catálogo de imagens registrado pelo admin**, com pull disparado no cadastro e
  acompanhamento de progresso. O usuário só vê imagens já baixadas e prontas.
- **Permissão por grupo**, não por usuário: grants ligam grupo a imagem, e a
  permissão de um usuário é a união dos grants dos seus grupos.
- **Ciclo de vida de instância com três estados** (ausente, rodando, parada) e as
  ações iniciar, parar e excluir. Sem pausar: `docker pause` congela a CPU mas
  **não libera memória**, então não serve ao propósito de economizar recurso, e
  deixaria a aba do navegador aparentemente travada.
- **Uma instância por par (usuário, imagem)**, garantida por índice único parcial.
- **Volume nomeado por (usuário, imagem)** montado em `/config`, de modo que os
  arquivos do usuário sobrevivam a parar e reiniciar. `stop` nunca toca no
  volume; apenas `delete` o remove, com confirmação explícita.
- **Proxy HTTP e WebSocket autorizador**, que verifica a propriedade da instância
  antes de encaminhar e injeta credencial interna por instância no header
  `Authorization`, para o usuário não enfrentar um segundo login.
- **Desligamento automático por inatividade**, preservando o volume, para que
  sessões abandonadas não consumam memória do host indefinidamente.
- **Endurecimento obrigatório do Selkies**: desligar os links de compartilhamento
  (`SELKIES_ENABLE_SHARING`, `SELKIES_ENABLE_SHARED`), que concedem acesso total à
  sessão sem autenticação própria, e manter o transporte WebRTC desligado, pois
  sua mídia trafega por UDP **por fora do proxy** e contornaria a autorização.
- **Suíte de testes em camadas**, com o runtime de containers atrás de um
  protocolo para que tudo exceto um punhado de testes opt-in rode sem Docker.

Fora de escopo nesta change: aceleração por GPU, federação de identidade
(OAuth/SAML/LDAP), múltiplos hosts Docker, cobrança ou medição de uso, e o modo
seguro de sessões compartilhadas do Selkies (`SELKIES_MASTER_TOKEN`).

## Capabilities

### New Capabilities

- `auth`: autenticação de usuário e ciclo de vida da sessão — login, logout,
  hash e verificação de senha, emissão, expiração e revogação de sessão.
- `user-management`: administração de contas e grupos — criação de usuário pelo
  admin, desabilitação, grupos e associação de usuários a grupos.
- `image-catalog`: registro das imagens webtop disponíveis, download da imagem e
  o estado de prontidão que determina se ela pode ser oferecida ao usuário.
- `access-control`: quais imagens cada usuário pode usar, via grants de grupo
  para imagem, incluindo o efeito de uma revogação sobre instâncias já rodando.
- `desktop-instances`: ciclo de vida das instâncias de desktop — criação, parada,
  exclusão, o volume persistente por usuário e imagem, o limite de uma instância
  por imagem e o desligamento por inatividade.
- `session-proxy`: acesso do navegador à instância em execução — autorização por
  propriedade, encaminhamento de HTTP e WebSocket, injeção da credencial interna
  e as garantias de isolamento entre usuários.

### Modified Capabilities

Nenhuma. O projeto não possui specs hoje (`openspec list --specs` retorna vazio).

## Impact

**Novo código, em um repositório hoje vazio:**

- Back-end Python com FastAPI, servindo API, front-end estático e o proxy de
  sessão no mesmo processo.
- Banco SQLite local, em modo WAL, com as tabelas de usuários, grupos, sessões,
  imagens, grants e instâncias.
- Front-end React com MUI. O Materialize original está sem manutenção ativa e seu
  wrapper para React está parado, então a linguagem visual Material vem do MUI.
- Adapter de runtime de containers sobre `aiodocker`, exposto por um protocolo
  com implementação falsa em memória para os testes.
- Caddy à frente do portal, apenas terminando TLS com certificado automático.
  Isso não é opcional: o cliente Selkies usa WebCodecs, que só funciona em
  secure context, e certificado self-signed é inviável para uma equipe.

**Dependências externas:** Docker Engine no host, imagens
`lscr.io/linuxserver/webtop` (2–4 GB cada), FastAPI, aiodocker, Argon2, React,
MUI, Caddy.

**Superfície de confiança:** o processo do portal precisa do socket do Docker
para criar containers. Como criar container permite montar o sistema de arquivos
do host, essa permissão equivale a root no host, e um `socket-proxy` restrito
**não** mitiga esse caso — a superfície que precisamos é exatamente a perigosa.
O portal é, portanto, um componente de confiança do plano de controle: mínimo,
sem executar código de usuário, e documentado como tal.

**Restrição de desempenho:** o stream de vídeo de cada sessão atravessa o
processo Python. O gargalo prático não é banda, é bloqueio — uma chamada Docker
síncrona travaria o event loop e congelaria o vídeo de todos os outros usuários
do mesmo worker. O desenho alvo é de 10 a 30 sessões simultâneas com um único
worker e nenhuma chamada bloqueante no caminho.
