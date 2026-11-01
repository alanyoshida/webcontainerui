# Design

## Context

Ver proposal.md para o porquê. Este documento cobre só o como, com base em
testes reais feitos contra as 5 imagens de agente (`docker run` direto nos
binários `claude`, `opencode`, `hermes`, `agy`, `omp`) — incluindo, para o
`omp`, um round-trip completo contra um servidor FastMCP local de verdade
(`--network host`, ferramenta `somar`), já que ele não tem subcomando
`mcp add` para inspecionar.

A injeção de arquivos num container já existe para identidade SSH e
`AGENTS.md` (`backend/app/services/instances.py`, `_inject_ssh_identity` /
`_inject_agents_md`, chamadas depois de `create_container` em
`_provision_instance`) — ambas usam `runtime.put_archive` para gravar um
arquivo que é **só nosso** (nada mais escreve nele). MCP quebra essa
suposição: o arquivo de config de cada ferramenta também guarda outro
estado dela (sessão, migração, outras configurações do usuário), então
`put_archive` sobrescrevendo o arquivo inteiro destruiria esse estado.

## Goals / Non-Goals

**Goals:**
- Cadastro genérico de servidor MCP (nome, transporte, comando/args/env ou
  url/headers) que funciona vinculado a qualquer uma das 5 imagens, sem o
  admin reescrever nada por ferramenta.
- Vincular/editar/desvincular propaga pras instâncias vivas sem rebuild de
  imagem.
- Nunca perder configuração alheia já presente no arquivo de cada
  ferramenta ao injetar MCP.
- Detectar, logo após escrever, se o merge quebrou o contrato esperado do
  arquivo daquela ferramenta — e avisar o administrador, nunca deixar
  passar em silêncio.

**Non-Goals:**
- Não cobre validar se o servidor MCP cadastrado realmente conecta (isso é
  responsabilidade do usuário dentro da sessão, como ligar qualquer MCP
  hoje).
- Não cobre instâncias webtop.
- Não cobre descoberta/catálogo de servidores MCP públicos.

## Decisions

### Schema genérico do cadastro

```
McpServer (biblioteca):
  display_name   único
  transport       "stdio" | "http" | "sse"
  command         (só stdio)           ex: "npx"
  args            (só stdio, lista)    ex: ["-y", "some-mcp-server"]
  url             (só http/sse)
  env             {chave: valor}       -- cifrado em repouso (stdio)
  headers         {chave: valor}       -- cifrado em repouso (http/sse)
  enabled         bool, default true
```

### Contrato confirmado por ferramenta

Tabela validada com testes reais (não documentação — nenhuma das 5 CLIs
documenta publicamente o schema do arquivo; `omp`, em particular, não tem
nem subcomando `mcp add` para descobrir por `--help`).

| Imagem | Arquivo | Formato | Chave MCP | stdio | remoto (http/sse) |
|---|---|---|---|---|---|
| claude-code | `/config/.claude.json` | JSON, **compartilhado** | `mcpServers` | `{type:"stdio", command, args, env}` | `{type:"http"\|"sse", url, headers}` |
| opencode | `/config/.config/opencode/opencode.jsonc` | JSONC, **compartilhado** | `mcp` | `{type:"local", command:[cmd,...args], environment}` | `{type:"remote", url, headers}` |
| agy | `/config/.gemini/config/mcp_config.json` | JSON, **compartilhado** | `mcpServers` | `{command, args, env, disabled}` (sem campo de tipo) | `{serverUrl, headers, disabled}` (campo é `serverUrl`, não `url`) |
| hermes | `/config/.hermes/config.yaml` + `/config/.hermes/.env` | **YAML** + env, compartilhado | `mcp_servers` | `{command, args, env, enabled}` | `{url, headers: {Chave: "Bearer ${MCP_<NOME>_API_KEY}"}, enabled}` — segredo vai pro `.env`, nunca inline no YAML |
| oh-my-pi | `~/.omp/agent/mcp.json` | JSON, **dedicado só a MCP** | `mcpServers` | `{transport:"stdio", command, args, env, disabled}` | `{transport:"http"\|"sse", url, headers, disabled}` |

Diferenças que cada tradutor precisa respeitar: nome do campo de URL
(`url` vs `serverUrl`), presença/ausência de campo de tipo e seu nome
(`type` vs `transport` vs nenhum), `command`+`args` separados vs array
combinado (OpenCode), `env` vs `environment`, `enabled` vs `disabled`
(polaridade invertida), e o `.env` à parte do Hermes.

### Merge, não overwrite — precisa ler o arquivo do container

`ContainerRuntime` hoje só tem `put_archive` (escreve) e `exec` (roda
comando); não tem como ler um arquivo de volta. Duas opções:

