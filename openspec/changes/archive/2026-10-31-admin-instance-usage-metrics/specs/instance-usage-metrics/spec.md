# Spec Delta

## Purpose

Registra o histórico de execução de cada instância (quando começou, quando
terminou e por quê) e oferece ao administrador visibilidade — ao vivo e
histórica — sobre quem usa quais instâncias e por quanto tempo.

## ADDED Requirements

### Requirement: Execução de instância é registrada com início e fim

O sistema DEVE registrar cada ciclo de execução (início até parada) de uma
instância, incluindo o usuário dono, a imagem, o instante de início e o
instante de fim, que permanece ausente enquanto a instância está em execução.

#### Scenario: Início de execução registrado

- **WHEN** uma instância entra em execução
- **THEN** um registro de execução é aberto com usuário, imagem e instante de
  início
- **AND** esse registro não possui instante de fim enquanto a instância
  continuar em execução

#### Scenario: Fim de execução registrado

- **WHEN** uma instância em execução para, por qualquer motivo
- **THEN** o registro de execução aberto correspondente recebe o instante de
  fim

### Requirement: Motivo do término de uma execução é registrado

O sistema DEVE registrar o motivo pelo qual cada execução terminou, distinguindo
ao menos parada pelo usuário, parada por ociosidade, parada por reconciliação
após queda externa do container, e exclusão da instância.

#### Scenario: Parada pelo usuário

- **WHEN** um usuário para sua instância em execução
- **THEN** o registro de execução é fechado com o motivo "parada pelo usuário"

#### Scenario: Parada por ociosidade

- **WHEN** o sistema para uma instância por inatividade além do limite
  configurado
- **THEN** o registro de execução é fechado com o motivo "ociosidade"

#### Scenario: Parada por reconciliação

- **WHEN** o sistema reconcilia o estado de uma instância cujo container foi
  encerrado por fora
- **THEN** o registro de execução é fechado com o motivo "queda externa"

#### Scenario: Encerrado por exclusão

- **WHEN** uma instância em execução é excluída
- **THEN** o registro de execução é fechado com o motivo "exclusão"

### Requirement: Histórico de execuções não é apagado automaticamente

O sistema NÃO DEVE remover registros de execução automaticamente; o histórico
cresce indefinidamente até que um administrador o remova por outro meio.

#### Scenario: Execução antiga permanece disponível

- **GIVEN** um registro de execução de meses atrás
- **WHEN** o sistema opera normalmente, sem intervenção manual
- **THEN** esse registro continua presente e consultável

### Requirement: Administrador visualiza instâncias em execução agora

O sistema DEVE oferecer ao administrador uma visão das instâncias atualmente
em execução, mostrando o usuário dono, a imagem e a duração da execução em
curso.

#### Scenario: Consulta com instâncias em execução

- **GIVEN** instâncias em execução pertencentes a usuários diferentes
- **WHEN** um administrador consulta as instâncias em execução agora
- **THEN** cada uma aparece com seu usuário, imagem e duração desde o início

### Requirement: Administrador visualiza histórico de execuções

O sistema DEVE oferecer ao administrador uma listagem das execuções passadas e
em curso, cada uma com usuário, imagem, início, fim, duração e motivo do
término, restrita por padrão aos últimos 30 dias.

#### Scenario: Listagem padrão de 30 dias

- **GIVEN** execuções registradas dentro e fora dos últimos 30 dias
- **WHEN** um administrador consulta o histórico de execuções sem especificar
  período
- **THEN** apenas as execuções dos últimos 30 dias são apresentadas

### Requirement: Administrador visualiza total de horas por usuário

O sistema DEVE apresentar ao administrador o total de horas de execução
agregado por usuário no período consultado.

#### Scenario: Agregado por usuário no período

- **GIVEN** execuções de múltiplos usuários no período consultado
- **WHEN** um administrador consulta o agregado por usuário
- **THEN** cada usuário aparece com a soma das durações de suas execuções no
  período

### Requirement: Administrador visualiza total de horas por grupo

O sistema DEVE apresentar ao administrador o total de horas de execução
agregado por grupo de usuários no período consultado.

#### Scenario: Agregado por grupo no período

- **GIVEN** execuções de usuários pertencentes a grupos diferentes no período
  consultado
- **WHEN** um administrador consulta o agregado por grupo
- **THEN** cada grupo aparece com a soma das durações das execuções de seus
  membros no período

### Requirement: Administrador visualiza ranking de imagens mais usadas

O sistema DEVE apresentar ao administrador um ranking das imagens do catálogo
por uso no período consultado, incluindo número de execuções e horas totais.

#### Scenario: Ranking no período

- **GIVEN** execuções de imagens diferentes no período consultado
- **WHEN** um administrador consulta o ranking de imagens
- **THEN** as imagens aparecem ordenadas por uso, com número de execuções e
  horas totais de cada uma

### Requirement: Administrador visualiza distribuição por motivo de término

O sistema DEVE apresentar ao administrador a distribuição das execuções
encerradas no período consultado por motivo de término.

#### Scenario: Distribuição no período

- **GIVEN** execuções encerradas por motivos diferentes no período consultado
- **WHEN** um administrador consulta a distribuição por motivo de término
- **THEN** o total de execuções de cada motivo no período é apresentado

### Requirement: Administrador visualiza uso diário ao longo do período

O sistema DEVE apresentar ao administrador a quantidade de instâncias ativas
por dia ao longo do período consultado.

#### Scenario: Série diária no período

- **GIVEN** execuções distribuídas em dias diferentes dentro do período
  consultado
- **WHEN** um administrador consulta o uso diário
- **THEN** a quantidade de instâncias ativas de cada dia do período é
  apresentada

### Requirement: Administrador visualiza pico de instâncias simultâneas

O sistema DEVE apresentar ao administrador o maior número de instâncias em
execução ao mesmo tempo observado no período consultado.

#### Scenario: Pico no período

- **GIVEN** execuções sobrepostas no tempo dentro do período consultado
- **WHEN** um administrador consulta o pico de simultaneidade
- **THEN** o maior número de instâncias simultâneas observado no período é
  apresentado

### Requirement: Métricas de uso são restritas a administradores

O sistema DEVE recusar acesso a qualquer métrica de uso de instâncias para
usuários que não sejam administradores.

#### Scenario: Usuário comum tenta acessar métricas

- **WHEN** um usuário sem privilégio de administrador tenta consultar
  métricas de uso
- **THEN** o sistema recusa o acesso

#### Scenario: Administrador acessa métricas

- **WHEN** um usuário administrador consulta métricas de uso
- **THEN** o sistema retorna os dados solicitados
