---
title: Auditorias
description: Status atual de cada achado dos relatórios de segurança do projeto — corrigido, aceito ou aberto — com a indicação de onde foi tratado.
sidebar:
  order: 5
---

Esta página lista cada achado dos relatórios de segurança publicados no repositório e diz, um a um, em que estado ele está no código atual. Os achados que continuam sem correção aparecem como "aberto" de propósito: a página existe para que você decida com informação completa, não para parecer limpa. Um achado só é marcado "corrigido" quando há evidência concreta no código — arquivo, especificação ou teste — de que o problema descrito não existe mais.

## Como ler os status

| Status | Significado |
|---|---|
| **corrigido** | O problema descrito não existe mais no código atual, e a correção está apontada na coluna "Onde foi tratado" |
| **aceito** | O risco é reconhecido e mantido por decisão de projeto documentada; a coluna aponta onde a decisão está registrada |
| **aberto** | Sem correção, ou sem evidência suficiente de correção |

:::note[Alcance desta verificação]
Os status foram conferidos por leitura do código, das especificações e dos testes automatizados existentes. Os testes dinâmicos dos relatórios (medição de tempo de resposta, inspeção de cabeçalhos atrás do Caddy, varredura de imagem) **não foram reexecutados** para esta página. Onde a correção depende de configuração de implantação, isso está dito na linha do achado.
:::

## Teste de intrusão — 1 de novembro de 2026

