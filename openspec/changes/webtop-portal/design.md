# Design

## Context

Projeto greenfield. Ver `proposal.md` — Why para a motivação, e os arquivos em
`specs/` para os requisitos de comportamento.

As restrições que moldam este desenho vêm quase todas da plataforma Selkies, que
substituiu o KasmVNC nas imagens webtop em junho de 2025:

- A porta `3000` serve HTTP e existe **apenas** para ficar atrás de proxy; a `3001`
  serve HTTPS com certificado self-signed. A documentação orienta proxiar a `3000`
  e terminar TLS no proxy, sem TLS duplo.
- **Todo o streaming anda num único WebSocket.** A documentação diz explicitamente
  que não são necessárias regras por caminho: o Nginx interno do container roteia
  tudo, então o container é proxiado como uma única location.
- O navegador precisa alcançar o portal por **HTTPS**, porque o cliente usa
  WebCodecs, que só funciona em secure context. `http://localhost` conta como
  secure context, o que viabiliza o desenvolvimento local sem TLS.
- A variável `SUBFOLDER=/caminho/` faz o container reescrever todas as suas rotas
  internas sob um prefixo.
- O CSP padrão do container é `frame-ancestors 'self'`.
- O transporte WebRTC opcional faz a **mídia trafegar por UDP, por fora do proxy**.
- Timeouts internos do Nginx do container são de 3600s; proxies à frente precisam
  acompanhar, e a documentação alerta que buffering de resposta quebra o stream.

Alvo operacional: 10 a 30 sessões simultâneas, um único host Docker.

## Goals / Non-Goals

**Goals:**

- Tornar o isolamento entre usuários uma propriedade da topologia de rede, não
  apenas o resultado de uma verificação em código.
- Manter o caminho de dados livre de bloqueio, para que uma operação de container
  nunca congele o vídeo de outras sessões.
- Deixar quase toda a suíte de testes executável sem Docker instalado.
- Servir tudo numa origem única, para que a sessão possa ser embutida sem relaxar
  o CSP do container.

**Non-Goals:**

- Escalar horizontalmente o processo do portal. O desenho assume um worker; o
  caminho para múltiplos workers está descrito mas não implementado.
- Suportar mais de um host Docker ou qualquer forma de agendamento distribuído.
- Isolar o processo do portal do daemon Docker. Isso é declaradamente impossível
  dada a superfície necessária, e está documentado como risco aceito.

## Decisions

### D1. O proxy de sessão vive dentro do FastAPI, numa origem única

O portal serve o front-end, a API e o encaminhamento das sessões no mesmo
processo e na mesma origem. Cada instância recebe o caminho `/i/<uuid>/`, e o
container é criado com `SUBFOLDER=/i/<uuid>/` para que suas rotas internas
coincidam com esse prefixo.

```
                       BROWSER (dono da instancia)
                             |
                     HTTPS (Let's Encrypt)
                             v
                 +-----------------------+
                 |  Caddy  (so TLS)      |
                 +-----------+-----------+
                             | HTTP + WS
                             v
      +---------------------------------------------------+
      |                   FastAPI                         |
      |  /            front-end (React build estatico)    |
      |  /api/*       auth, catalogo, instancias, admin    |
      |  /i/{uuid}/*  encaminhamento HTTP + WS            |
      |                   |                               |
      |                   +-- sessao valida?              |
      |                   +-- dono da instancia?          |
      |                   +-- instancia em execucao?      |
      |                   +-- injeta Authorization        |
      +-------------------|-------------------------------+
                          |
                 rede docker wcui_net
            *** containers sem porta publicada ***
                          v
        +-------------+  +-------------+  +-------------+
        |  webtop A   |  |  webtop B   |  |  webtop C   |
        |   :3000     |  |   :3000     |  |   :3000     |
        | SUBFOLDER=  |  | SUBFOLDER=  |  | SUBFOLDER=  |
        | /i/<ua>/    |  | /i/<ub>/    |  | /i/<uc>/    |
        +-------------+  +-------------+  +-------------+
```

**Por que origem única e não subdomínio por instância:** o container envia
`frame-ancestors 'self'`. Com caminho na mesma origem, embutir a sessão em iframe
funciona sem configurar nada. Com subdomínio por instância, seria necessário
relaxar `SELKIES_FRAME_ANCESTORS` em cada container, além de certificado wildcard
e DNS dinâmico.

