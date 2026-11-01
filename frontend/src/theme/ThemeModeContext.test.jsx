import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeModeProvider, useThemeMode } from "./ThemeModeContext";

const STORAGE_KEY = "wcui.theme";

function Probe() {
  const { mode, setMode } = useThemeMode();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <button onClick={() => setMode("pastel")}>pastel</button>
      <button onClick={() => setMode("light")}>light</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
});

test("sem escolha registrada, o padrão é dark", () => {
  render(
    <ThemeModeProvider>
      <Probe />
    </ThemeModeProvider>
  );

  expect(screen.getByTestId("mode")).toHaveTextContent("dark");
});

test("escolha registrada anteriormente prevalece sobre o padrão", () => {
  localStorage.setItem(STORAGE_KEY, "light");

  render(
    <ThemeModeProvider>
      <Probe />
    </ThemeModeProvider>
  );

  expect(screen.getByTestId("mode")).toHaveTextContent("light");
});

test("trocar de tema atualiza o contexto e persiste a escolha", async () => {
  const user = userEvent.setup();
  render(
    <ThemeModeProvider>
      <Probe />
    </ThemeModeProvider>
  );

  await user.click(screen.getByRole("button", { name: "pastel" }));

  expect(screen.getByTestId("mode")).toHaveTextContent("pastel");
  expect(localStorage.getItem(STORAGE_KEY)).toBe("pastel");
});
