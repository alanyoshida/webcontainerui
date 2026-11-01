import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";

// O reaper de ociosidade e a reconciliação de estado rodam no backend sem
// avisar o front-end (nenhum canal de push existe para isso); sem um poll
// aqui, uma instância que o backend já marcou como parada continuaria
// aparecendo "em execução" na tela até a próxima ação manual do usuário.
const POLL_INTERVAL_MS = 5000;

export function useInstances() {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      setInstances(await api.listInstances());
      setError("");
    } catch {
      setError("Não foi possível carregar suas instâncias.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    const interval = setInterval(reload, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [reload]);

  const create = useCallback(
    async (imageId) => {
      await api.createInstance(imageId);
      await reload();
    },
    [reload]
  );

  const stop = useCallback(
    async (instanceId) => {
      await api.stopInstance(instanceId);
      await reload();
    },
    [reload]
  );

  const update = useCallback(
    async (instanceId) => {
      await api.updateInstance(instanceId);
      await reload();
    },
    [reload]
  );

  const remove = useCallback(
    async (instanceId) => {
      await api.deleteInstance(instanceId, true);
      await reload();
    },
    [reload]
  );

  return { instances, loading, error, reload, create, stop, update, remove };
}