**Alternativas consideradas:**

- *Publicar portas no host e redirecionar o usuário para `host:porta`.* Descartada:
  qualquer pessoa que descubra a porta alcança o desktop, e o requisito central é
  justamente impedir isso. A verificação de dono deixaria de existir no caminho de
  dados.
- *Proxy externo (Caddy ou Traefik) fazendo o roteamento das sessões com
  forward-auth no FastAPI.* É a opção correta a partir de ~50 sessões, porque o
  stream deixa de atravessar o Python. Descartada agora por acrescentar roteamento
  dinâmico, descoberta de containers e um segundo ponto onde a autorização pode
  divergir, sem benefício na faixa de 10 a 30 sessões.

### D2. Containers não publicam porta; o isolamento é topológico

Os containers são criados sem `-p`, conectados à rede `wcui_net`. O processo do
portal roda em container na mesma rede e alcança cada webtop pelo nome via DNS
embutido do Docker.

A consequência é a que importa: **não existe endereço alternativo**. Mesmo que a
verificação de propriedade tivesse um defeito, não há rota da LAN nem do host
para o container de outra pessoa. A verificação no encaminhamento é a segunda
camada, e a credencial interna por instância é a terceira.

**Alternativa considerada:** *publicar em `127.0.0.1:<efêmera>` e rodar o portal no
host.* Desenvolvimento local fica bem mais simples, mas qualquer processo do host
passa a alcançar qualquer desktop, o que enfraquece o requisito central.

### D3. Um worker, `aiodocker`, nenhuma chamada bloqueante

O risco dominante do desenho não é banda, é bloqueio. O cliente Docker síncrono
chamado dentro de um handler assíncrono travaria o event loop — o mesmo loop que
repassa frames de todas as outras sessões daquele processo. Como as imagens webtop
têm 2 a 4 GB, um download no caminho de uma requisição congelaria todas as sessões
por minutos.

A conta a favor de um worker: 30 sessões a ~3 Mbps somam algo entre 400 e 1400
mensagens WebSocket por segundo de repasse de bytes, sem parsing. Um event loop
asyncio sustenta isso com folga **desde que nada o bloqueie**. Logo, a decisão
correta é eliminar o bloqueio, não multiplicar processos.

Um worker também resolve, de graça, três problemas que vários workers criariam: o
loop do reaper tem dono único, a reconciliação de estado tem dono único, e o
SQLite tem um único escritor.

**Alternativas consideradas:**

- *`docker-py` em thread pool.* Mantém a biblioteca mais madura, mas ainda disputa
  o GIL durante o download e deixa o loop do reaper duplicado por worker.
- *N workers mais um processo orquestrador dono do Docker.* É o caminho de
  crescimento correto, registrado aqui para quando a medição exigir. Construir
  agora seria resolver um problema que o alvo de escala não tem.

### D4. Caddy à frente, apenas terminando TLS

WebCodecs exige secure context, e certificado self-signed é inviável para uma
equipe — cada pessoa clicaria em aviso de segurança. Caddy obtém certificado
automaticamente e repassa HTTP e WebSocket ao portal.

Isso **não** é a alternativa de proxy externo da D1: Caddy aqui não conhece
instâncias nem autorização. A configuração é um `reverse_proxy` único, sem
roteamento dinâmico. Em desenvolvimento, Caddy sai da composição e o acesso é por
`http://localhost`, que já é secure context.

### D5. SQLite em modo WAL, com o modelo de dados abaixo

```
users           id, email UNIQUE, password_hash, is_admin,
                disabled_at, created_at

sessions        token_hash PK, user_id, created_at,
                expires_at, revoked_at

groups          id, name UNIQUE, created_at

user_groups     user_id, group_id          UNIQUE (user_id, group_id)

images          id, display_name, repository, tag,
                shm_size, mem_limit, cpu_limit,
                harden_desktop, enabled,
                pull_state, pull_progress, pull_error,
                created_at                 UNIQUE (repository, tag)

group_images    group_id, image_id         UNIQUE (group_id, image_id)

instances       id (uuid, vai na URL), user_id, image_id,
                container_id, container_name, volume_name,
                inner_user, inner_password,
                state, error_message,
                created_at, last_seen_at, deleted_at

                UNIQUE (user_id, image_id) WHERE deleted_at IS NULL
```

