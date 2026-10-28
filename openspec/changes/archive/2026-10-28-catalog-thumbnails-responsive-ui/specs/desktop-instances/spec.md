# Spec Delta

## ADDED Requirements

### Requirement: Listagem de instâncias adapta o layout ao tamanho da tela

A listagem de instâncias do usuário DEVE apresentar seus cartões em layout que
adapta o número de colunas à largura da tela do dispositivo, em vez de
empilhamento vertical fixo.

#### Scenario: Tela estreita

- **WHEN** um usuário consulta sua listagem de instâncias em uma tela estreita
- **THEN** os cartões de instância são exibidos em uma única coluna

#### Scenario: Tela larga

- **WHEN** um usuário consulta sua listagem de instâncias em uma tela larga
- **THEN** os cartões de instância são exibidos em múltiplas colunas lado a lado

### Requirement: Sessão embutida permanece utilizável em qualquer largura de coluna

Quando o usuário abre a sessão embutida de uma instância, o layout responsivo da
listagem DEVE manter essa sessão com área útil suficiente para interação,
independentemente do número de colunas vigente.

#### Scenario: Sessão aberta em listagem de múltiplas colunas

- **GIVEN** uma listagem exibida em múltiplas colunas
- **WHEN** o usuário abre a sessão embutida de uma das instâncias
- **THEN** a sessão é exibida com área útil suficiente para interação