1. **Rodar o merge dentro do container via `exec`** (script Python/shell
   embutido). Evita mudar o protocolo, mas espalha a lógica de parsing
   JSON/YAML por 5 scripts embutidos, sem poder testar com
   `FakeContainerRuntime`, e exige YAML disponível no Python de sistema de
   cada imagem (não garantido — o Hermes usa um venv próprio em
   `/opt/hermes`, separado do `python3` de sistema da base).
2. **Adicionar `get_archive` ao protocolo** *(escolhido)*: novo método
   `ContainerRuntime.get_archive(container_id, path) -> bytes | None`, que
   devolve o **conteúdo do arquivo já desempacotado** (não o tar cru —
   `aiodocker` `container.get_archive()` devolve um tar de um arquivo só,
   e é a implementação que desempacota, não quem chama), `None` se o
   arquivo não existir. O backend lê, faz o merge em
   Python puro (testável, uma implementação só por formato — JSON e YAML —
   reaproveitada pelos 5 tradutores), e escreve de volta com
   `put_archive`. Mesma simetria de `FakeContainerRuntime` já ter
   `put_archive_calls`: ganha um dicionário interno `_files` por
   container, populado por `put_archive` e lido por `get_archive`, para
   os testes simularem round-trip sem Docker de verdade.

Ganha a opção 2 por manter toda a lógica de tradução e merge no nosso
código Python (mesmo padrão arquitetural de `ContainerRuntime` como
protocolo estreito, descrito em `docker_runtime.py`), e por permitir
testar o merge inteiro com o runtime falso, sem depender de Docker.

### Dependência nova: PyYAML

O backend não tem nenhuma dependência YAML hoje (só JSON, via `json` da
biblioteca padrão). O Hermes exige escrever YAML preservando comentários e
chaves que não são nossas (`_config_version`, `fallback_model`
comentado). `ruamel.yaml` preserva comentários e formatação ao
round-tripar; `PyYAML` não. Como o arquivo do Hermes tem comentários
extensos de documentação que o usuário não deve perder a cada edição de
MCP, a dependência nova é `ruamel.yaml`, não `PyYAML`.

### Arquivo dedicado (oh-my-pi) vs compartilhado (as outras 4)

`~/.omp/agent/mcp.json` só guarda MCP (nunca vimos outra chave nele,
diferente dos outros 4) — tecnicamente dá pra sobrescrever inteiro sem
risco. Mesmo assim, o merge genérico (ler, trocar só a chave `mcpServers`,
escrever) é aplicado igual às outras 4: um caminho de código só, sem
exceção por ferramenta, e blinda contra o dia em que o `omp` passar a
guardar mais coisa nesse arquivo.

### Segredos cifrados em repouso

`env` e `headers` do cadastro são cifrados com a mesma infraestrutura
Fernet de `ssh_identity.py` (`settings.ssh_key_encryption_key`), guardados
como blob cifrado por servidor MCP. Só decifrados no momento de montar o
payload traduzido pra injetar. Editar o cadastro exige reenviar os
valores (não é possível mostrar de volta um valor já cifrado) — mesmo
trade-off já aceito pela chave SSH.

Para o Hermes, o valor decifrado do header/segredo vai pro `.env`
(`MCP_<NOME_NORMALIZADO>_API_KEY=<valor>`), e o YAML recebe só a
referência `${MCP_<NOME_NORMALIZADO>_API_KEY}` — nunca o valor em claro no
arquivo que o `AGENTS.md`/skills já tratam como "pode ter outro estado
visível". As outras 4 ferramentas embutem o valor decifrado diretamente no
JSON (é onde elas mesmas o colocariam, via seu próprio `mcp add`).

### Gatilho de propagação: sempre recomputa o estado inteiro daquele par (imagem, ferramenta)

Para evitar corrida entre duas mudanças quase simultâneas (vincular MCP A
e editar MCP B vinculado à mesma imagem), cada propagação não faz um PATCH
pontual — ela resolve a lista **completa** de MCPs vinculados à imagem
naquele momento (join `image_mcp_servers`+`mcp_servers`), monta o objeto
`mcpServers`/`mcp`/`mcp_servers` inteiro traduzido, e substitui essa chave
por completo no arquivo (preservando as demais chaves do arquivo). Mesmo
princípio de "sempre a partir do estado atual do banco" já usado nos
`buildargs` de skills — qualquer gatilho converge pro mesmo resultado
final, mesmo que dois disparem em sequência rápida.

### Injeção na criação da instância

Mesmo ponto de `instances.py` que já injeta identidade SSH e `AGENTS.md`
(`_provision_instance`, depois de `create_container`): nova função
`_inject_mcp_servers` resolve os MCPs vinculados à imagem e escreve o
arquivo traduzido antes da instância ficar pronta. Falha isolada por MCP e
por instância, mesmo padrão dos outros dois.

### Validação de schema depois de escrever, antes de dar por concluído