O índice único parcial é o que implementa "uma instância por par usuário e
imagem" sem impedir que o usuário crie outra depois de excluir a anterior.

A permissão é resolvida por junção, não materializada:

```
  permitido(u, i)  <=>  EXISTS (
      user_groups ug JOIN group_images gi ON gi.group_id = ug.group_id
      WHERE ug.user_id = u AND gi.image_id = i )
```

Isso dá de graça o requisito de "mudança de grupo vale na consulta seguinte" e o
caso de permissão remanescente por um segundo grupo após uma revogação.

Modo WAL com `busy_timeout` e transações curtas. Com um escritor e volume de
escrita baixo — mudanças de estado de instância, não tráfego — não há contenção
esperada.

**Sobre `inner_password` em texto plano:** cifrar no SQLite com uma chave que mora
ao lado do arquivo é teatro. A função dessa credencial é barrar *outros* usuários,
não o dono, que tem root dentro do próprio container de qualquer forma. A decisão é
armazenar em texto plano e tratar o arquivo do banco como tão sensível quanto o
socket do Docker, documentando isso em vez de simular proteção.

### D6. Configuração obrigatória de endurecimento do container

Toda instância é criada com:

```
  SUBFOLDER=/i/<uuid>/
  CUSTOM_USER=<aleatorio>        PASSWORD=<aleatorio>
  SELKIES_ENABLE_SHARING=false   SELKIES_ENABLE_SHARED=false
  PUID / PGID / TZ
  shm_size, mem_limit, cpu_limit vindos da entrada do catálogo
  volume wcui_<user>_<image>:/config
  rede wcui_net, nenhuma porta publicada
  transporte WebRTC não habilitado
```

Os dois primeiros flags de sharing não são opcionais: os links nativos de
compartilhamento concedem controle total da sessão, incluindo o terminal com
`sudo` sem senha, a quem tiver o endereço, e não carregam autenticação própria.
Mantê-los ligados anularia o requisito de isolamento.

O transporte WebRTC fica desligado por um motivo estrutural: sua mídia trafega por
UDP **por fora** do encaminhamento, portanto por fora da autorização.

`HARDEN_DESKTOP` desliga `sudo` e terminais. Fica como flag opcional por entrada do
catálogo, **desligada por padrão** — o propósito do produto é dar um Linux de
verdade ao usuário, e remover o terminal o anularia. A flag serve a imagens de
quiosque no futuro.

### D7. `ContainerRuntime` como protocolo, com implementação falsa

Todo acesso ao Docker passa por um protocolo estreito: criar, iniciar, parar,
remover, inspecionar, garantir volume, remover volume, baixar imagem com
progresso. Duas implementações: uma sobre `aiodocker` e uma falsa em memória.

Essa é a única decisão que determina se a suíte será rápida e confiável ou lenta e
instável. Camadas de teste:

```
  camada       o que roda de verdade              o que e falso
  ---------------------------------------------------------------------
  dominio      resolucao de permissao,            todo IO
               maquina de estados, quota
  api          FastAPI via httpx ASGITransport,   ContainerRuntime
               SQLite temporario real
  proxy        FastAPI + servidor WS falso        Docker
               que ecoa mensagens
  e2e          Docker real + 1 webtop real        nada
  (opt-in,
   marcado)
```

O encaminhamento, que é a parte mais arriscada, fica testável sem Docker: um
servidor WebSocket falso que ecoa permite afirmar que o não dono recebe recusa,
que o prefixo é reescrito, que `Authorization` é injetado e que o
`Authorization` do cliente é descartado, e que mensagens trafegam nos dois
sentidos.

### D8. Atividade com debounce, reaper no `lifespan`

O encaminhamento vê centenas de mensagens por segundo. Gravar `last_seen_at` a
cada mensagem destruiria o banco. A marca fica em memória e é persistida no
máximo a cada 30 segundos por instância.

O reaper e a reconciliação de estado são tarefas de fundo iniciadas no `lifespan`
do FastAPI. Isso é correto exatamente porque há um único worker — e é mais uma
razão para a D3.

### D9. MUI no lugar de Materialize

