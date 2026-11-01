# Spec Delta

## MODIFIED Requirements

### Requirement: Entrada pode ser desabilitada sem remoção

O sistema DEVE permitir desabilitar uma entrada do catálogo, retirando-a da
oferta a novos usuários e preservando seu registro. A desabilitação DEVE exigir
confirmação explícita que descreva o efeito de retirar a imagem da oferta.

#### Scenario: Imagem desabilitada

- **WHEN** um administrador desabilita uma entrada do catálogo
- **THEN** a entrada deixa de aparecer no catálogo dos usuários
- **AND** novas instâncias a partir dela são recusadas

#### Scenario: Desabilitação sem confirmação

- **WHEN** a desabilitação de uma entrada é pedida sem confirmação explícita
- **THEN** o sistema não altera a entrada
