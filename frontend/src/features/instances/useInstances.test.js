import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import { useInstances } from "./useInstances";

vi.mock("../../api/client", () => ({ api: { listInstances: vi.fn() } }));

beforeEach(() => {
  vi.useFakeTimers();
  api.listInstances.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

// `waitFor` do testing-library usa timers reais por baixo; sob fake timers
// o jeito seguro de deixar a promise mockada (resolvida) se resolver é
// avançar um microtask explicitamente dentro de `act`.
async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve();
  });
}

test("recarrega periodicamente para refletir mudanças de estado feitas pelo backend (reaper, reconciliação)", async () => {
  api.listInstances
    .mockResolvedValueOnce([{ id: "i1", state: "running" }])
    .mockResolvedValueOnce([{ id: "i1", state: "stopped" }]);

  const { result } = renderHook(() => useInstances());
  await flushMicrotasks();

  expect(result.current.instances).toEqual([{ id: "i1", state: "running" }]);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });

  expect(result.current.instances).toEqual([{ id: "i1", state: "stopped" }]);
  expect(api.listInstances).toHaveBeenCalledTimes(2);
});

test("para de recarregar quando o componente desmonta", async () => {
  api.listInstances.mockResolvedValue([]);

  const { unmount } = renderHook(() => useInstances());
  await flushMicrotasks();
  expect(api.listInstances).toHaveBeenCalledTimes(1);

  unmount();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(20000);
  });

  expect(api.listInstances).toHaveBeenCalledTimes(1);
});
