# Spec Delta

## Purpose

Dá a cada usuário uma identidade SSH própria, gerada e guardada pelo
portal, disponível automaticamente em qualquer instância dele, para que
`git` dentro do container autentique com repositórios remotos sem
configuração manual.

## ADDED Requirements

### Requirement: Usuário tem uma identidade SSH própria, gerada pelo portal

O sistema DEVE gerar e manter um par de chaves SSH por usuário, usado para
autenticar `git`/`ssh` dentro das instâncias desse usuário. O sistema NÃO
DEVE aceitar uma chave privada trazida pelo usuário.

#### Scenario: Identidade gerada sob demanda

- **WHEN** um usuário sem identidade SSH ainda consulta sua chave pública ou
  tem uma instância criada pela primeira vez
- **THEN** o sistema gera a identidade antes de prosseguir

#### Scenario: Importação de chave existente é recusada

- **WHEN** um usuário tenta fornecer uma chave privada já existente para uso
  como sua identidade
- **THEN** o sistema recusa a operação

### Requirement: Chave privada é armazenada cifrada em repouso

A chave privada de cada identidade DEVE ser armazenada cifrada. O sistema
NÃO DEVE expor a chave privada por nenhuma interface voltada ao usuário —
apenas a chave pública.

#### Scenario: Consulta de identidade retorna só a chave pública

- **WHEN** um usuário consulta sua identidade SSH
- **THEN** o sistema retorna a chave pública
- **AND** a chave privada não é incluída na resposta

### Requirement: Identidade SSH é privada ao usuário dono

O sistema DEVE restringir a consulta e a regeneração de uma identidade SSH
ao próprio usuário dono.

#### Scenario: Outro usuário tenta acessar identidade alheia

- **WHEN** um usuário autenticado tenta consultar ou regenerar a identidade
  SSH de outro usuário
- **THEN** o sistema recusa a operação

### Requirement: Toda instância criada recebe a identidade SSH do dono

Ao criar o container de uma instância, de qualquer imagem (agente ou
webtop), o sistema DEVE disponibilizar nele a chave privada, a chave
pública e um `known_hosts` pré-cadastrado com GitHub, GitLab e Bitbucket da
identidade do dono, prontos para uso por `git`/`ssh` sem configuração
manual.

#### Scenario: Instância pronta já tem a identidade disponível

- **WHEN** uma instância de qualquer imagem é criada para um usuário com
  identidade SSH
- **THEN** `git`/`ssh` dentro do container encontram a chave privada, a
  pública e o `known_hosts` da identidade do dono, sem configuração manual

#### Scenario: Mesma identidade em imagens diferentes

- **GIVEN** um usuário com instâncias de imagens diferentes (por exemplo um
  agente e um webtop)
- **WHEN** cada uma dessas instâncias é criada
- **THEN** todas recebem a mesma identidade SSH desse usuário

### Requirement: Identidade permanece disponível enquanto a instância existir

Parar e religar uma instância NÃO DEVE exigir reconfiguração da identidade
SSH — ela permanece disponível como foi injetada na criação.

#### Scenario: Instância parada e religada

- **GIVEN** uma instância cuja identidade SSH já foi injetada
- **WHEN** a instância é parada e religada
- **THEN** a identidade SSH continua disponível, sem nova ação do sistema

### Requirement: Usuário pode regenerar sua identidade SSH

O sistema DEVE permitir ao usuário gerar uma nova identidade SSH,
substituindo a anterior. A chave pública antiga deixa de corresponder à
nova chave privada.

#### Scenario: Regeneração troca a chave pública exibida

- **WHEN** o usuário aciona a regeneração da identidade SSH
- **THEN** uma nova chave pública é exibida, diferente da anterior

### Requirement: Regeneração propaga para instâncias existentes

Ao regenerar a identidade, o sistema DEVE atualizá-la em todas as
instâncias vivas do usuário — em execução ou paradas —, não apenas nas
criadas depois.

#### Scenario: Regeneração atualiza instâncias em execução e paradas

- **GIVEN** um usuário com uma instância em execução e outra parada
- **WHEN** ele regenera sua identidade SSH
- **THEN** ambas as instâncias passam a ter a nova identidade

#### Scenario: Falha ao atualizar uma instância não impede as demais

- **GIVEN** um usuário com mais de uma instância viva
- **WHEN** a atualização da identidade falha numa delas durante a
  regeneração
- **THEN** as demais instâncias ainda são atualizadas
- **AND** a falha na instância afetada é reportada ao usuário
