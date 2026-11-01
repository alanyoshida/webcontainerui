# Spec Delta — image-catalog

## ADDED Requirements

### Requirement: Admin atualiza a imagem de uma entrada pronta

O sistema DEVE permitir que um administrador dispare o novo download da
referência de imagem de uma entrada do catálogo já pronta (`ready`), para
acompanhar versões publicadas pela origem (tags móveis). Durante o download a
entrada DEVE voltar ao estado em andamento e ao concluir DEVE retornar a
pronta; em falha DEVE seguir o fluxo de retry existente. Entradas de build
seguem o fluxo de rebuild já definido, sem mudança.

#### Scenario: Atualização concluída

- **WHEN** um administrador dispara a atualização de uma entrada pronta e o
  download conclui com sucesso
- **THEN** a entrada registra a versão da imagem recém-baixada
- **AND** a entrada volta ao estado pronta

#### Scenario: Instanciação bloqueada durante a atualização

- **WHEN** a entrada está com download em andamento por atualização
- **THEN** criar instância a partir dela é recusado

#### Scenario: Falha de download durante a atualização

- **WHEN** o download da atualização falha
- **THEN** a entrada fica em falha com a mensagem do erro
- **AND** o fluxo de nova tentativa existente volta a valer para ela

#### Scenario: Re-pull de conteúdo idêntico

- **WHEN** o download conclui e a origem não mudou o conteúdo da referência
- **THEN** a entrada permanece pronta, sem efeito sobre as instâncias
  existentes

#### Scenario: Usuário comum tenta atualizar

- **WHEN** um usuário sem papel de administrador tenta atualizar a imagem de
  uma entrada
- **THEN** o sistema recusa a operação por falta de permissão

### Requirement: Catálogo registra a versão da imagem baixada

Ao concluir um download, o sistema DEVE registrar na entrada do catálogo uma
identificação legível da versão da imagem baixada: o rótulo de versão da
imagem quando disponível (por exemplo, o rótulo de build das imagens
LinuxServer) e, na ausência dele, o identificador curto do conteúdo baixado.
A versão registrada DEVE ser exposta na API e na interface do catálogo. O
download de uma nova versão DEVE substituir a versão registrada.

#### Scenario: Versão capturada no download

- **WHEN** um download conclui com sucesso
- **THEN** a entrada registra a versão legível da imagem baixada

#### Scenario: Imagem sem rótulo de versão

- **WHEN** o download conclui e a imagem não publica rótulo de versão
- **THEN** a entrada registra o identificador curto do conteúdo baixado
