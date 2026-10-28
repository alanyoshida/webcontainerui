# Tasks

Referências: `specs/` define o comportamento exigido, `design.md` define a
abordagem. Os identificadores de decisão (D1–D9) remetem a `design.md`.

## 1. Fundação do projeto

- [x] 1.1 Criar a estrutura do repositório (`backend/`, `frontend/`, `deploy/`) e verificar que `python -c "import app"` e `npm ci` executam sem erro em cada lado
- [x] 1.2 Declarar as dependências do back-end (FastAPI, uvicorn, aiodocker, argon2-cffi, pydantic-settings, pytest, pytest-asyncio, httpx) e verificar que a instalação em ambiente limpo conclui
- [x] 1.3 Declarar as dependências do front-end (React, MUI, Vite, Vitest) conforme D9 e verificar que `npm run build` produz o bundle
- [x] 1.4 Configurar o runner de testes com marcador `e2e` registrado e desselecionado por padrão, e verificar que `pytest` coleta zero testes e `pytest -m e2e` os seleciona
- [x] 1.5 Escrever `README.md` com a arquitetura de origem única, o alvo de escala e o aviso de que o processo do portal equivale a root no host, e verificar que os comandos citados executam como escritos

## 2. Persistência e configuração

- [x] 2.1 Implementar a carga de configuração por ambiente (caminho do banco, rede Docker, credenciais do primeiro administrador, limite de inatividade, limites de recurso padrão) e verificar com teste que valores ausentes usam o padrão e valores inválidos falham na inicialização
- [x] 2.2 Criar o schema do SQLite conforme D5, incluindo o índice único parcial de `instances` sobre `(user_id, image_id)` com `deleted_at IS NULL`, e verificar com teste que a segunda inserção viva é rejeitada e que após `deleted_at` uma nova é aceita
- [x] 2.3 Habilitar modo WAL e `busy_timeout` na abertura da conexão e verificar com teste que `PRAGMA journal_mode` retorna `wal`
- [x] 2.4 Implementar a fixture de banco temporário por teste e verificar que dois testes em sequência não compartilham estado

## 3. Autenticação e sessão

- [x] 3.1 Implementar hash e verificação de senha com Argon2 e verificar com teste que o hash tem sal, que a senha correta valida e que a incorreta não
- [x] 3.2 Implementar emissão, consulta, expiração e revogação de sessão e verificar com testes os cenários de `specs/auth/spec.md` para sessão expirada e token reapresentado após logout
- [x] 3.3 Implementar o endpoint de login com resposta indistinguível entre identificador inexistente e senha incorreta, e verificar com teste que status e corpo são idênticos nos dois casos
- [x] 3.4 Implementar a dependência de autenticação e aplicá-la a todas as rotas não públicas, verificando com teste que requisição anônima a rota protegida recebe não autenticado
- [x] 3.5 Emitir o cookie de sessão com `HttpOnly`, `SameSite` e `Secure` condicionado a HTTPS, e verificar com teste os atributos presentes na resposta
- [x] 3.6 Implementar logout com revogação e verificar com teste que o token revogado deixa de autenticar

## 4. Usuários, grupos e provisionamento do administrador

- [x] 4.1 Implementar a dependência de autorização de administrador e verificar com teste que usuário comum recebe recusa em rota administrativa
- [x] 4.2 Implementar criação de usuário pelo administrador com validação de complexidade da senha inicial e unicidade do e-mail, verificando com testes o caminho de sucesso e o conflito de e-mail já usado
- [x] 4.3 Confirmar que não existe rota de auto-cadastro e verificar com teste que nenhuma rota pública cria usuário
- [x] 4.4 Implementar desabilitação de conta com revogação das sessões existentes e verificar com testes os dois cenários de `specs/auth/spec.md` e `specs/user-management/spec.md` relativos a conta desabilitada
- [x] 4.5 Implementar criação, renomeação e remoção de grupo com nome único, verificando com testes o conflito de nome e que a remoção preserva as contas dos membros
- [x] 4.6 Implementar inclusão e remoção de membros, verificando com teste que um usuário pode pertencer a vários grupos e que remover de um preserva os demais
- [x] 4.7 Implementar o provisionamento do primeiro administrador na inicialização com banco vazio e verificar com testes que a conta nasce no banco vazio e que uma segunda inicialização não cria nem sobrescreve nada

## 5. Runtime de containers e seu substituto de teste

