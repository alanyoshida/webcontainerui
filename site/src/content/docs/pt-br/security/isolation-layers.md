---
title: Camadas de isolamento
description: As camadas que separam a sessão de um usuário da de outro, o que cada uma garante e o que nenhuma delas garante.
sidebar:
  order: 2
---

O isolamento entre usuários não depende de uma única checagem. Uma requisição a `/i/{uuid}/` só chega ao container depois de passar por quatro camadas independentes, e os segredos que o portal guarda ficam cifrados em repouso. Esta página descreve cada camada, o que ela garante e — com a mesma ênfase — o que ela não garante.

Nenhuma destas camadas limita o que o próprio portal pode fazer no host. Esse é outro assunto, tratado em [Superfície de confiança](/security/trust-surface/).

## Visão geral

| Camada | Onde é aplicada | O que barra |
|---|---|---|
| 1. Sessão autenticada | Portal, em toda rota não pública | Requisição anônima |
| 2. Verificação de dono | Proxy de sessão e autorização do plano de dados | Usuário autenticado acessando instância alheia |
| 3. Credencial aleatória por instância | Dentro do container | Quem alcança o container sem passar pelo portal |
| 4. Isolamento topológico | Rede Docker interna, sem porta publicada | Acesso ao container a partir de fora do host |

As camadas 1 e 2 são decisão do portal. A camada 3 é aplicada pelo próprio container. A camada 4 é propriedade da topologia de rede, não de código.

## Camada 1 — sessão autenticada

Toda rota que não é explicitamente pública exige um cookie de sessão válido: a API, o painel administrativo e o caminho das instâncias. Sem sessão, a resposta é "não autenticado" e não revela se o recurso existe.

A sessão é um token aleatório de 256 bits, guardado no banco apenas como hash, com expiração (12 horas por padrão) e revogação imediata no logout. Desabilitar uma conta revoga as sessões existentes dela. Os detalhes de cookie, limitador e hash de senha estão em [Endurecimento do login](/security/login-hardening/).

**Garante:** que toda ação é atribuída a um usuário conhecido e ativo.

**Não garante:** que quem apresenta o cookie é a pessoa certa. Não há segundo fator. Um cookie roubado vale até expirar ou ser revogado. Além disso, o conteúdo servido de dentro do container do usuário roda na mesma origem do portal e pode usar a sessão dele — é um risco aceito, descrito em [Auditorias](/security/audits/).

Especificação: [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md).

## Camada 2 — verificação de dono

Ter sessão válida não basta para alcançar uma instância: o portal confere que o usuário autenticado é o dono dela. A checagem acontece a cada requisição HTTP e também na abertura do canal persistente (WebSocket) que carrega a sessão interativa.

- Instância inexistente e instância de outro dono produzem a mesma resposta (`404`), de modo que não é possível enumerar identificadores alheios.
- Instância do dono que não está em execução responde `409`, sem tentar alcançar o container.
- Quando o administrador revoga a concessão de uma imagem a um grupo, as instâncias afetadas são paradas na hora e o acesso a elas passa a ser recusado.
- A criação de instância exige permissão vigente sobre a imagem; a permissão de um usuário é a união das permissões dos grupos a que pertence.

**Garante:** que um usuário autenticado não entra na instância de outro pelo portal, mesmo conhecendo o identificador.

**Não garante:** nada sobre quem alcança o container sem passar pelo portal — é para isso que existem as camadas 3 e 4. E não protege contra um administrador: administradores controlam usuários, grupos, catálogo e os documentos e servidores MCP que o portal propaga para as instâncias.

Especificações: [session-proxy](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md) e [access-control](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/access-control/spec.md).

## Camada 3 — credencial aleatória por instância

Cada instância nasce com um par usuário/senha próprio, gerado pelo portal com `secrets.token_urlsafe` (8 bytes de usuário, 16 bytes de senha) e entregue ao container na criação. O serviço dentro do container — a interface do webtop ou o terminal do agente — exige essa credencial em toda requisição.