O merge preserva o que já estava no arquivo, mas não garante sozinho que o
objeto que a gente escreveu bate com o que a ferramenta espera — um bug no
tradutor, ou uma mudança de versão da ferramenta, podem quebrar o contrato
sem nenhum erro aparente no momento da escrita (o `put_archive` só falha
se o container não existir, não se o conteúdo for inválido). Por isso,
depois de escrever (seja na propagação ou na injeção de instância nova), o
sistema lê o arquivo de volta (`get_archive`) e valida a chave de MCP
contra um **JSON Schema por ferramenta**, derivado direto da tabela de
contrato confirmado acima — cada schema aceita só os dois formatos de
entrada (stdio ou remoto) daquela ferramenta, com os nomes de campo
exatos dela (`serverUrl` na Agy, `transport` no oh-my-pi, etc.).

Exemplo (Agy — sem campo de tipo, distinguido pela presença de `command`
ou `serverUrl`):

```json
{
  "type": "object",
  "additionalProperties": {
    "type": "object",
    "oneOf": [
      {"properties": {"command": {"type": "string"}, "args": {"type": "array"}, "env": {"type": "object"}, "disabled": {"type": "boolean"}}, "required": ["command"]},
      {"properties": {"serverUrl": {"type": "string"}, "headers": {"type": "object"}, "disabled": {"type": "boolean"}}, "required": ["serverUrl"]}
    ]
  }
}
```

Os outros 4 seguem o mesmo molde, usando os nomes de campo da tabela de
contrato. Validação via `jsonschema` (dependência nova, leve e já conhecida
— foi o que o próprio `mcp` SDK usa, visto testando o Hermes).

**Quando a validação falha**: o sistema não desfaz a escrita (o arquivo já
está no estado novo, melhor do que deixar a instância sem reagir a nada),
mas marca aquela propagação/injeção como tendo quebrado o contrato,
reaproveitando o mesmo relatório de falhas por instância que já existe
para propagação (`propagation_failures`), só que cada entrada carrega a
mensagem do campo que violou o schema, não só "falhou" — ex: `"MCP
'minha-skill' na instância X: campo 'command' obrigatório ausente"`. A
resposta da rota de vínculo/edição/desvínculo devolve essa lista pro
admin, e o painel mostra um alerta pedindo pra corrigir os campos daquele
MCP, nomeando qual.

### Desvínculo remove só a entrada, não o arquivo

Diferente do `AGENTS.md` (que remove o arquivo inteiro ao desvincular),
desvincular um MCP só tira aquela chave do objeto — o arquivo continua
existindo com os demais MCPs (ou vazio) e o resto do estado da ferramenta
intacto. Isso é só uma consequência natural de "recomputa o estado
inteiro": a lista de MCPs vinculados já vem sem aquele.

## Risks / Trade-offs

- **Schema do oh-my-pi validado só por engenharia reversa + teste próprio**
  (sem documentação oficial, sem `mcp add` pra comparar) → mitigado por um
  teste de ponta a ponta real feito nesta exploração (FastMCP local,
  `--network host`, confirmando tanto stdio quanto http através do próprio
  log do servidor e da notificação `"mounted mcp__<nome>_<tool>"` que o
  `omp` emite). Risco residual: uma versão futura do `omp` pode mudar esse
  formato sem aviso, já que não é uma API pública estável.
- **Arquivo compartilhado com estado que não é nosso** (sessão, migração,
  outras configs) → mitigado pelo merge seletivo (só a chave de MCP),
  nunca overwrite do arquivo inteiro.
- **Corrida entre duas propagações quase simultâneas pro mesmo
  container** → mitigada (não eliminada) por sempre recomputar o estado
  completo a partir do banco; a última escrita que chegar reflete o banco
  inteiro, então o pior caso é uma leitura intermediária descartada, não
  um estado inconsistente.
- **Dependência nova (`ruamel.yaml`)** só para o Hermes → aceito; é a
  única das 5 ferramentas com config em YAML, e perder os comentários do
  arquivo a cada edição seria um efeito colateral ruim pro usuário.
- **Validação pós-escrita não desfaz a escrita** (não há "rollback" do
  arquivo) → aceito: desfazer exigiria guardar o conteúdo anterior e
  decidir se restaura, o que esconderia do admin que algo mudou. Preferido
  deixar o estado novo (mesmo que quebrado) visível e reportado, para o
  admin corrigir os campos cientes do que está no arquivo agora.

## Migration Plan

Mudança aditiva: tabelas novas (`mcp_servers`, `image_mcp_servers`),
método novo no protocolo de runtime (`get_archive`, com default seguro
nos dois lados — real e falso), dependências novas (`ruamel.yaml` e
`jsonschema`). Sem coluna removida ou redefinida. Roda automaticamente na
próxima inicialização do portal.