- [x] 5.1 Definir o protocolo `ContainerRuntime` conforme D7, cobrindo criar, iniciar, parar, remover, inspecionar, garantir volume, remover volume e baixar imagem com progresso, e verificar que o módulo passa a checagem de tipos
- [x] 5.2 Implementar o runtime falso em memória com estados de container e volumes, e verificar com testes que ele reproduz a máquina de estados e permite injetar falhas
- [x] 5.3 Implementar o runtime sobre `aiodocker` sem nenhuma chamada bloqueante conforme D3, e verificar por inspeção que nenhuma chamada síncrona do cliente Docker é feita fora de contexto assíncrono
- [x] 5.4 Escrever teste que exercita operação de container concorrente com tráfego simulado e verificar que o tráfego continua fluindo durante a operação, cobrindo o cenário de não bloqueio de `specs/desktop-instances/spec.md`
- [x] 5.5 Documentar em `deploy/` por que `socket-proxy` não mitiga este caso de uso e verificar que o texto corresponde ao risco registrado em `design.md`

## 6. Catálogo de imagens

- [x] 6.1 Implementar o registro de entrada do catálogo com unicidade de repositório e tag e limites de recurso com padrão, verificando com testes o conflito e o preenchimento dos padrões quando omitidos
- [x] 6.2 Implementar o download em segundo plano disparado no registro, com estados de progresso, pronta e falha, verificando com testes que o registro responde sem esperar o download e que cada transição de estado é observável
- [x] 6.3 Implementar nova tentativa de download sobre entrada em falha e verificar com teste que a entrada volta ao estado de download sem ser recriada
- [x] 6.4 Implementar a desabilitação de entrada e verificar com teste que ela sai do catálogo do usuário e que novas instâncias dela são recusadas
- [x] 6.5 Implementar o filtro do catálogo do usuário por habilitada, pronta e permitida, verificando com teste que imagem permitida mas ainda em download não aparece

## 7. Controle de acesso por grupo

- [x] 7.1 Implementar a resolução de permissão por junção conforme D5 e verificar com testes os cenários de `specs/access-control/spec.md` para permissão vinda de um entre vários grupos e para nenhum grupo com concessão
- [x] 7.2 Implementar concessão idempotente de imagem a grupo e verificar com teste que a concessão repetida é aceita sem duplicar
- [x] 7.3 Implementar a pré-visualização do impacto de uma revogação e verificar com teste que o número de instâncias afetadas é informado e que nada muda sem confirmação
- [x] 7.4 Implementar a revogação com parada das instâncias afetadas e preservação dos volumes, verificando com testes a revogação com instância em execução e o caso de permissão remanescente por outro grupo
- [x] 7.5 Verificar com teste que a permissão reflete mudança de grupo na consulta seguinte, sem novo login
- [x] 7.6 Verificar com teste que usuário sem nenhum grupo autentica, recebe catálogo vazio e tem a criação de instância recusada

## 8. Ciclo de vida das instâncias

- [x] 8.1 Implementar a criação de instância com geração de identificador, credencial interna aleatória por instância e volume por usuário e imagem, verificando com testes que duas instâncias recebem credenciais distintas e que o volume é nomeado por par
- [x] 8.2 Aplicar na criação a configuração obrigatória de D6 e verificar com teste que o container nasce sem porta publicada, na rede interna, com `SUBFOLDER` da instância, sharing desabilitado e WebRTC não habilitado
- [x] 8.3 Implementar o limite de uma instância por par usuário e imagem e verificar com testes que o segundo pedido da mesma imagem devolve a existente e que imagens diferentes coexistem
- [x] 8.4 Implementar a recusa de criação sobre imagem não pronta, não habilitada ou não permitida, verificando com testes os três casos
- [x] 8.5 Implementar parar instância preservando o volume e verificar com teste que o container encerra e o volume permanece
- [x] 8.6 Implementar excluir instância com remoção de container e volume exigindo confirmação explícita, verificando com testes que sem confirmação nada é removido e que após a exclusão uma nova instância da mesma imagem pode ser criada
- [x] 8.7 Implementar a autorização de propriedade nas ações de ciclo de vida e na listagem, verificando com testes que ação sobre instância de outro é recusada sem revelar existência e que a listagem retorna apenas as do solicitante
- [x] 8.8 Implementar o tratamento de falha de criação ou início com estado de erro e sem container órfão, verificando com teste que injeta falha no runtime falso
- [x] 8.9 Implementar a parada das instâncias ao desabilitar a conta e verificar com teste que a instância para e o volume é preservado

## 9. Encaminhamento da sessão

