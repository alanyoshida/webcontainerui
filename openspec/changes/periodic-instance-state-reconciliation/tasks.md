# Tasks

## 1. Backend: reconciliação periódica no loop do reaper

- [x] 1.1 Em `backend/app/services/reaper.py`, fazer `run_reaper` chamar
      `reconcile_instance_states(conn, runtime)` no início de cada iteração,
      antes de `reap_idle_instances`, reaproveitando a mesma conexão aberta
      naquela iteração; verificar com teste novo em `backend/tests/test_reaper.py`
      que, rodando `run_reaper` com intervalo curto sobre uma instância cujo
      container foi removido do runtime por fora, o estado vira "stopped" sem
      chamar `reconcile_instance_states` diretamente (só pelo loop)
- [x] 1.2 Verificar que uma instância com container encerrado por fora não é
      tratada como candidata a "parar por ociosidade" na mesma iteração (a
      reconciliação já a deixou "stopped" antes de `find_idle_running_instances`
      rodar); verificar com teste cobrindo que `stop_instance`/`runtime.stop_container`
      não é chamado para essa instância depois que ela já foi reconciliada
- [x] 1.3 Confirmar que uma falha na chamada de reconciliação dentro de uma
      iteração não interrompe o loop (mesma proteção `try/except` por
      iteração que já existe para `reap_idle_instances`); verificar com teste
      cobrindo falha injetada em `reconcile_instance_states`

## 2. Verificação integrada

- [x] 2.1 Rodar a suíte completa do backend (`pytest`) e verificar que todos
      os testes passam, incluindo os já existentes de `test_reaper.py`
- [x] 2.2 Validar manualmente no preview: subir uma instância real, matar o
      container por fora (`docker kill`), e confirmar que o estado no banco
      vira "stopped" sozinho dentro do próximo ciclo do reaper, sem reiniciar
      o portal

## Workflow follow-up

- Sincronizar a spec delta (`desktop-instances`) para a spec principal e
  arquivar esta change após a revisão do usuário.
