# Spec Delta

## Purpose

Define o site público do projeto: o que ele apresenta a quem ainda não conhece
o produto, como organiza a documentação de arquitetura, segurança e operação,
em quais idiomas, e quais garantias de integridade a publicação oferece.

## ADDED Requirements

### Requirement: Site público apresenta o produto numa landing

O site DEVE ter uma página inicial que apresente o produto como portal de
desktops Linux e de agentes de código em CLI no navegador, com capturas de
tela da interface, o resumo do modelo de segurança e o caminho de instalação.

#### Scenario: Visitante abre o endereço do site

- **WHEN** um visitante abre a raiz do site
- **THEN** vê a apresentação do produto citando desktops Linux e agentes de código
- **AND** vê ao menos uma captura de tela da interface do portal
- **AND** encontra um caminho visível para a instalação e para a documentação

#### Scenario: Visitante chega ao repositório a partir da landing

- **WHEN** o visitante procura o código-fonte na landing
- **THEN** encontra um link para o repositório no GitHub

### Requirement: Landing declara que o portal equivale a root no host

A landing DEVE exibir, em seção própria e sem exigir navegação até a
documentação, o aviso de que o processo do portal tem autoridade equivalente a
root no host e de que o usuário tem root dentro do próprio desktop.

#### Scenario: Aviso visível sem sair da landing

- **WHEN** um visitante percorre a landing até o fim
- **THEN** passa por uma seção que declara a equivalência a root no host
- **AND** essa seção leva à página de documentação que detalha a superfície de confiança

### Requirement: Documentação é navegável e pesquisável

O site DEVE oferecer a documentação organizada nas seções Começar,
Arquitetura, Segurança, Operação e Referência, com navegação lateral entre as
páginas e busca por texto que funcione sem serviço externo.

#### Scenario: Navegação entre seções

- **WHEN** o visitante abre qualquer página de documentação
- **THEN** vê a navegação com as cinco seções e as páginas de cada uma

#### Scenario: Busca encontra um termo da documentação

- **WHEN** o visitante busca um termo presente no texto de uma página, como `forward_auth`
- **THEN** a busca lista a página que contém o termo

#### Scenario: Referência aponta para as specs

- **WHEN** o visitante abre a seção Referência
- **THEN** encontra a lista das capabilities do projeto, cada uma com link para sua spec no repositório

### Requirement: Site é publicado em inglês e em português

O site DEVE estar disponível em inglês, servido na raiz, e em português do
Brasil, servido sob `/pt-br/`. Landing e documentação DEVEM existir nos dois
idiomas, e o visitante DEVE poder alternar de idioma permanecendo na página
equivalente.

#### Scenario: Raiz em inglês

- **WHEN** um visitante abre a raiz do site
- **THEN** o conteúdo é exibido em inglês

#### Scenario: Versão em português

- **WHEN** um visitante abre o site sob `/pt-br/`
- **THEN** landing e documentação são exibidas em português

#### Scenario: Troca de idioma preserva a página

- **GIVEN** um visitante lendo uma página de documentação em inglês
- **WHEN** ele escolhe português no seletor de idioma
- **THEN** é levado à mesma página em português, não à página inicial

### Requirement: Tradução defasada impede a publicação

O português é a língua de origem do conteúdo. A verificação do site DEVE
falhar quando uma página em português não tiver correspondente em inglês ou
quando o texto de origem tiver mudado depois da última tradução registrada.

#### Scenario: Página sem tradução

- **WHEN** existe uma página em português sem a página inglesa correspondente
- **THEN** a verificação falha e nomeia a página faltante

#### Scenario: Origem alterada depois da tradução

- **GIVEN** uma página traduzida e registrada como em dia
- **WHEN** o texto em português dessa página é alterado sem que a tradução seja reconfirmada
- **THEN** a verificação falha e nomeia a página defasada

#### Scenario: Conteúdo em paridade

- **WHEN** toda página em português tem tradução registrada contra o texto atual
- **THEN** a verificação passa

### Requirement: Links internos quebrados impedem a publicação

A construção do site DEVE falhar quando uma página apontar para outra página
ou âncora do próprio site que não existe.

#### Scenario: Link para página inexistente

- **WHEN** uma página contém um link interno para um caminho que não existe no site
- **THEN** a construção falha e indica a página e o link

### Requirement: Site segue a identidade visual do portal

O site DEVE usar a identidade do portal: tema escuro em carvão com primário
rosa como padrão, alternativa clara, as famílias tipográficas do portal e a
logo do produto. Fontes e demais recursos de apresentação DEVEM ser servidos
pelo próprio site, sem requisição a terceiros.

#### Scenario: Primeira visita

- **WHEN** um visitante sem preferência registrada abre o site
- **THEN** o site é exibido no tema escuro com a logo do produto

#### Scenario: Alternância para o tema claro

- **WHEN** o visitante escolhe o tema claro
- **THEN** landing e documentação passam a ser exibidas no tema claro

#### Scenario: Nenhuma fonte externa

- **WHEN** uma página do site é carregada
- **THEN** nenhuma fonte tipográfica é requisitada a um domínio diferente do domínio do site

### Requirement: Página de auditoria declara o status de cada achado

A seção Segurança DEVE ter uma página que liste cada achado dos relatórios de
segurança publicados no repositório com severidade, status atual (corrigido,
aceito ou aberto) e onde foi tratado, identificando a data e o commit de cada
relatório e apontando para o relatório completo.

#### Scenario: Achado corrigido

- **WHEN** o visitante consulta um achado já corrigido
- **THEN** vê o status "corrigido" e a indicação de onde a correção está especificada ou implementada

#### Scenario: Achado não corrigido

- **WHEN** o visitante consulta um achado que permanece sem correção
- **THEN** vê o status "aberto" ou "aceito", nunca "corrigido"

#### Scenario: Acesso ao relatório completo

- **WHEN** o visitante quer o texto integral de um relatório
- **THEN** encontra na página o link para o relatório no repositório

### Requirement: Publicação automática a partir da branch principal

O site DEVE ser reconstruído e publicado automaticamente quando uma mudança no
seu conteúdo chegar à branch principal, e só quando as verificações de
tradução e de links passarem.

#### Scenario: Mudança de conteúdo chega à branch principal

- **WHEN** um commit que altera o site é integrado à branch principal e as verificações passam
- **THEN** a versão publicada do site passa a refletir esse commit sem ação manual

#### Scenario: Verificação falha na branch principal

- **WHEN** um commit integrado à branch principal falha na verificação de tradução ou de links
- **THEN** nada é publicado e a versão anterior do site permanece no ar

#### Scenario: Pull request é validado sem publicar

- **WHEN** um pull request altera o conteúdo do site
- **THEN** as verificações e a construção rodam e seu resultado fica visível no pull request
- **AND** o site publicado não é alterado

### Requirement: Documentos do repositório apontam para o site

Os textos longos de arquitetura, segurança e operação DEVEM existir num único
lugar, o site. Os documentos do repositório que antes os continham DEVEM
manter um resumo e apontar para a página correspondente, nos dois idiomas.

#### Scenario: Leitor do README procura a documentação

- **WHEN** alguém lê o `README.md` do repositório
- **THEN** encontra os links para o site em inglês e em português

#### Scenario: Leitor da pasta de implantação

- **WHEN** alguém abre `deploy/README.md` ou `deploy/SECURITY.md`
- **THEN** encontra um resumo e o link para a seção correspondente do site
- **AND** não encontra uma segunda cópia do texto completo
