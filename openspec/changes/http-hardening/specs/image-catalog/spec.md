# Spec Delta

## ADDED Requirements

### Requirement: Capa carrega somente de origem própria

A interface DEVE exibir a capa de uma entrada do catálogo apenas quando a URL informada aponta para o armazenamento próprio do portal (`/uploads/`); qualquer outra origem cai no mesmo estado visual de capa ausente, sem carregar conteúdo externo.

#### Scenario: Capa válida

- **WHEN** a entrada do catálogo informa `icon_url` iniciada por `/uploads/`
- **THEN** a interface carrega e exibe a capa

#### Scenario: URL externa é recusada

- **WHEN** a entrada do catálogo informa `icon_url` de origem externa ao portal
- **THEN** a interface não requisita essa URL
- **AND** exibe o mesmo tratamento visual de entrada sem capa
