# Spec Delta

## Purpose

Decide quais imagens de desktop cada usuário pode usar, concedendo permissão a
grupos em vez de a pessoas individuais, e define o que acontece com instâncias já
em execução quando uma permissão é retirada.

## ADDED Requirements

### Requirement: Permissão é concedida a grupo, não a usuário

O sistema DEVE conceder acesso a uma imagem associando-a a um grupo. NÃO DEVE
existir concessão dirigida diretamente a um usuário.

#### Scenario: Concessão a grupo

- **WHEN** um administrador concede uma imagem a um grupo
- **THEN** todos os membros atuais daquele grupo passam a ter permissão sobre ela

### Requirement: Somente administrador concede ou revoga permissão

O sistema DEVE restringir a concessão e a revogação de permissões a usuários com
papel de administrador.

#### Scenario: Usuário comum tenta conceder permissão

- **WHEN** um usuário sem papel de administrador tenta conceder uma imagem
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** nenhuma permissão é alterada

### Requirement: Permissão do usuário é a união das permissões de seus grupos

O sistema DEVE considerar um usuário autorizado a usar uma imagem quando pelo
menos um de seus grupos tiver concessão sobre ela.

#### Scenario: Permissão vinda de um entre vários grupos

- **GIVEN** um usuário membro dos grupos A e B, onde só B tem concessão da imagem
- **WHEN** o sistema resolve a permissão desse usuário sobre a imagem
- **THEN** o usuário é considerado autorizado

#### Scenario: Nenhum grupo com concessão

- **GIVEN** um usuário cujos grupos não têm concessão sobre a imagem
- **WHEN** o sistema resolve a permissão desse usuário sobre a imagem
- **THEN** o usuário é considerado não autorizado

### Requirement: Mudança de associação a grupo altera a permissão imediatamente

O sistema DEVE recalcular a permissão do usuário a partir de suas associações
correntes, sem exigir novo login.

#### Scenario: Usuário adicionado a grupo com concessão

- **GIVEN** um usuário autenticado sem permissão sobre uma imagem
- **WHEN** o administrador o inclui em um grupo que tem concessão sobre ela
- **THEN** a imagem passa a aparecer no catálogo desse usuário na consulta seguinte

### Requirement: Concessão duplicada é idempotente

O sistema DEVE tratar a concessão de uma imagem a um grupo que já a possui como
operação sem efeito, em vez de erro ou duplicação.

#### Scenario: Concessão repetida

- **GIVEN** um grupo que já tem concessão sobre uma imagem
- **WHEN** o administrador concede a mesma imagem ao mesmo grupo
- **THEN** a operação é aceita
- **AND** continua existindo uma única concessão

### Requirement: Criação de instância exige permissão vigente

O sistema DEVE verificar a permissão do usuário sobre a imagem no momento da
criação da instância e DEVE recusar a operação quando ela não existir.

#### Scenario: Criação sem permissão

- **WHEN** um usuário tenta criar instância de imagem que seus grupos não permitem
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** nenhum container é criado

### Requirement: Revogação para as instâncias afetadas imediatamente

Ao revogar a concessão de uma imagem a um grupo, o sistema DEVE parar as
instâncias em execução daquela imagem pertencentes a usuários que perderam a
permissão, preservando seus volumes.

#### Scenario: Revogação com instância em execução

- **GIVEN** um usuário com instância em execução de uma imagem concedida ao seu grupo
- **WHEN** o administrador revoga aquela concessão e o usuário perde a permissão
- **THEN** a instância é parada
- **AND** o volume do usuário é preservado

#### Scenario: Permissão remanescente por outro grupo

- **GIVEN** um usuário que recebe a mesma imagem por dois grupos distintos
- **WHEN** o administrador revoga a concessão de apenas um deles
- **THEN** o usuário mantém a permissão
- **AND** sua instância em execução não é parada

### Requirement: Acesso à instância é negado após perda de permissão

Após a revogação, o sistema DEVE recusar o acesso do usuário à instância daquela
imagem, mesmo que o container ainda esteja em processo de parada.

#### Scenario: Acesso imediatamente após a revogação

- **GIVEN** um usuário que acabou de perder a permissão sobre uma imagem
- **WHEN** esse usuário requisita o endereço da sua instância daquela imagem
- **THEN** o sistema recusa o acesso

### Requirement: Impacto da revogação é informado antes da confirmação

O sistema DEVE informar ao administrador quantas instâncias em execução serão
paradas por uma revogação, antes de efetivá-la.

#### Scenario: Pré-visualização do impacto

- **WHEN** um administrador solicita a revogação de uma concessão
- **THEN** o sistema informa o número de instâncias em execução que serão paradas
- **AND** a revogação só é aplicada após confirmação explícita
