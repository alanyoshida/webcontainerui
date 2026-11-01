import { createTheme } from "@mui/material/styles";

const PALETTES = {
  light: {
    mode: "light",
    primary: { main: "#1565c0" },
    secondary: { main: "#546e7a" },
    background: { default: "#f4f6f8", paper: "#ffffff" },
  },
  // Carvão, não preto puro (ver theming spec: "Identificação do dark").
  dark: {
    mode: "dark",
    primary: { main: "#5b9bd9" },
    secondary: { main: "#90a4ae" },
    background: { default: "#121417", paper: "#1a1d21" },
  },
  // Primário pêssego sobre fundo claro suave (ver theming spec:
  // "Identificação do pastel").
  pastel: {
    mode: "light",
    primary: { main: "#d98e6b" },
    secondary: { main: "#8d7b74" },
    background: { default: "#fdf6ef", paper: "#fffaf5" },
  },
};

const SHAPE = {
  light: { borderRadius: 12 },
  dark: { borderRadius: 12 },
  pastel: { borderRadius: 16 },
};

// Fontes próprias, carregadas por `@fontsource-variable/*` em main.jsx —
// sem depender de serviço externo (ver theming spec: "funcionamento sem
// acesso à internet"). JetBrains Mono fica reservada para conteúdo técnico
// (chave SSH, referência de imagem, saídas de log — ver MONO_FONT_FAMILY).
export const MONO_FONT_FAMILY = '"JetBrains Mono Variable", ui-monospace, monospace';
const SANS_FONT_FAMILY =
  '"Inter Variable", "Roboto", "Helvetica", "Arial", sans-serif';

/**
 * Um tema por modo (ver design.md D1) — light, dark (carvão) e pastel
 * (pêssego). `ThemeModeProvider` (abaixo) decide qual construir e aplica
 * via `ThemeProvider` em App.jsx.
 */
export function buildTheme(mode) {
  return createTheme({
    palette: PALETTES[mode],
    shape: SHAPE[mode],
    typography: {
      fontFamily: SANS_FONT_FAMILY,
      h5: { fontWeight: 600 },
      h6: { fontWeight: 600 },
    },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            transition: "box-shadow 0.2s ease, transform 0.2s ease",
            "&:hover": {
              boxShadow: mode === "pastel" ? "0 4px 14px rgba(0, 0, 0, 0.06)" : "0 6px 20px rgba(0, 0, 0, 0.08)",
            },
          },
        },
      },
      MuiCardContent: {
        styleOverrides: {
          root: {
            padding: 20,
          },
        },
      },
    },
  });
}

export const THEME_MODES = ["light", "dark", "pastel"];
export const DEFAULT_THEME_MODE = "dark";