O Materialize original está sem manutenção ativa e o wrapper `react-materialize`
está parado. MUI entrega a mesma linguagem visual Material com componentes React
mantidos, tema e acessibilidade prontos. O custo é bundle maior, irrelevante para
um portal interno.

## Risks / Trade-offs

**O processo do portal equivale a root no host** → Não mitigável por
`socket-proxy`: a superfície necessária inclui criar container, e quem cria
container pode montar o sistema de arquivos do host. Mitigação real: tratar o
portal como componente de confiança do plano de controle — imagem mínima, nenhum
código de usuário executado nele, e o risco documentado explicitamente em vez de
disfarçado.

**O usuário tem root dentro do próprio container** → Inerente à imagem webtop,
que embute terminal com `sudo` sem senha. A documentação da LinuxServer orienta
tratar uma sessão como um login SSH. Mitigação: não usar `--privileged`, não
montar o socket do Docker nos containers de desktop, e limites de recurso por
entrada do catálogo. Um usuário mal-intencionado ainda pode sondar a rede interna
— restringir `wcui_net` fica registrado como trabalho futuro, pois o portal
precisa estar alcançável nela.

**O stream atravessa o Python** → Teto prático em algumas dezenas de sessões.
Mitigação: medir throughput e latência no marco de testes, e manter o caminho de
crescimento da D1 (proxy externo com forward-auth) registrado.

**Um worker é ponto único de falha** → Uma exceção não tratada no loop derruba
todas as sessões. Mitigação: `restart: unless-stopped` na composição, tarefas de
fundo com tratamento de exceção que não deixa a task morrer silenciosamente, e
reconciliação de estado no start para recuperar a visão dos containers vivos.

**Volume por usuário e imagem cresce sem limite** → Disco pode encher. Mitigação
nesta change: o `delete` remove o volume, dando ao usuário um caminho de limpeza,
e o painel admin lista instâncias com tempo de ociosidade. Quota de disco e
remoção automática por idade ficam fora de escopo.

**Parada por inatividade pode surpreender** → O usuário pode voltar e encontrar a
sessão encerrada. Mitigação: o volume é preservado, então reiniciar recupera os
arquivos; a interface informa o limite de inatividade e o estado parado.

**`docker pause` ausente pode ser pedido depois** → Registrado como decisão
consciente: pause congela CPU mas não libera memória, então não atende a economia
de recurso, e deixaria a aba aparentemente travada por manter o WebSocket aberto
sem tráfego.

## Migration Plan

Não há migração: o repositório está vazio e não existe sistema em produção.

**Implantação:** uma composição Docker com três serviços — Caddy, o portal e o
volume do SQLite — mais a rede `wcui_net` criada pela composição. O portal monta o
socket do Docker. O primeiro administrador nasce de variáveis de ambiente lidas na
primeira inicialização, com banco vazio.

**Ordem de subida:** criar a rede, subir o portal (que aplica o schema e provisiona
o administrador), subir o Caddy. O administrador então registra as imagens, cujo
download ocorre em segundo plano, e cria grupos e usuários.

**Desenvolvimento:** sem Caddy; `http://localhost` já é secure context. O portal
roda com reload e o Vite serve o front-end. Os testes, exceto os marcados como
e2e, não exigem Docker.

**Reversão:** derrubar a composição. Os volumes dos desktops e o arquivo SQLite
sobrevivem, pois são volumes nomeados. Reverter uma mudança de schema exige
restaurar o arquivo do banco, que é um único arquivo e deve ser copiado antes de
qualquer migração.

## Open Questions

- Valor padrão do limite de inatividade. A proposta é 30 minutos; a configuração é
  requisito de spec, o número não é, e pode ser calibrado após observar uso real.
- Limiares da validação de complexidade da senha inicial definida pelo
  administrador — comprimento mínimo e quais classes de caractere exigir. A
  validação existe; os limiares são calibração.
- Se o painel administrativo precisa de paginação e busca desde o início, ou se as
  listagens simples bastam para a ordem de grandeza de 30 usuários.
- Se vale expor um endpoint de métricas além do `health` que a composição exige.

Fora de escopo por decisão, não por pendência: troca obrigatória de senha no
primeiro login e autosserviço de redefinição de senha. Nenhum spec os requer, e
ambos acrescentariam fluxo de autenticação; se forem desejados, entram como change
própria.