- O portal (ou, em produção, o plano de dados) injeta a credencial na requisição encaminhada. O usuário nunca a digita e nunca a recebe.
- Qualquer cabeçalho `Authorization` enviado pelo cliente é descartado antes do encaminhamento e substituído pela credencial da instância.
- A credencial não aparece em respostas de erro nem em cabeçalhos refletidos.

**Garante:** que alcançar a porta do container não é suficiente para entrar na sessão. No teste de intrusão, um container "atacante" na mesma rede recebeu `401` ao tentar o container da "vítima".

**Não garante:** proteção para qualquer outro serviço que escute dentro do container. A credencial protege só o processo de interface que a exige. Um servidor de desenvolvimento, uma API de depuração ou qualquer coisa que o usuário ou uma imagem de agente suba em outra porta fica alcançável pelos containers dos outros usuários (ver camada 4). Também não protege contra quem lê o banco do portal, onde a credencial fica em claro.

## Camada 4 — isolamento topológico

Os containers de instância **nunca publicam porta no host**. Eles existem apenas na rede Docker interna (`wcui_net` em produção), e o único caminho de fora para dentro é a borda (Caddy) — que só encaminha o que o portal aprovou. O portal também não publica porta em produção; só o Caddy expõe 80 e 443.

**Garante:** que nenhum container de usuário é alcançável da internet ou da rede do host diretamente, e que redes Docker distintas ficam isoladas entre si.

**Não garante isolamento entre usuários dentro da rede interna.** Este é o limite mais importante desta página:

:::caution[Todas as instâncias compartilham a mesma rede]
O portal cria todos os containers de instância na mesma rede Docker. Não existe rede por usuário nem por instância. De dentro do próprio container, um usuário (que tem root ali) consegue varrer portas e alcançar os containers de todos os outros usuários, o portal na porta 8000, o Caddy e o PostgreSQL. O que o detém é a camada 3 nos containers alheios, a camada 1 no portal e a senha do banco. Este ponto foi registrado no teste de intrusão como achado B4 e permanece em aberto — ver [Auditorias](/security/audits/).
:::

Consequência prática para quem mantém imagens: **todo listener dentro de um container de instância precisa exigir a credencial interna ou escutar apenas em `localhost`**. Isso ainda não é um contrato formal das imagens de agente; é uma recomendação. Ver [Imagens de agente](/architecture/agent-images/).

O isolamento topológico também não restringe a saída: um container alcança o que o host alcança, incluindo a internet e, dependendo do seu ambiente, outras máquinas da rede do host.

## Plano de dados das sessões

Em produção o Caddy transporta `/i/{uuid}/` diretamente aos containers das instâncias; o portal deixa de reenviar os frames e passa a decidir apenas a autorização. O desenho completo está em [Plano de dados das sessões](/architecture/session-data-plane/). Do ponto de vista de segurança, isso muda a superfície de três formas:

- **O Caddy alcança os containers das instâncias.** Ele já vivia na `wcui_net`; agora o `reverse_proxy` usa esse acesso. Os containers continuam sem porta publicada no host — o isolamento em relação ao exterior segue topológico.
- **Segredo compartilhado.** O `forward_auth` apresenta `WCUI_DATA_PLANE_SECRET` ao endpoint interno de autorização (`/internal/data-plane/authorize`). Sem o segredo correto, o endpoint responde `401` e nada é encaminhado — falha fechada, inclusive com o portal fora do ar. A comparação é em tempo constante, e segredo vazio desativa o endpoint em vez de liberá-lo. O endpoint não é exposto pela borda: o Caddy responde `404` a `/internal/*` vindo de fora, e ele não aparece no schema público da API.
- **Rotas são configuração, não código.** O portal escreve um snippet por instância no volume `caddy_routes`, com id e nome de container validados (apenas `[A-Za-z0-9_.-]`); o comando de reload é fixo no portal, nunca derivado de input de usuário.

O portal continua sendo o único componente que decide autorização; o Caddy só transporta o que o portal aprovou. Com o plano de dados ativo, as camadas 1 e 2 são avaliadas no endpoint interno a cada requisição e a cada abertura de canal, e a credencial da camada 3 viaja do portal para o Caddy na resposta da autorização e do Caddy para o container — nunca para o cliente.