- **Data:** 1 de novembro de 2026
- **Commit avaliado:** `22f2d69`
- **Tipo:** teste de intrusão caixa-branca (código-fonte disponível), com testes dinâmicos contra uma instância local de desenvolvimento
- **Resultado:** nenhum achado crítico ou alto; 3 médios, 5 baixos, 5 informativos
- **Relatório completo:** [docs/relatorio-pentest-2026-11-01.md](https://github.com/alanyoshida/webcontainerui/blob/main/docs/relatorio-pentest-2026-11-01.md) (em português)

| Achado | Severidade | Resumo | Status | Onde foi tratado |
|---|---|---|---|---|
| M1 | Médio | Cookie de sessão sem `Secure` em produção, porque o portal não honrava os cabeçalhos encaminhados pelo Caddy | **corrigido** | Especificação [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (cookie protegido no transporte). `deploy/docker-compose.yml` define `UVICORN_PROXY_HEADERS` e `UVICORN_FORWARDED_ALLOW_IPS` com a subnet fixa da `wcui_net`; `deploy/Caddyfile` envia HSTS. Depende da configuração de implantação — ver observação abaixo |
| M2 | Médio | Login sem limitação de tentativas nem bloqueio temporário | **corrigido** | Especificação [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (tentativas com falha são limitadas). `backend/app/services/login_throttle.py`, consultado em `backend/app/api/auth.py` antes do banco e do Argon2; testes em `backend/tests/test_login_throttle.py` e `backend/tests/test_auth.py` |
| M3 | Médio | Conteúdo do container do usuário executa na mesma origem do portal e pode usar a sessão dele | **aceito** | Decisão de arquitetura registrada na especificação [session-proxy](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/session-proxy/spec.md) (cada instância tem endereço sob a origem do portal). Mitigação parcial em [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md), que não cobre `/i/` |
| B1 | Baixo | Conta desabilitada distinguível das demais pelo tempo de resposta do login | **corrigido** | Especificação [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (conta desabilitada indistinguível também por tempo). Em `backend/app/api/auth.py` a senha é verificada antes da checagem de `disabled_at`; teste `test_conta_desabilitada_passa_pelo_hash` em `backend/tests/test_auth.py` |
| B2 | Baixo | Respostas sem cabeçalhos de segurança (CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) | **corrigido** | Especificação [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md). `SecurityHeadersMiddleware` em `backend/app/main.py`; testes em `backend/tests/test_http_hardening.py` |
| B3 | Baixo | `/docs` e `/openapi.json` expostos sem autenticação | **corrigido** | Especificação [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md). `docs_enabled` desligado por padrão em `backend/app/config.py`, aplicado em `backend/app/main.py` |
| B4 | Baixo | Containers de usuários distintos compartilham a mesma rede Docker e se alcançam | **aberto** | Sem correção. `backend/app/services/instances.py` cria toda instância na rede única de `WCUI_DOCKER_NETWORK`; não há rede por usuário nem por instância no runtime |
| B5 | Baixo | `icon_url` usado como `src` de imagem sem validação no front-end | **corrigido** | `localCoverUrl()` em `frontend/src/utils/iconUrl.js` só aceita caminhos sob `/uploads/`; usada em `CatalogSection.jsx` e `ImagesPanel.jsx`, com teste em `frontend/src/utils/iconUrl.test.js`. Reforçado pela CSP do portal (`img-src 'self' data:` em `backend/app/main.py`), especificação [http-hardening](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/http-hardening/spec.md) |
| I1 | Informativo | Opção `harden_desktop` aceita e devolvida pela API sem efeito algum | **corrigido** | O campo deixou de ser aceito e devolvido pela API e não aparece na interface; teste `test_harden_desktop_some_da_api` em `backend/tests/test_image_edit.py`. A coluna permanece no schema (`backend/app/db.py`), sem uso |
| I2 | Informativo | Containers órfãos de implantações anteriores continuam em execução no host | **aberto** | Sem correção. A reconciliação em `backend/app/services/reaper.py` só corrige o estado registrado no banco; nada lista nem remove containers `wcui-*` sem registro |
| I3 | Informativo | Cabeçalho `Server: uvicorn` divulga a stack | **corrigido** | `header -Server` em `deploy/Caddyfile`. Vale na borda de produção; em desenvolvimento, sem Caddy, o cabeçalho continua presente |
| I4 | Informativo | Nenhum evento de segurança era registrado | **corrigido** | Especificação [security-audit-log](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/security-audit-log/spec.md). `backend/app/services/audit_log.py` e chamadores nas rotas; testes em `backend/tests/test_audit_log.py` e `backend/tests/test_audit_events.py` |
| I5 | Informativo | Tabela `sessions` cresce indefinidamente | **corrigido** | Especificação [auth](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/auth/spec.md) (sessões expiradas ou revogadas são purgadas). `purge_sessions` em `backend/app/services/sessions.py`, chamada pelo ciclo de `backend/app/services/reaper.py` |

### Observações sobre os itens corrigidos

Alguns itens corrigidos têm ressalvas que não cabem numa célula de tabela.

- **M1 depende da implantação.** A correção está na composição de produção, não na imagem: o cookie só ganha `Secure` se a allowlist de cabeçalhos encaminhados casar com a subnet real da rede interna. Quem altera a subnet sem ajustar `WCUI_FORWARDED_ALLOW_IPS`, ou sobe o portal atrás de outro proxy com uma composição própria, volta ao estado do achado sem nenhum erro visível. O [Checklist pós-deploy](/operations/post-deploy-checklist/) tem a verificação.
- **M2 foi corrigido com um trade-off.** O limitador por conta permite que um atacante mantenha a conta de uma vítima temporariamente trancada. O estado vive em memória e é zerado quando o portal reinicia. O atraso exponencial recomendado pelo relatório não foi implementado. Detalhes em [Endurecimento do login](/security/login-hardening/).
- **B1 foi verificado pela estrutura do código, não por medição.** O Argon2 agora roda em todos os ramos de falha, e há um teste que confirma a ordem das checagens. A medição de tempo do relatório original não foi refeita.
- **B2 não cobre o caminho de sessão.** Os cabeçalhos valem para as respostas do próprio portal. O conteúdo de `/i/{uuid}/` chega sem CSP — o que é justamente o cenário de M3. A política usa `X-Frame-Options: SAMEORIGIN` em vez do `DENY` recomendado, porque o portal embute a sessão em iframe, e mantém `style-src 'unsafe-inline'` por exigência da biblioteca de interface.
- **I4 tem lacunas de cobertura.** A trilha existe e cobre login, administração e ciclo de vida de instância, mas não registra tentativas negadas por autorização, paradas automáticas nem regeneração de identidade SSH. Ver [Trilha de eventos de segurança](/security/audit-log/).
- **I5 não limita sessões por usuário.** A purga remove linhas mortas; o limite opcional de sessões ativas por usuário, sugerido pelo relatório, não foi implementado.

## Varredura SAST e SCA — 1 de novembro de 2026

- **Data:** 1 de novembro de 2026
- **Commit avaliado:** o relatório não declara o commit; foi produzido no mesmo dia, como complemento ao teste de intrusão
- **Tipo:** análise estática de código (bandit) e análise de composição de software — dependências Python (pip-audit), dependências npm (npm audit) e imagem Docker de produção (trivy)
- **Relatório completo:** [docs/relatorio-sast-sca-2026-11-01.md](https://github.com/alanyoshida/webcontainerui/blob/main/docs/relatorio-sast-sca-2026-11-01.md) (em português)

O relatório não numera os achados; os identificadores `S1` a `S7` abaixo foram atribuídos por esta página, na ordem em que aparecem nele. A severidade é a máxima reportada pela ferramenta, antes da triagem.

| Achado | Severidade | Resumo | Status | Onde foi tratado |
|---|---|---|---|---|
| S1 | Crítico (só em ferramentas de desenvolvimento) | 6 advisories do npm na cadeia de teste e build: `vitest`, `tinypool`, `vite`, `esbuild`, `vite-node`, `@vitest/mocker` | **corrigido** | `frontend/package.json` exige `vitest@^5.0.5`; `frontend/package-lock.json` fixa vitest 5.0.5, vite 6.4.5 e esbuild 0.25.12, e não contém mais `tinypool` nem `vite-node`. Adendo 8.1 do relatório |
| S2 | Médio (bandit B608) | Dois alertas de possível injeção de SQL por construção de string, em `agents_md.py` e `usage_metrics.py` | **aceito** | Falso positivo, triado na seção 4 do relatório. Conferido no código atual: o texto SQL é montado só com constantes do módulo e marcadores de parâmetro gerados; os valores sempre vão como parâmetros nomeados |
| S3 | Baixo (bandit B110/B112) | Quatro blocos `try/except` que engolem a exceção, em `agent_images.py`, `image_covers.py`, `image_pull.py` e `mcp_tool_configs.py` | **aceito** | Isolamento por item, intencional: a falha de uma imagem, capa ou servidor MCP não derruba o startup nem os demais. Documentado nos comentários do código e na seção 4 do relatório; nenhum está em caminho de autenticação ou autorização |
| S4 | Alto | 177 CVEs em pacotes do sistema operacional da imagem base (`python:3.12-slim`, Debian 13): 46 altos, 62 médios, 61 baixos, 8 sem classificação | **aberto** | Sem correção. A mitigação indicada pelo relatório é reconstruir a imagem periodicamente; o repositório não tem automação que faça isso |
| S5 | Médio | 6 CVEs no `pip` 25.0.1 embutido na imagem base | **corrigido** | `Dockerfile` atualiza `pip` e `setuptools` antes de instalar as dependências. Adendo 8.1 do relatório |
| S6 | Não classificado | `msgpack`, dependência transitiva do `aiodocker`, sem piso de versão que exclua releases com falhas de desserialização | **corrigido** | `backend/pyproject.toml` exige `msgpack>=1.2.3`. Adendo 8.1 do relatório |
| S7 | Não classificado | 8 achados "Python" na nova varredura da imagem, todos em cópias embutidas em `pip/_vendor/` | **aceito** | Ruído conhecido, triado no adendo 8.2 do relatório: são cópias usadas só pelo próprio `pip` durante o build, nunca carregadas em execução |

O mesmo relatório registra **zero** vulnerabilidades conhecidas nas dependências Python do portal e nas dependências npm de produção, na data da varredura. Registra também uma limitação: a ferramenta `semgrep` falhou ao executar, de modo que a análise estática automatizada ficou restrita ao `bandit`, e o front-end não teve análise estática automatizada — só a revisão manual do teste de intrusão.

:::caution[Varredura de dependências envelhece]
Os resultados de SCA valem para a data em que foram obtidos. `npm audit`, `pip-audit` e `trivy` não foram reexecutados para esta página, e o repositório não tem verificação automática periódica. Advisories publicados depois de 1 de novembro de 2026 não estão refletidos aqui. Rode as ferramentas contra a sua própria imagem antes de implantar; os comandos estão na seção 7 do relatório.
:::

## O que continua em aberto

Itens abertos e aceitos, com o impacto real de cada um.

### M3 — o container executa na origem do portal (aceito)

O desktop ou terminal é embutido em um iframe servido pelo próprio portal em `/i/{uuid}/`. Todo HTML e JavaScript que sai do container do usuário roda, para o navegador, como se fosse o portal: compartilha o cookie de sessão e pode chamar a API autenticado como o usuário logado.

Na prática: se algo dentro do container conseguir servir conteúdo malicioso pela porta da interface — um pacote npm comprometido que sobrescreva os arquivos do terminal web, ou uma falha de XSS na interface embutida —, esse conteúdo pode excluir as instâncias do usuário, regenerar a chave SSH dele e, **se o usuário logado for administrador, operar toda a API administrativa**: criar usuários, alterar o catálogo, propagar documentos e servidores MCP para as instâncias dos outros. O produto existe para executar agentes de IA e pacotes de terceiros dentro desses containers; a fronteira de confiança do terminal é, de fato, a fronteira de confiança da conta no portal.

A decisão de manter a mesma origem está na especificação do proxy de sessão: é o que permite embutir a sessão sem relaxar a política de origem do container. A correção de fundo — servir as sessões em origem separada, com subdomínio por instância — não foi feita. A CSP adicionada depois protege as páginas do portal, não o conteúdo de `/i/`.

O que você pode fazer hoje: **não use uma conta de administrador para abrir sessões de desktop ou de agente.** Mantenha uma conta administrativa separada, usada só para o painel, e uma conta comum para o trabalho nos containers.

### B4 — rede Docker compartilhada entre usuários (aberto)

Todas as instâncias, de todos os usuários, ficam na mesma rede interna, junto com o portal, o Caddy e o PostgreSQL. De dentro do próprio container — onde o usuário tem root — é possível varrer portas e conectar aos containers dos outros usuários.

O que segura hoje é a credencial aleatória por instância, que no teste resistiu: o container alheio respondeu `401`. Mas ela protege apenas o processo de interface. Qualquer outro serviço que um usuário, um agente ou uma imagem suba em outra porta — um servidor de desenvolvimento, uma API de depuração, um banco local — fica exposto a todos os demais usuários do portal, sem autenticação. Para um produto cuja finalidade é rodar ambientes de desenvolvimento, isso é um cenário comum, não hipotético.

Nenhuma das duas recomendações do relatório foi implementada: não há rede por usuário, e o requisito "todo listener exige a credencial interna" não foi formalizado como contrato das imagens de agente. Enquanto isso, oriente os usuários a escutar apenas em `localhost` dentro do container e trate todos os usuários de uma mesma instalação como pertencentes ao mesmo nível de confiança de rede. Ver [Camadas de isolamento](/security/isolation-layers/).

### I2 — containers órfãos (aberto)

O portal reconcilia o estado das instâncias que conhece: se um container sumiu, a instância passa a "parada". O inverso não acontece. Um container `wcui-*` que continua rodando sem registro correspondente no banco — depois de restaurar um backup antigo, trocar de banco ou apagar o volume de dados sem derrubar os containers — não é detectado nem removido.

O impacto é de higiene e de recurso, com um componente de segurança: o container órfão continua consumindo CPU e memória, mantém o volume e os dados do usuário, segue conectado à rede interna e fica fora de qualquer controle do portal (não é parado por ociosidade nem por revogação de acesso). Os containers criados pelo portal não recebem rótulos que identifiquem a implantação, o que dificulta distinguir órfãos de instâncias legítimas além do prefixo do nome.

Ao reprovisionar ou restaurar, compare manualmente os containers em execução com as instâncias registradas:

```bash
docker ps --filter "name=wcui-" --format '{{.Names}}\t{{.Status}}\t{{.Networks}}'
```

Procedimentos relacionados em [Backup e restauração](/operations/backup-and-restore/) e [Reversão](/operations/rollback/).

### S4 — CVEs no sistema operacional da imagem base (aberto)

A imagem do portal parte de `python:3.12-slim`. Na data da varredura ela carregava 177 CVEs em pacotes do Debian, 46 deles de severidade alta, vários sem versão corrigida disponível. A triagem do relatório os classifica como risco de profundidade: as bibliotecas atingidas (util-linux, ncurses, PAM, systemd) não estão em nenhum caminho de requisição do portal.

Essa triagem é razoável, mas tem um peso particular aqui: o processo do portal tem o socket do Docker e equivale a root no host. Uma falha que em outra aplicação seria contida pelo container, neste componente não é. E o número não diminui sozinho — a única mitigação é reconstruir a imagem para incorporar as correções da base, e o repositório não automatiza isso.

Reconstrua a imagem do portal regularmente (`docker compose build --pull`) e rode a varredura contra a imagem que você de fato implanta.

### S2, S3 e S7 — alertas triados como não exploráveis (aceitos)

- **S2:** os dois alertas de injeção de SQL são falsos positivos. O texto das consultas é montado apenas com constantes e marcadores gerados pelo próprio código; nenhuma entrada de usuário entra no texto SQL. O risco residual é de manutenção: uma alteração futura nessas duas funções que interpole um valor externo não seria barrada por nada além de revisão.
- **S3:** os quatro blocos que engolem exceção são isolamento deliberado no startup e na montagem de configuração. O custo é de observabilidade — uma falha nesses pontos pode passar sem registro — e não de autorização.
- **S7:** os achados em `pip/_vendor/` são cópias internas do `pip`, que só executa durante o build da imagem. Continuam aparecendo em varreduras; filtre o diretório ou trate como ruído conhecido.

## O que as auditorias não cobriram

Para dimensionar o que os relatórios provam:

- O teste de intrusão rodou contra o ambiente de **desenvolvimento** local. A composição de produção — Caddy, plano de dados externo, PostgreSQL — foi revisada estaticamente no teste, não atacada. O plano de dados externo das sessões e a migração para PostgreSQL são posteriores ao commit avaliado e **não passaram por teste de intrusão**.
- Ficaram fora do escopo, por decisão: negação de serviço destrutiva, exploração em rede pública e engenharia social.
- Escape de container e segurança das imagens de terceiros (webtop, CLIs dos agentes) não foram avaliados.
- Os dois relatórios combinam ferramentas automatizadas e revisão manual, executadas sobre o ambiente do próprio mantenedor. Nenhum deles é uma auditoria por terceiro independente.

Os riscos estruturais que não são "achados" — porque decorrem do que o produto faz — estão em [Superfície de confiança](/security/trust-surface/).
