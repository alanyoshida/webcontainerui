import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";

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

  const remove = useCallback(
    async (instanceId) => {
      await api.deleteInstance(instanceId, true);
      await reload();
    },
    [reload]
  );

  return { instances, loading, error, reload, create, stop, remove };
}
