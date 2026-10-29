# Spec Delta

## MODIFIED Requirements

### Requirement: Estado real do container reconcilia com o registrado

O sistema DEVE corrigir o estado registrado de uma instância quando ele divergir
do estado real do container, de modo que um container encerrado por fora não
apareça como em execução. Essa correção DEVE acontecer periodicamente durante
a operação normal do portal, não apenas na inicialização do processo, para que
um container encerrado por fora enquanto o portal está no ar seja detectado
sem exigir um reinício.

#### Scenario: Container encerrado externamente

- **GIVEN** uma instância registrada como em execução cujo container foi encerrado por fora
- **WHEN** o sistema reconcilia os estados
- **THEN** a instância passa a constar como parada

#### Scenario: Container encerrado externamente durante a operação normal do portal

- **GIVEN** o portal em execução há mais tempo que um ciclo de reconciliação,
  com uma instância registrada como em execução
- **WHEN** o container dessa instância é encerrado por fora enquanto o portal
  continua no ar, sem reinício
- **THEN** a instância passa a constar como parada no ciclo de reconciliação
  seguinte, sem exigir um reinício do portal