O que isso **não** muda:

- O endpoint interno é alcançável de dentro da rede interna, portanto também pelos containers de instância. O que impede um container de consultá-lo é o segredo. Quem obtiver `WCUI_DATA_PLANE_SECRET` e estiver na rede interna ainda precisaria de um cookie de sessão válido do dono para receber a credencial de uma instância — o segredo sozinho não autoriza nada.
- O proxy de sessão dentro do portal continua registrado. Em produção ele fica sombreado pelo roteamento da borda; é o caminho de desenvolvimento e de testes e uma defesa em profundidade, com as mesmas verificações.

Especificação: [stream-data-plane](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/stream-data-plane/spec.md).

## Identidade SSH cifrada em repouso

Cada usuário tem um par de chaves SSH próprio, gerado pelo portal, para que `git` e `ssh` funcionem dentro das instâncias sem configuração manual.

- A chave privada é armazenada cifrada com Fernet, usando `WCUI_SSH_KEY_ENCRYPTION_KEY`. O portal recusa subir sem uma chave Fernet válida — não há modo "sem cifragem".
- O portal **só gera** chaves. Ele nunca recebe nem armazena uma chave privada pré-existente; a importação é recusada.
- A API devolve apenas a chave pública. Consultar e regenerar a identidade é restrito ao próprio dono.
- Regenerar substitui a identidade em todas as instâncias vivas do usuário, em execução ou paradas.

**Garante:** que um vazamento do banco, sozinho, não entrega chaves privadas.

**Não garante:**

- Proteção contra quem tem o banco **e** a chave Fernet. As duas juntas equivalem a todas as chaves privadas.
- Proteção dentro do container. A chave privada é injetada em claro em `/config/.ssh/` (modo `600`) para que `git` a use. Qualquer processo rodando na instância — incluindo um agente de IA e os pacotes que ele instalar — consegue lê-la. Trate a chave pública cadastrada no GitHub, GitLab ou Bitbucket como uma credencial que os agentes daquela pessoa podem usar.
- Rotação automática. A troca acontece quando o usuário aciona a regeneração; a chave pública antiga precisa ser removida manualmente dos serviços remotos.

Especificação: [ssh-identity](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/ssh-identity/spec.md).

## Segredos de MCP cifrados

Os servidores MCP cadastrados pelo administrador podem carregar variáveis de ambiente e cabeçalhos com segredos (tokens de API, por exemplo). Esses valores são cifrados no banco com a mesma infraestrutura Fernet da identidade SSH, e a API devolve só os nomes das chaves, nunca os valores.

**Garante:** que os valores não ficam em claro no banco nem voltam pela API administrativa.

**Não garante:** sigilo em relação aos usuários das imagens vinculadas. Para o agente usar o servidor MCP, a configuração — com os valores — é escrita dentro do container da instância. Um segredo de MCP vinculado a uma imagem deve ser considerado conhecido por todo usuário que tem acesso a essa imagem. Use credenciais de escopo mínimo, pensadas para serem compartilhadas com esse grupo.

:::note
A identidade SSH e os segredos de MCP usam a mesma chave (`WCUI_SSH_KEY_ENCRYPTION_KEY`). Perder a chave torna ambos irrecuperáveis; vazá-la junto com o banco expõe ambos. Ver [Variáveis de ambiente](/operations/environment-variables/) e [Backup e restauração](/operations/backup-and-restore/).
:::

## Resumo do que nenhuma camada cobre

- A autoridade do portal sobre o host ([Superfície de confiança](/security/trust-surface/)).
- O alcance de rede entre containers de usuários distintos (achado B4, aberto).
- O fato de o conteúdo do container rodar na origem do portal (achado M3, aceito).
- Um administrador mal-intencionado ou comprometido.
- Escape de container por falha no kernel ou no runtime do Docker.

O status de cada item levantado em auditoria está em [Auditorias](/security/audits/).
