# Spec Delta

## ADDED Requirements

### Requirement: Sessão preenche a área disponível na visão dedicada

Na visão dedicada, o conteúdo embutido da sessão DEVE ocupar a área disponível
da página. O portal DEVE negociar o dimensionamento do conteúdo por parâmetro
na URL do conteúdo embutido e, quando o conteúdo não aceitar o parâmetro, DEVE
exibi-lo centralizado sobre fundo coerente com o tema ativo, sem faixas mortas
laterais que pareçam defeito.

#### Scenario: Conteúdo aceita negociação de dimensionamento

- **GIVEN** uma sessão cujo conteúdo aceita o parâmetro de dimensionamento
- **WHEN** a visão dedicada é aberta ou a janela é redimensionada
- **THEN** o conteúdo acompanha a área disponível sem faixas mortas laterais

#### Scenario: Conteúdo não aceita negociação

- **GIVEN** uma sessão cujo conteúdo ignora o parâmetro de dimensionamento
- **WHEN** a visão dedicada é aberta
- **THEN** o conteúdo é exibido centralizado sobre fundo coerente com o tema
  ativo
