# Spec Delta

## ADDED Requirements

### Requirement: Entradas de desktop padrão são garantidas no startup

O sistema DEVE garantir, a cada inicialização, que as entradas de desktop
padrão do produto existam no catálogo, registrando as ausentes com
provisionamento por download iniciado em segundo plano. Uma entrada que já
exista no catálogo DEVE ser mantida como está: o seed NÃO DEVE duplicá-la,
reativá-la, sobrescrever seus limites nem sua capa. Falha no download de uma
entrada NÃO DEVE impedir o startup do portal nem o provisionamento das
demais.

#### Scenario: Banco vazio no primeiro startup

- **WHEN** o portal inicia com um catálogo vazio
- **THEN** as entradas de desktop padrão são registradas com download iniciado
- **AND** cada uma fica observável como em provisionamento, sem bloquear o startup

#### Scenario: Entrada já configurada pelo administrador

- **GIVEN** uma das entradas padrão já existe no catálogo, desabilitada ou com limites editados
- **WHEN** o portal inicia
- **THEN** a entrada permanece exatamente como estava, sem nova linha nem download disparado

#### Scenario: Falha de download isolada

- **WHEN** o download de uma das entradas padrão falha
- **THEN** o estado de falha fica observável na entrada e as demais seguem
- **AND** o portal sobe normalmente, com a entrada recuperável por nova tentativa
