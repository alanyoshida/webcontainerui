import { buildTheme, DEFAULT_THEME_MODE, THEME_MODES } from "./theme";

test("dark é o modo padrão", () => {
  expect(DEFAULT_THEME_MODE).toBe("dark");
});

test("oferece exatamente light, dark e pastel", () => {
  expect(THEME_MODES).toEqual(["light", "dark", "pastel"]);
});

test("dark usa superfície carvão, não preto puro", () => {
  const theme = buildTheme("dark");
  expect(theme.palette.background.default.toLowerCase()).toBe("#121417");
  expect(theme.palette.background.default.toLowerCase()).not.toBe("#000000");
});

test("pastel usa primário pêssego sobre fundo claro", () => {
  const theme = buildTheme("pastel");
  expect(theme.palette.mode).toBe("light");
  // tom pêssego: mais vermelho que azul no primário
  const [r, , b] = theme.palette.primary.main.match(/[0-9a-f]{2}/gi).map((h) => parseInt(h, 16));
  expect(r).toBeGreaterThan(b);
});

test("os três temas têm paletas de primário distintas", () => {
  const mains = THEME_MODES.map((mode) => buildTheme(mode).palette.primary.main);
  expect(new Set(mains).size).toBe(3);
});