- [x] 9.1 Implementar o servidor WebSocket falso que ecoa mensagens, para uso dos testes de encaminhamento, e verificar que ele aceita conexão e devolve o que recebe
- [x] 9.2 Implementar o encaminhamento HTTP de `/i/{uuid}/*` com verificação de sessão, propriedade e estado em execução, verificando com testes que anônimo é recusado, que não dono é recusado e que instância inexistente e instância de outro produzem respostas indistinguíveis
- [x] 9.3 Implementar a injeção da credencial interna e o descarte da credencial enviada pelo cliente, verificando com testes que a requisição encaminhada carrega a da instância e que a do cliente não é repassada
- [x] 9.4 Implementar o encaminhamento do canal WebSocket com as mesmas verificações e repasse nos dois sentidos, verificando com testes que o não dono não estabelece o canal e que as mensagens chegam com conteúdo preservado em ambas as direções
- [x] 9.5 Configurar timeouts longos e desabilitar o acúmulo em buffer conforme as restrições de `design.md`, verificando com testes que canal sem tráfego por período prolongado permanece aberto e que fluxo contínuo é repassado conforme chega
- [x] 9.6 Implementar o registro de atividade com debounce conforme D8 e verificar com teste que tráfego intenso gera no máximo uma escrita por janela e que a instância não é considerada ociosa
- [x] 9.7 Implementar as respostas de instância parada e de container inalcançável, verificando com testes que a parada não é encaminhada e que a indisponibilidade não revela endereço nem nome interno
- [x] 9.8 Escrever teste de isolamento com dois usuários autenticados simultaneamente, cada um com instância da mesma imagem, verificando que nenhum alcança a do outro por HTTP ou por WebSocket

## 10. Tarefas de fundo

- [x] 10.1 Implementar o reaper de ociosidade no `lifespan` conforme D8 e verificar com testes que instância além do limite é parada com volume preservado e que sessão com tráfego contínuo não é parada
- [x] 10.2 Implementar a reconciliação entre estado registrado e estado real do container e verificar com teste que container encerrado por fora passa a constar como parado
- [x] 10.3 Garantir que as tarefas de fundo sobrevivam a exceção em uma iteração e verificar com teste que uma falha injetada não encerra o loop

## 11. Interface web

- [x] 11.1 Implementar o shell da aplicação com tema MUI e roteamento, e verificar que o build conclui e a rota raiz renderiza
- [x] 11.2 Implementar a tela de login consumindo o endpoint de autenticação e verificar com teste de componente que credencial inválida exibe erro sem distinguir os casos
- [x] 11.3 Implementar a tela de catálogo listando apenas imagens prontas e permitidas, e verificar com teste de componente que catálogo vazio exibe estado vazio explicativo
- [x] 11.4 Implementar a tela de instâncias com os estados em execução, parada, iniciando e erro, e as ações iniciar, parar e excluir, verificando com teste de componente que nenhuma ação de pausa é oferecida e que excluir exige confirmação
- [x] 11.5 Implementar a exibição da sessão embutida em iframe apontando para o caminho da instância, e verificar com teste de componente que o endereço usado é o da própria origem
- [x] 11.6 Implementar o painel administrativo de usuários, grupos, catálogo e concessões, incluindo a confirmação de revogação com o número de instâncias afetadas, e verificar com testes de componente os fluxos de criação e de revogação
- [x] 11.7 Exibir o limite de inatividade e o estado parado na interface, e verificar com teste de componente que a explicação aparece quando a instância está parada

## 12. Implantação

- [x] 12.1 Escrever a composição de produção com Caddy, portal e rede `wcui_net` conforme D4, e verificar que `docker compose config` valida
- [x] 12.2 Escrever a configuração do Caddy terminando TLS e repassando HTTP e WebSocket, e verificar que a configuração passa em `caddy validate`
- [x] 12.3 Escrever a composição de desenvolvimento sem Caddy, servindo em `http://localhost`, e verificar que o portal responde e o front-end carrega
- [x] 12.4 Implementar o endpoint de health usado pela composição e verificar que ele responde com o estado da conexão ao banco e ao Docker
- [x] 12.5 Documentar em `deploy/README.md` a ordem de subida, as variáveis de ambiente, a reversão e a cópia do arquivo SQLite antes de migração, verificando que os comandos executam como escritos

## 13. Verificação integrada

- [x] 13.1 Escrever o teste e2e marcado, opt-in, que sobe um webtop real e verifica que o dono alcança a sessão e que outro usuário não, confirmando que `pytest -m e2e` passa com Docker disponível
- [x] 13.2 Medir throughput e latência do encaminhamento com várias sessões simuladas e registrar o resultado, verificando se o alvo de 10 a 30 sessões se sustenta num worker conforme D3
- [x] 13.3 Executar a suíte completa sem Docker instalado e verificar que todos os testes não marcados como e2e passam
- [x] 13.4 Revisar a cobertura de testes contra os cenários de segurança dos specs e verificar que cada um tem teste correspondente: acesso a instância de outro, requisição anônima, imagem sem concessão, usuário desabilitado e concessão revogada
