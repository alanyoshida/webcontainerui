# Proposal

## Why

A reconciliação de estado (`reconcile_instance_states`) só roda uma vez, na
inicialização do processo. Se um container morre por fora enquanto o portal
está no ar — `docker kill` externo, OOM, crash do próprio webtop — a
instância fica presa como "em execução" no banco indefinidamente, até o
próximo restart do portal. Reproduzido ao vivo: matei um container real com
`docker kill`, a instância continuou aparecendo "Em execução" na interface, e
só passou a "Parada" depois que forcei manualmente a atualização do estado no
banco. O requisito "Estado real do container reconcilia com o registrado" já
existe na spec de `desktop-instances`, mas não diz quando a reconciliação
acontece — a implementação atual satisfaz a letra (o mecanismo existe e
funciona quando chamado) sem satisfazer o espírito (o usuário só vê o estado
corrigido numa janela estreita, logo após o portal reiniciar).

## What Changes

- A reconciliação de estado passa a rodar periodicamente, não só na
  inicialização, reaproveitando o loop de fundo já existente do reaper de
  ociosidade em vez de criar uma tarefa de fundo nova.
- A cada iteração do loop, primeiro reconcilia o estado real dos containers
  das instâncias marcadas como "em execução", depois aplica a verificação de
  ociosidade sobre o estado já corrigido — uma instância cujo container
  morreu por fora não deve ser contada como candidata a "parada por
  ociosidade" (ela já está parada, só o registro estava desatualizado).

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `desktop-instances`: o requisito "Estado real do container reconcilia com o
  registrado" passa a exigir que a reconciliação aconteça periodicamente
  durante a operação normal do portal, não apenas na inicialização do
  processo.

## Impact

- Backend: `backend/app/services/reaper.py` (`run_reaper` passa a reconciliar
  antes de reaper ociosidade, a cada iteração), `backend/app/main.py`
  (mantém a reconciliação de inicialização — cobre o intervalo entre o
  restart e a primeira iteração do loop — e segue chamando `run_reaper` sem
  mudança de assinatura).
- Sem mudança de API pública, sem mudança de schema — não é **BREAKING**.
