# Spec Delta

## Purpose

Define o transporte do tráfego de sessão por um plano de dados externo ao
portal em produção, com a decisão de autorização permanecendo no portal —
removendo o stream do processo do portal sem enfraquecer as camadas de
segurança da sessão.

## ADDED Requirements

### Requirement: Tráfego de sessão não atravessa o portal em produção

Quando o plano de dados externo está no caminho, o transporte das requisições
e do canal persistente de uma instância NÃO DEVE passar pelo processo do
portal: apenas a decisão de autorização o atravessa, e o conteúdo da sessão
deve ir do cliente ao container direto pelo plano de dados.

#### Scenario: Stream ativo sem carga no portal

- **WHEN** uma sessão transporta tráfego intenso com o plano de dados ativo
- **THEN** os dados trafegam entre cliente e container pelo plano de dados
- **AND** o processo do portal não os recebe nem os reenvia

### Requirement: Encaminhamento pelo plano de dados exige aprovação prévia do portal

O plano de dados DEVE consultar a autorização interna do portal antes de
encaminhar qualquer requisição ao container e antes de estabelecer o canal
persistente, e NÃO DEVE encaminhar nada quando o portal não aprovar — inclusive
quando o portal estiver indisponível.

#### Scenario: Portal fora do ar recusa novas sessões

- **GIVEN** o plano de dados ativo e o portal indisponível
- **WHEN** uma requisição chega ao caminho de uma instância
- **THEN** nada é encaminhado ao container

#### Scenario: Recusa do portal bloqueia o canal persistente

- **WHEN** o portal recusa a autorização de abertura do canal persistente
- **THEN** o canal não é estabelecido

### Requirement: Autorização interna não é alcançável pela borda

O endpoint de autorização interna do portal NÃO DEVE ser acessível a partir
de fora da rede interna, e NÃO DEVE responder a decisões para requisições que
não venham do plano de dados configurado.

#### Scenario: Requisição externa ao endpoint interno

- **WHEN** alguém na internet requisita o endpoint de autorização interna
- **THEN** a borda não o expõe e a requisição não é atendida

### Requirement: Portal publica as rotas vivas no ciclo de vida

O portal DEVE publicar no plano de dados a rota de cada instância (seu nome de
container e a porta registrada no catálogo) ao criá-la ou iniciá-la, e DEVE
retirá-la ao pará-la ou excluí-la, de modo que o plano de dados só encaminhe a
containers vivos e na porta correta da imagem.

#### Scenario: Instância iniciada fica alcançável pelo plano de dados

- **WHEN** uma instância entra em execução
- **THEN** o plano de dados encaminha seu caminho ao container na porta da
  entrada do catálogo

#### Scenario: Instância parada deixa de ser encaminhada

- **WHEN** uma instância é parada ou excluída
- **THEN** o plano de dados deixa de encaminhar o caminho dela

### Requirement: Credencial da instância transita sem chegar ao cliente

A credencial da instância DEVE viajar do portal para o plano de dados na
resposta da autorização e do plano de dados para o container na requisição
encaminhada, e NUNCA DEVE ser devolvida ao cliente — nem em respostas de
erro, nem em cabeçalhos refletidos.

#### Scenario: Resposta de autorização não vaza credencial

- **WHEN** o plano de dados consulta a autorização de uma requisição
- **THEN** a resposta com a credencial é consumida pelo plano de dados e não
  é reenviada ao cliente

#### Scenario: Credencial do cliente é descartada no plano de dados

- **WHEN** a requisição do cliente traz credencial própria
- **THEN** apenas a credencial da instância chega ao container

### Requirement: Detecção de ociosidade permanece equivalente sem tráfego no portal

Com o plano de dados ativo, o portal DEVE continuar registrando atividade
suficiente para a detecção de ociosidade — pelas autorizações e pelo
heartbeat da visão de sessão — e NÃO DEVE persistir marca de atividade por
mensagem trafegada.

#### Scenario: Uso só no terminal não é marcado como ocioso

- **GIVEN** uma sessão ativa apenas pelo canal persistente, sem requisições
  HTTP
- **WHEN** o usuário interage com a visão de sessão aberta
- **THEN** o heartbeat registra atividade e a instância não é considerada
  ociosa

#### Scenario: Visão de sessão fechada deixa de registrar atividade

- **WHEN** a visão de sessão é fechada e nenhuma autorização ocorre
- **THEN** a marca de atividade deixa de ser renovada e a ociosidade progride
  como hoje

### Requirement: Caminho no portal permanece para desenvolvimento

Sem o plano de dados externo, o sistema DEVE continuar entregando as sessões
pelo caminho atual dentro do portal, com os mesmos comportamentos de
autorização e transporte, para que desenvolvimento e testes não exijam o
proxy externo.

#### Scenario: Dev stack sem Caddy entrega sessão

- **WHEN** o portal sobe em desenvolvimento, sem plano de dados externo
- **THEN** a sessão é entregue pelo caminho dentro do portal, como hoje
