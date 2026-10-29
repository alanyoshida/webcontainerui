# Design

## Context

`reconcile_instance_states` (`backend/app/services/reaper.py`) já existe e
já funciona corretamente quando chamado — o problema não é o mecanismo, é a
cadência. Hoje só é chamado uma vez, em `backend/app/main.py:66`, antes do
`run_reaper` ser agendado como tarefa de fundo via `spawn` (`main.py:77-85`).
`run_reaper` já roda um loop periódico (`asyncio.sleep(interval_seconds)`
seguido de `reap_idle_instances`) — é a infraestrutura de tarefa de fundo que
esta change reaproveita, ver proposal.md - What Changes.

## Goals / Non-Goals

**Goals:**
- Detectar um container encerrado por fora durante a operação normal do
  portal, não só na janela estreita logo após um restart.
- Reaproveitar o loop de fundo já existente (`run_reaper`), sem criar uma
  segunda tarefa de fundo nem um novo intervalo configurável.

**Non-Goals:**
- Não reduzir o intervalo de reconciliação abaixo de
  `reaper_interval_seconds` — detectar em segundos exigiria observar eventos
  do Docker (`docker events`) em vez de poll, fora de escopo aqui.
- Não mudar o comportamento de `reconcile_instance_states` em si (já correto);
  só muda quando ela é chamada.

## Decisions

### Reconciliar dentro do loop do reaper, antes de reap_idle_instances

`run_reaper` passa a chamar `reconcile_instance_states(conn, runtime)` no
início de cada iteração, antes de `reap_idle_instances`. A ordem importa:
uma instância cujo container morreu por fora deve ser corrigida para
"parada" antes da checagem de ociosidade rodar sobre ela — senão
`find_idle_running_instances` poderia tentar tratar como "parar por
ociosidade" (chamando `stop_instance`, que por sua vez chamaria
`runtime.stop_container` num container que já não existe) uma instância que
já devia constar como parada por outro motivo.

Alternativa considerada: *tarefa de fundo própria para reconciliação,
independente do reaper.* Rejeitada por duplicar o padrão de loop
(`asyncio.sleep` + tratamento de exceção por iteração) que `run_reaper` já
implementa, para o mesmo tipo de trabalho periódico de correção de estado —
sem necessidade de um intervalo diferente do já configurado.

### Mantém a chamada de inicialização em main.py

A reconciliação de startup (`main.py:66`) continua existindo: cobre o
intervalo entre o processo subir e a primeira iteração do loop do reaper
(que só reconcilia depois do primeiro `asyncio.sleep(interval_seconds)`).
Removê-la reabriria a janela original que motivou essa chamada (D-risco
"worker é ponto único de falha", design.md de `webtop-portal`).

## Risks / Trade-offs

- [Reconciliar a cada iteração custa uma chamada ao runtime por instância
  "em execução", a cada `reaper_interval_seconds`] → já é o custo que
  `reap_idle_instances` paga hoje por iteração para as instâncias
  candidatas; a diferença é rodar sobre o conjunto de instâncias em
  execução, não só as ociosas. Em escala alvo (dezenas de instâncias),
  negligenciável frente ao intervalo de dezenas de segundos do loop.
- [Falha do runtime numa iteração] → já coberto pelo `try/except Exception`
  por iteração que `run_reaper` tem hoje; uma falha não interrompe o loop,
  a próxima iteração tenta de novo.
