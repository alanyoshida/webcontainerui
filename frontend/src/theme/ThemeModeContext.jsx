import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import { buildTheme, DEFAULT_THEME_MODE, THEME_MODES } from "../theme";

const STORAGE_KEY = "wcui.theme";

const ThemeModeContext = createContext(null);

function readStoredMode() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return THEME_MODES.includes(stored) ? stored : DEFAULT_THEME_MODE;
  } catch {
    // localStorage indisponível (ex.: modo privado): cai no padrão, sem persistir
    return DEFAULT_THEME_MODE;
  }
}

/**
 * Guarda o tema escolhido (ver theming spec: dark é o padrão sem escolha
 * registrada, e a escolha explícita persiste entre sessões via
 * `localStorage`). Aplica o tema MUI correspondente via `ThemeProvider`.
 */
export function ThemeModeProvider({ children }) {
  const [mode, setMode] = useState(readStoredMode);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // modo privado ou storage bloqueado: a escolha só vale para esta sessão
    }
  }, [mode]);

  const theme = useMemo(() => buildTheme(mode), [mode]);
  const value = useMemo(() => ({ mode, setMode }), [mode]);

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) throw new Error("useThemeMode precisa estar dentro de ThemeModeProvider");
  return ctx;
}
