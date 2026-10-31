import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useFullscreen } from "./useFullscreen";

function setFullscreenElement(element) {
  Object.defineProperty(document, "fullscreenElement", {
    value: element,
    configurable: true,
  });
}

afterEach(() => {
  setFullscreenElement(null);
  document.body.style.overflow = "";
});

test("entra em tela cheia nativa quando o elemento aceita requestFullscreen", async () => {
  const element = document.createElement("div");
  element.requestFullscreen = vi.fn().mockResolvedValue(undefined);
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });

  expect(element.requestFullscreen).toHaveBeenCalledTimes(1);
  expect(result.current.mode).toBe("native");
  expect(result.current.isFullscreen).toBe(true);
});

test("cai no modo imersivo quando o elemento não tem requestFullscreen", async () => {
  const element = document.createElement("div");
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });

  expect(result.current.mode).toBe("immersive");
  expect(result.current.isFullscreen).toBe(true);
});

test("cai no modo imersivo quando requestFullscreen é recusado", async () => {
  const element = document.createElement("div");
  element.requestFullscreen = vi.fn().mockRejectedValue(new Error("recusado"));
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });

  expect(result.current.mode).toBe("immersive");
});

test("sincroniza o estado quando o fullscreenchange nativo indica saída (ESC nativo)", async () => {
  const element = document.createElement("div");
  element.requestFullscreen = vi.fn().mockImplementation(() => {
    setFullscreenElement(element);
    return Promise.resolve();
  });
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });
  expect(result.current.mode).toBe("native");

  act(() => {
    setFullscreenElement(null);
    document.dispatchEvent(new Event("fullscreenchange"));
  });

  expect(result.current.mode).toBe("normal");
  expect(result.current.isFullscreen).toBe(false);
});

test("sai do modo imersivo ao pressionar ESC", async () => {
  const element = document.createElement("div");
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });
  expect(result.current.mode).toBe("immersive");

  act(() => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  });

  expect(result.current.mode).toBe("normal");
});

test("exit() chama document.exitFullscreen quando em modo nativo", async () => {
  const element = document.createElement("div");
  element.requestFullscreen = vi.fn().mockImplementation(() => {
    setFullscreenElement(element);
    return Promise.resolve();
  });
  document.exitFullscreen = vi.fn().mockImplementation(() => {
    setFullscreenElement(null);
    return Promise.resolve();
  });
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });

  act(() => {
    result.current.exit();
  });

  expect(document.exitFullscreen).toHaveBeenCalledTimes(1);
  expect(result.current.mode).toBe("normal");
});

test("cai no modo imersivo quando requestFullscreen nunca resolve nem rejeita (host que ignora o pedido)", async () => {
  vi.useFakeTimers();
  try {
    const element = document.createElement("div");
    // Promessa que nunca se resolve, simulando um host embutido que ignora
    // o pedido de tela cheia sem recusar explicitamente.
    element.requestFullscreen = vi.fn().mockReturnValue(new Promise(() => {}));
    const containerRef = { current: element };

    const { result } = renderHook(() => useFullscreen(containerRef));
    let enterPromise;
    act(() => {
      enterPromise = result.current.enter();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
      await enterPromise;
    });

    expect(result.current.mode).toBe("immersive");
    expect(result.current.isFullscreen).toBe(true);
  } finally {
    vi.useRealTimers();
  }
});

test("exit() no modo imersivo restaura o layout sem chamar exitFullscreen nativo", async () => {
  const element = document.createElement("div");
  document.exitFullscreen = vi.fn();
  const containerRef = { current: element };

  const { result } = renderHook(() => useFullscreen(containerRef));
  await act(async () => {
    await result.current.enter();
  });
  expect(result.current.mode).toBe("immersive");
  expect(document.body.style.overflow).toBe("hidden");

  act(() => {
    result.current.exit();
  });

  expect(document.exitFullscreen).not.toHaveBeenCalled();
  expect(result.current.mode).toBe("normal");
  expect(document.body.style.overflow).toBe("");
});
